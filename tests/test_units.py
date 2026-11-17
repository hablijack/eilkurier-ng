"""Unit tests without a database."""

from datetime import date

import httpx
import pytest
from factories import PARAGRAPH, article_page

from eilkurier import almanac
from eilkurier.collect import extract_fulltext
from eilkurier.edition import date_label
from eilkurier.llm import LLM, BadAnswer, Unavailable
from eilkurier.reporter import ENRICH_SCHEMA, validate_enrichment
from eilkurier.text import looks_scrambled, sentences, shorten, strip_html

# --- text ---------------------------------------------------------------------------------------


def test_sentences_keep_german_abbreviations() -> None:
    assert sentences("Es gibt z. B. Äpfel. Und Nr. 5 ist da! Fertig?") == [
        "Es gibt z. B. Äpfel.",
        "Und Nr. 5 ist da!",
        "Fertig?",
    ]


def test_shorten_cuts_at_sentence_boundary() -> None:
    result = shorten("Erster Satz hier. Zweiter Satz folgt. Dritter Satz ist lang.", 40)
    assert result == ["Erster Satz hier. Zweiter Satz folgt."]


def test_shorten_always_returns_at_least_one_sentence() -> None:
    assert shorten("Ein sehr langer einziger Satz ohne Ende in Sicht.", 10) == [
        "Ein sehr langer einziger Satz ohne Ende in Sicht."
    ]


def test_strip_html() -> None:
    assert strip_html("<p>Hallo&nbsp;<b>Welt</b> &amp; mehr</p>") == "Hallo\xa0 Welt & mehr"


def test_date_label() -> None:
    assert date_label(date(2026, 11, 17), "de") == "Dienstag, 17. November 2026"
    assert date_label(date(2026, 11, 17), "en") == "Tuesday, November 17, 2026"


# --- full text extraction ---------------------------------------------------------------------


def test_extracts_article_text() -> None:
    text = extract_fulltext(article_page("Brücke öffnet"), "https://example.org/a")
    assert text is not None and "Mühlbach" in text and "Impressum" not in text


def test_rejects_consent_wall() -> None:
    wall = (
        "<html><body><article><p>Besuchen Sie uns wie gewohnt mit Werbung und Tracking, indem Sie der "
        "Nutzung aller Cookies zustimmen. Details zum Tracking finden Sie im Privacy Center. "
        + "Oder lesen Sie werbefrei mit einem Pur-Abo. " * 6
        + "</p></article></body></html>"
    )
    assert extract_fulltext(wall) is None


def test_detects_scrambled_paywall_text() -> None:
    scrambled = (
        "Aciq jqc 8500 icjc Mqlcjiclqäiic ljc 2032: Ajic icjc Aijqjc qcq Djiqcqcxjcccq ji Yjqqcljq icjci. "
        * 5
    )
    assert looks_scrambled(scrambled)
    assert not looks_scrambled(PARAGRAPH * 2)
    assert extract_fulltext(f"<html><body><article><p>{scrambled}</p></article></body></html>") is None


def test_rejects_teaser_page() -> None:
    assert extract_fulltext("<html><body><article><p>Nur ein Satz.</p></article></body></html>") is None


# --- enrichment validation --------------------------------------------------------------------


def _answer(**overrides):
    base = {
        "headline": "Brücke öffnet früher",
        "subhead": "Sanierung beendet",
        "summary": ["Die Sanierung kostete 2,3 Millionen Euro."],
        "event": "Die Brücke wird am Freitag freigegeben.",
        "topics": ["Brücke", "#Verkehr", "brücke"],
        "importance": 9,
    }
    return base | overrides


def test_validate_enrichment_normalises() -> None:
    result = validate_enrichment(_answer(), PARAGRAPH)
    assert result["topics"] == ["brücke", "verkehr"]
    assert result["importance"] == 5


def test_validate_enrichment_rejects_invented_numbers() -> None:
    with pytest.raises(BadAnswer, match="unsupported_numbers:47"):
        validate_enrichment(_answer(summary=["Es kamen 47 Gäste."]), PARAGRAPH)


