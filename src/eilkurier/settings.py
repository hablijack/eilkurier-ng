from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    # src/eilkurier/settings.py -> repository root (only valid for a source checkout;
    # the container sets EILKURIER_RESOURCE_ROOT explicitly).
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration, read from EILKURIER_* environment variables (12-factor)."""

    model_config = SettingsConfigDict(env_prefix="EILKURIER_", extra="ignore")

    # Directory that contains `layout/` (Typst templates) and `assets/` (fonts, logo).
    resource_root: Path = _repo_root()


@lru_cache
def get_settings() -> Settings:
    return Settings()
