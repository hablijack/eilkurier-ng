"""The curated source catalog (classic Eilkurier list): topics for the wizard and their feeds."""

import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache
def load_catalog() -> dict[str, list[dict[str, Any]]]:
    return json.loads(resources.files("eilkurier").joinpath("catalog.json").read_text("utf-8"))


def source_fields(entry: dict[str, Any]) -> dict[str, str]:
    """The columns a catalog entry becomes when it is added as a `Source`."""
    return {
        "name": entry["name"],
        "url": entry["url"],
        "category": entry["category"],
        "image_mode": entry.get("images", "auto"),
    }
