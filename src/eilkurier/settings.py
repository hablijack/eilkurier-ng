from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    # src/eilkurier/settings.py -> repository root (only valid for a source checkout;
    # the container sets EILKURIER_RESOURCE_ROOT explicitly).
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration, read from EILKURIER_* environment variables (12-factor)."""

    model_config = SettingsConfigDict(env_prefix="EILKURIER_", extra="ignore")

    # --- resources & storage -------------------------------------------------------------------
    # Directory that contains `layout/` (Typst templates), `assets/` and `prompts/`.
    resource_root: Path = _repo_root()
    # Built web UI (SvelteKit static build). Served at "/" when the directory exists.
    web_root: Path | None = None
    database_url: str = "postgresql+psycopg://eilkurier:eilkurier@localhost:5432/eilkurier"

    # --- household -----------------------------------------------------------------------------
    timezone: str = "Europe/Berlin"
    language: str = "de"  # language of the written articles
    location_name: str = "Musterstadt"
    latitude: float = 49.45
    longitude: float = 11.86
    # Optional household PIN for the web UI (home network only). Empty = no login.
    household_pin: str = ""
    secret_key: str = Field(default="dev-only-change-me", min_length=8)

    # --- language model (OpenAI-compatible: Ollama on the Jetson, vLLM on captiva, or the simulator)
    llm_url: str = ""  # e.g. http://jetson.fritz.box:11434 ; empty = no LLM, editions are extractive
    llm_model: str = "gemma3:4b"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 300.0
    # Extra JSON merged into every chat request, e.g. {"chat_template_kwargs": {"enable_thinking": false}}
    llm_extra_body: dict[str, Any] = {}
    embedding_model: str = ""  # e.g. embeddinggemma ; empty = tag-based story matching
    # Minimum seconds between availability probes while the model is unreachable.
    llm_probe_interval_seconds: int = 60

    # --- pipeline ------------------------------------------------------------------------------
    fetch_interval_minutes: int = 30
    fulltext_batch: int = 20
    enrich_batch: int = 10
    article_retention_days: int = 60
    story_window_days: int = 14
    user_agent: str = "Eilkurier/1.0 (private family newspaper; +https://github.com/hablijack/eilkurier-ng)"

    # --- delivery ------------------------------------------------------------------------------
    telegram_bot_token: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Eilkurier <eilkurier@localhost>"
    smtp_starttls: bool = True

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_url)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host)


@lru_cache
def get_settings() -> Settings:
    return Settings()
