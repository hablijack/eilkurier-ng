"""OpenAI-compatible client for the language model: Ollama on the Jetson, vLLM on captiva, or the simulator.

One request at a time, temperature 0, strict JSON-schema output. The model is often unreachable (powered off,
busy); that is reported as `Unavailable` and the work simply waits.
"""

import json
import logging
import time
from typing import Any

import httpx

from eilkurier.settings import Settings

log = logging.getLogger(__name__)


class Unavailable(RuntimeError):
    """Runtime unreachable or overloaded: retry later, it is not the item's fault."""


class BadAnswer(RuntimeError):
    """The runtime answered, but not with a usable JSON object."""


class LLM:
    def __init__(self, settings: Settings, http: httpx.Client | None = None) -> None:
        self.settings = settings
        self.model = settings.llm_model
        self.embedding_model = settings.embedding_model
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}
        self.http = http or httpx.Client(
            base_url=settings.llm_url.rstrip("/"),
            timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=5.0),
            headers=headers,
        )
        self._last_probe = 0.0
        self._available = False

    def close(self) -> None:
        self.http.close()

    # -- availability ---------------------------------------------------------------------------

    def available(self, force: bool = False) -> bool:
        """Probe `GET /v1/models` (rate-limited while the runtime is down)."""
        now = time.monotonic()
        if (
            not force
            and not self._available
            and now - self._last_probe < self.settings.llm_probe_interval_seconds
        ):
            return False
        self._last_probe = now
        try:
            response = self.http.get("/v1/models", timeout=5.0)
            response.raise_for_status()
            served = {m["id"] for m in response.json()["data"]}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            if self._available:
                log.info("language model went away: %s", type(exc).__name__)
            self._available = False
            return False
        wanted = {self.model} | ({self.embedding_model} if self.embedding_model else set())
        # Ollama lists "gemma3:4b" but also accepts "gemma3" (= ":latest"); compare loosely.
        missing = {w for w in wanted if w not in served and f"{w}:latest" not in served}
        if missing:
            log.warning("model(s) not served: %s (served: %s)", missing, sorted(served))
        if not self._available and not missing:
            log.info("language model available: %s", self.model)
        self._available = not missing
        return self._available

    def mark_unavailable(self) -> None:
        self._available = False
        self._last_probe = time.monotonic()

    # -- calls ----------------------------------------------------------------------------------

    def ask(
        self, system: str, user: str, *, schema: dict[str, Any], name: str, max_tokens: int
    ) -> dict[str, Any]:
        body = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": max_tokens,
            "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": name, "strict": True, "schema": schema},
            },
            **self.settings.llm_extra_body,
        }
        response = self._post("/v1/chat/completions", body)
        try:
            choice = response.json()["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise BadAnswer("truncated" if choice.get("finish_reason") == "length" else "not_finished")
            result = json.loads(choice["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError):
            raise BadAnswer("invalid_json") from None
        if not isinstance(result, dict):
            raise BadAnswer("invalid_json")
        return result

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embedding_model:
            raise Unavailable("no embedding model configured")
        response = self._post("/v1/embeddings", {"model": self.embedding_model, "input": texts})
        try:
            data = sorted(response.json()["data"], key=lambda d: d["index"])
            return [d["embedding"] for d in data]
        except (ValueError, KeyError, TypeError):
            raise BadAnswer("invalid_embedding") from None

    def _post(self, path: str, body: dict[str, Any]) -> httpx.Response:
        try:
            response = self.http.post(path, json=body)
        except httpx.TransportError as exc:
            self.mark_unavailable()
            raise Unavailable(type(exc).__name__) from None
        if response.status_code in (429, 502, 503, 504):
            self.mark_unavailable()
            raise Unavailable(f"HTTP {response.status_code}")
        if response.status_code != 200:
            raise BadAnswer(f"http_{response.status_code}")
        return response
