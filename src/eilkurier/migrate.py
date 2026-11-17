"""Programmatic Alembic: `eilkurier migrate` runs as a one-shot container before app and worker start."""

from pathlib import Path

from alembic import command
from alembic.config import Config


def alembic_config(url: str | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    if url:
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def upgrade(url: str | None = None) -> None:
    command.upgrade(alembic_config(url), "head")


def revision(message: str, url: str | None = None) -> None:
    command.revision(alembic_config(url), message=message, autogenerate=True)
