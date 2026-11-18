"""Typesetting of an edition (JSON document) into a PDF via the Typst templates in `layout/`."""

import json
import logging
from enum import StrEnum
from pathlib import Path
from typing import Any

import typst

from eilkurier.images import grayscale

Edition = dict[str, Any]


log = logging.getLogger(__name__)


class Theme(StrEnum):
    KLASSISCH = "klassisch"
    FEUILLETON = "feuilleton"
    GROSSDRUCK = "grossdruck"
    EPAPER = "epaper"


class EditionRenderer:
    def __init__(self, resource_root: Path) -> None:
        self.root = resource_root
        self.main = resource_root / "layout" / "main.typ"
        self.fonts = resource_root / "assets" / "fonts"

    def render_pdf(self, edition: Edition, pictures: dict[int, bytes] | None = None) -> bytes:
        pdf, warnings = self.render_with_warnings(edition, pictures)
        for warning in warnings:
            log.warning("typesetting: %s", warning)
        return pdf

    def render_with_warnings(
        self, edition: Edition, pictures: dict[int, bytes] | None = None
    ) -> tuple[bytes, list[str]]:
        """`pictures`: JPEG bytes by image id, for the `image.id` references in the edition."""
        inputs = {"edition": json.dumps(edition, ensure_ascii=False)}
        if pictures:
            retro = edition.get("style", {}).get("theme") == Theme.KLASSISCH
            # Typst inputs are strings: bytes travel as JSON arrays (fast enough for a handful of JPEGs).
            inputs["images"] = json.dumps(
                {str(i): list(grayscale(data) if retro else data) for i, data in pictures.items()},
                separators=(",", ":"),
            )
        pdf, warnings = typst.compile_with_warnings(
            str(self.main),
            root=str(self.root),
            font_paths=[str(self.fonts)],
            sys_inputs=inputs,
            format="pdf",
            # Accessible, tagged PDF. Typst fails the build on violations (e.g. images without alt text).
            pdf_standards="ua-1",
        )
        return pdf, [str(getattr(w, "message", w)) for w in warnings]

    def sample_edition(self, theme: Theme = Theme.EPAPER) -> Edition:
        edition = json.loads((self.root / "layout" / "sample" / "edition.json").read_text("utf-8"))
        edition["style"]["theme"] = theme.value
        return edition
