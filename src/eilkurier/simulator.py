"""A stand-in for the language model server (OpenAI-compatible, like Ollama/vLLM).

It answers deterministically from the article text itself: extractive "summaries", keyword topics and
bag-of-words embeddings. Good enough to develop, test and demo the whole pipeline without a GPU.
Run: `eilkurier simulator --port 11434`, then set EILKURIER_LLM_URL=http://localhost:11434.
"""

import hashlib
import json
import math
import re
import time
from collections import Counter
from typing import Any

from fastapi import FastAPI, HTTPException

from eilkurier.text import sentences, shorten

EMBEDDING_DIM = 256
_WORD = re.compile(r"[A-Za-zÄÖÜäöüß]{4,}")
_STOP = set(
    [
        "aber",
        "alle",
        "allem",
        "als",
        "also",
        "auch",
        "auf",
        "aus",
        "bei",
        "beim",
        "bereits",
        "bis",
        "dass",
        "dabei",
        "damit",
        "dann",
        "darauf",
        "das",
        "dem",
        "den",
        "denn",
        "der",
        "des",
        "die",
        "dies",
        "diese",
        "diesem",
        "dieser",
        "doch",
        "durch",
        "eine",
        "einem",
        "einen",
        "einer",
        "eines",
        "einige",
        "etwa",
        "für",
        "gegen",
        "gibt",
        "habe",
        "haben",
        "hatte",
        "hier",
        "ihre",
        "im",
        "immer",
        "ist",
        "jetzt",
        "kann",
        "kein",
        "keine",
        "mehr",
        "mit",
        "nach",
        "nicht",
        "noch",
        "nun",
        "oder",
        "ohne",
        "schon",
        "sein",
        "seine",
        "sich",
        "sie",
        "sind",
        "soll",
        "sollen",
        "sowie",
        "über",
        "um",
        "und",
        "uns",
        "unter",
        "vom",
        "von",
        "vor",
        "war",
        "waren",
        "was",
        "weil",
        "wenn",
        "werden",
        "wie",
        "wieder",
        "will",
        "wird",
        "wurde",
        "wurden",
        "zum",
        "zur",
        "zwei",
        "drei",
        "that",
        "with",
        "from",
        "this",
        "have",
        "have",
        "will",
        "would",
        "about",
        "their",
        "there",
        "were",
        "what",
        "when",
        "which",
        "into",
        "more",
        "than",
        "also",
        "been",
    ]
)


def _keywords(text: str, n: int) -> list[str]:
    words = [w.lower() for w in _WORD.findall(text)]
    counts = Counter(w for w in words if w not in _STOP)
    return [w for w, _ in counts.most_common(n)]


def embed(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    for word in _keywords(text, 40):
        bucket = int(hashlib.blake2b(word.encode(), digest_size=4).hexdigest(), 16) % EMBEDDING_DIM
        vector[bucket] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _field(user: str, label: str) -> str:
    match = re.search(rf"^{label}:\s*(.*)$", user, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _enrichment(user: str) -> dict[str, Any]:
    title = _field(user, "TITEL")
    text = user.split("TEXT:", 1)[-1].strip()
    first = sentences(text)[:1] or [title]
    words = title.split()
    # Long titles: keep the first clause ("A: B" -> "A") instead of cutting mid-phrase.
    headline = title if len(words) <= 12 else re.split(r":| – | - ", title, maxsplit=1)[0]
    return {
        "headline": headline.rstrip(" –-:,;") or "Meldung",
        "subhead": " ".join(first[0].split()[:12]),
        "summary": shorten(text, 450) or [title],
        "event": first[0],
        "topics": _keywords(f"{title} {title} {text}", 4),
        "importance": 3,
    }


def _story(user: str) -> dict[str, Any]:
    item = user.split("LAUFENDE GESCHICHTEN:", 1)[0]
    item_words = set(_keywords(item, 15))
    best, best_overlap = 0, 0.0
    for line in user.split("LAUFENDE GESCHICHTEN:", 1)[-1].strip().splitlines():
        number, _, rest = line.partition(".")
        overlap_words = item_words & set(_keywords(rest, 15))
        overlap = len(overlap_words) / (len(item_words) or 1)
        if number.strip().isdigit() and overlap > best_overlap:
            best, best_overlap = int(number), overlap
    return {"story": best if best_overlap >= 0.4 else 0}


def create_app(models: list[str] | None = None) -> FastAPI:
    served = models or ["gemma3:4b", "embeddinggemma", "qwen3.8"]
    app = FastAPI(title="Eilkurier LLM simulator")

    @app.get("/v1/models")
    def list_models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [{"id": m, "object": "model", "owned_by": "simulator"} for m in served],
        }

    @app.post("/v1/chat/completions")
    def chat(body: dict[str, Any]) -> dict[str, Any]:
        if body.get("model") not in served:
            raise HTTPException(404, "model not found")
        user = next((m["content"] for m in body["messages"] if m["role"] == "user"), "")
        name = body.get("response_format", {}).get("json_schema", {}).get("name")
        answer = _story(user) if name == "story" else _enrichment(user)
        return {
            "id": f"sim-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "model": body["model"],
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)},
                }
            ],
        }

    @app.post("/v1/embeddings")
    def embeddings(body: dict[str, Any]) -> dict[str, Any]:
        inputs = body["input"] if isinstance(body["input"], list) else [body["input"]]
        return {
            "object": "list",
            "model": body.get("model"),
            "data": [
                {"object": "embedding", "index": i, "embedding": embed(t)} for i, t in enumerate(inputs)
            ],
        }

    return app
