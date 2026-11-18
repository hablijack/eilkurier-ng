import pytest

from eilkurier.render import EditionRenderer
from eilkurier.settings import get_settings


def renderer() -> EditionRenderer:
    return EditionRenderer(get_settings().resource_root)


def test_english_edition_renders() -> None:
    r = renderer()
    edition = r.sample_edition()
    edition["edition"]["lang"] = "en"
    assert r.render_pdf(edition).startswith(b"%PDF")


@pytest.mark.parametrize("theme", ["klassisch", "epaper"])
def test_edition_without_optional_sections_renders(theme) -> None:
    r = renderer()
    edition = r.sample_edition()
    edition["style"]["theme"] = theme
    for optional in ("lead", "weather", "briefs", "family", "almanac"):
        edition.pop(optional)
    assert r.render_pdf(edition).startswith(b"%PDF")


def test_pdf_metadata_names_reader() -> None:
    pdf = renderer().render_pdf(renderer().sample_edition())
    # Title is set via `set document(...)`; needed for accessible (tagged) PDFs.
    assert b"Christoph" in pdf


@pytest.mark.parametrize("theme", ["klassisch", "feuilleton", "grossdruck", "epaper"])
def test_long_edition_converges(theme) -> None:
    """Many stories over several pages: the balanced column flow must settle without Typst warnings."""
    r = renderer()
    edition = r.sample_edition()
    edition["style"]["theme"] = theme
    stories = edition["stories"]
    edition["stories"] = [
        {**stories[i % len(stories)], "headline": f"{stories[i % len(stories)]['headline']} {i}"}
        for i in range(14)
    ]
    pdf, warnings = r.render_with_warnings(edition)
    assert pdf.startswith(b"%PDF") and warnings == []