def test_validate_enrichment_ignores_names_with_digits() -> None:
    answer = _answer(summary=["Weniger CO2 dank 5G-Steuerung und MP3-Ansagen."])
    assert validate_enrichment(answer, PARAGRAPH)["summary"]
    with pytest.raises(BadAnswer, match="unsupported_numbers:5"):
        validate_enrichment(_answer(summary=["Es gibt 5 neue Ladesäulen mit CO2-Bilanz."]), PARAGRAPH)


def test_validate_enrichment_rejects_incomplete() -> None:
    with pytest.raises(BadAnswer):
        validate_enrichment(_answer(summary=[]), PARAGRAPH)


def test_enrich_schema_is_strict() -> None:
    assert ENRICH_SCHEMA["additionalProperties"] is False
    assert set(ENRICH_SCHEMA["required"]) == set(ENRICH_SCHEMA["properties"])


# --- language model client ----------------------------------------------------------------------


def _llm(settings, handler) -> LLM:
    http = httpx.Client(base_url="http://llm", transport=httpx.MockTransport(handler))
    return LLM(settings, http)


def test_llm_against_simulator(settings, simulator_http) -> None:
    llm = LLM(settings, simulator_http)
    assert llm.available()
    answer = llm.ask(
        "system",
        f"TITEL: Brücke\nQUELLE: Test\n\nTEXT:\n{PARAGRAPH}",
        schema=ENRICH_SCHEMA,
        name="e",
        max_tokens=9,
    )
    assert validate_enrichment(answer, "Brücke " + PARAGRAPH)["event"]
    vectors = llm.embed(["Brücke Sanierung", "Brücke Sanierung", "Fußball Bundesliga"])
    assert vectors[0] == vectors[1] != vectors[2]


def test_llm_overloaded_is_unavailable(settings) -> None:
    llm = _llm(settings, lambda r: httpx.Response(503))
    with pytest.raises(Unavailable):
        llm.ask("s", "u", schema={}, name="n", max_tokens=1)


def test_llm_transport_error_is_unavailable(settings) -> None:
    def boom(request):
        raise httpx.ConnectError("down")

    llm = _llm(settings, boom)
    assert llm.available() is False
    with pytest.raises(Unavailable):
        llm.embed(["x"])


def test_llm_truncated_answer_is_bad(settings) -> None:
    body = {"choices": [{"finish_reason": "length", "message": {"content": "{"}}]}
    llm = _llm(settings, lambda r: httpx.Response(200, json=body))
    with pytest.raises(BadAnswer, match="truncated"):
        llm.ask("s", "u", schema={}, name="n", max_tokens=1)


def test_llm_reports_missing_model(settings) -> None:
    llm = _llm(settings, lambda r: httpx.Response(200, json={"data": [{"id": "other"}]}))
    assert llm.available() is False


def test_llm_accepts_ollama_latest_suffix(settings) -> None:
    settings.llm_model = "gemma3"
    settings.embedding_model = ""
    llm = _llm(settings, lambda r: httpx.Response(200, json={"data": [{"id": "gemma3:latest"}]}))
    assert llm.available() is True


# --- almanac ------------------------------------------------------------------------------------


def test_summarize_weather() -> None:
    hours = [
        {
            "timestamp": f"2026-11-17T{h:02d}:00:00+01:00",
            "temperature": 3 + h / 3,
            "wind_speed": 12,
            "wind_direction": 225,
            "icon": "cloudy",
            "condition": "rain" if h > 15 else "dry",
        }
        for h in range(24)
    ]
    w = almanac.summarize_weather(hours, "Weiden", "de")
    assert w == {
        "place": "Weiden",
        "summary": "Bedeckt, später Regen",
        "temp_min": 5,
        "temp_max": 10,
        "wind": "Wind 12 km/h aus SW",
    }


def test_almanac_without_network(settings) -> None:
    entries = almanac.almanac(None, settings, date(2026, 11, 17), "de")
    assert entries["Sonne"].endswith("Uhr")
    assert entries["Mond"] in {"Neumond", "zunehmend", "Vollmond", "abnehmend"}


def test_on_this_day_prefers_round_anniversary() -> None:
    events = {"selected": [{"year": 2003, "text": "B"}, {"year": 1926, "text": "A"}]}
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=events)))
    assert almanac.on_this_day(http, date(2026, 11, 17), "de") == (1926, "A")
