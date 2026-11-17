"""Typesetting of an edition (JSON document) into a PDF via the Typst templates in `layout/`."""

import json
import logging
from enum import StrEnum
from pathlib import Path
from typing import Any

import typst

Edition = dict[str, Any]


log = logging.getLogger(__name__)


class Theme(StrEnum):
    KLASSISCH = "klassisch"
    FEUILLETON = "feuilleton"
    GROSSDRUCK = "grossdruck"


class EditionRenderer:
    def __init__(self, resource_root: Path) -> None:
        self.root = resource_root
        self.main = resource_root / "layout" / "main.typ"
        self.fonts = resource_root / "assets" / "fonts"

    def render_pdf(self, edition: Edition) -> bytes:
        pdf, warnings = self.render_with_warnings(edition)
        for warning in warnings:
            log.warning("typesetting: %s", warning)
        return pdf

    def render_with_warnings(self, edition: Edition) -> tuple[bytes, list[str]]:
        pdf, warnings = typst.compile_with_warnings(
            str(self.main),
            root=str(self.root),
            font_paths=[str(self.fonts)],
            sys_inputs={"edition": json.dumps(edition, ensure_ascii=False)},
            format="pdf",
            # Accessible, tagged PDF. Typst fails the build on violations (e.g. images without alt text).
            pdf_standards="ua-1",
        )
        return pdf, [str(getattr(w, "message", w)) for w in warnings]

    def sample_edition(self, theme: Theme = Theme.KLASSISCH) -> Edition:
        edition = json.loads((self.root / "layout" / "sample" / "edition.json").read_text("utf-8"))
        edition["style"]["theme"] = theme.value
        return edition
