from eilkurier.render import EditionRenderer
from eilkurier.settings import get_settings


def renderer() -> EditionRenderer:
    return EditionRenderer(get_settings().resource_root)


def test_english_edition_renders() -> None:
    r = renderer()
    edition = r.sample_edition()
    edition["edition"]["lang"] = "en"
    assert r.render_pdf(edition).startswith(b"%PDF")


def test_edition_without_optional_sections_renders() -> None:
    r = renderer()
    edition = r.sample_edition()
    for optional in ("lead", "weather", "briefs", "family", "almanac"):
        edition.pop(optional)
    assert r.render_pdf(edition).startswith(b"%PDF")


def test_pdf_metadata_names_reader() -> None:
    pdf = renderer().render_pdf(renderer().sample_edition())
    # Title is set via `set document(...)`; needed for accessible (tagged) PDFs.
    assert b"Christoph" in pdf
