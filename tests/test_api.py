"""REST API (/api/v1) against a real database."""

import pytest
from factories import add_article, add_reader, add_source
from fastapi.testclient import TestClient

from eilkurier import app as app_module
from eilkurier.app import create_app
from eilkurier.settings import get_settings


@pytest.fixture
def client(engine, clean_db, monkeypatch) -> TestClient:
    monkeypatch.setattr(app_module, "make_client", lambda settings: _offline())
    return TestClient(create_app())


def _offline():
    import httpx

    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))


def test_health(client) -> None:
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ok"}


def test_openapi_is_published(client) -> None:
    paths = client.get("/api/v1/openapi.json").json()["paths"]
    assert {"/api/v1/readers", "/api/v1/sources", "/api/v1/editions/{edition_id}/pdf"} <= set(paths)


def test_reader_lifecycle(client) -> None:
    created = client.post(
        "/api/v1/readers",
        json={"name": "Oma", "theme": "grossdruck", "delivery_time": "07:30", "delivery_days": [6, 7]},
    )
    assert created.status_code == 201
    reader = created.json()
    assert reader["theme"] == "grossdruck" and reader["delivery_time"] == "07:30:00"
    assert len(reader["telegram_link_code"]) == 6 and not reader["telegram_linked"]

    rid = reader["id"]
    updated = client.put(
        f"/api/v1/readers/{rid}", json={**reader, "font_scale": 1.3, "channel": "email", "email": "o@x.de"}
    )
    assert updated.json()["font_scale"] == 1.3

    interests = client.put(
        f"/api/v1/readers/{rid}/interests",
        json=[{"term": "Garten", "weight": 2}, {"term": "Fußball", "weight": -1}],
    )
    assert [i["term"] for i in interests.json()["interests"]] == ["Garten", "Fußball"]

    source = client.post(
        "/api/v1/sources",
        json={"name": "Tagesschau", "url": "https://www.tagesschau.de/x.xml", "category": "Nachrichten"},
    ).json()
    assert client.put(f"/api/v1/readers/{rid}/sources", json=[source["id"]]).json()["source_ids"] == [
        source["id"]
    ]

    code = client.post(f"/api/v1/readers/{rid}/telegram-link").json()["telegram_link_code"]
    assert code and code != reader["telegram_link_code"]

    assert client.delete(f"/api/v1/readers/{rid}").status_code == 204
    assert client.get(f"/api/v1/readers/{rid}").status_code == 404


def test_reader_validation(client) -> None:
    assert client.post("/api/v1/readers", json={"name": ""}).status_code == 422
    assert client.post("/api/v1/readers", json={"name": "X", "theme": "comic"}).status_code == 422
    assert client.post("/api/v1/readers", json={"name": "X", "delivery_days": [8]}).status_code == 422
    assert client.post("/api/v1/readers", json={"name": "X", "email": "kein-mail"}).status_code == 422


def test_sources_and_catalog(client) -> None:
    catalog = client.get("/api/v1/catalog").json()
    assert len(catalog) > 50 and not any(e["added"] for e in catalog)
    entry = catalog[0]
    assert client.post("/api/v1/sources", json=entry | {"kind": "rss"}).status_code == 201
    assert client.post("/api/v1/sources", json=entry | {"kind": "rss"}).status_code == 409
    assert next(e for e in client.get("/api/v1/catalog").json() if e["url"] == entry["url"])["added"]
    sources = client.get("/api/v1/sources").json()
    assert sources[0]["article_count"] == 0
    assert client.delete(f"/api/v1/sources/{sources[0]['id']}").status_code == 204


def test_build_edition_now_and_download(client, scope) -> None:
    with scope() as s:
        source = add_source(s)
        reader = add_reader(s, [source], name="Papa")
        add_article(s, source, "Brücke öffnet")
        rid = reader.id
    summary = client.post(f"/api/v1/readers/{rid}/editions").json()
    assert summary["number"] == 1 and summary["lead_headline"] == "Brücke öffnet"
    assert summary["delivery_status"] == "pending"

    again = client.post(f"/api/v1/readers/{rid}/editions").json()
    assert again["id"] == summary["id"]  # rebuilt, not duplicated
    assert again["lead_headline"] == "Brücke öffnet"  # and its own articles are still eligible

    listing = client.get("/api/v1/editions", params={"reader_id": rid}).json()
    assert [e["id"] for e in listing] == [summary["id"]]
    detail = client.get(f"/api/v1/editions/{summary['id']}").json()
    assert detail["payload"]["edition"]["reader"] == "Papa"
    pdf = client.get(f"/api/v1/editions/{summary['id']}/pdf")
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")


def test_letters(client) -> None:
    letter = client.post("/api/v1/letters", json={"author": "Mama", "text": "Sonntag Kuchen!"}).json()
    assert letter["via"] == "web"
    assert [x["text"] for x in client.get("/api/v1/letters").json()] == ["Sonntag Kuchen!"]
    assert client.delete(f"/api/v1/letters/{letter['id']}").status_code == 204
    assert client.get("/api/v1/letters").json() == []


def test_status_without_language_model(client) -> None:
    status = client.get("/api/v1/status").json()
    assert status["language_model"]["configured"] is False
    assert status["counts"]["articles_total"] == 0


@pytest.mark.parametrize("theme", ["klassisch", "feuilleton", "grossdruck"])
def test_sample_edition_pdf(client, theme) -> None:
    response = client.get("/api/v1/samples/edition.pdf", params={"theme": theme})
    assert response.status_code == 200 and response.content.startswith(b"%PDF")


def test_household_pin(engine, clean_db, monkeypatch) -> None:
    monkeypatch.setenv("EILKURIER_HOUSEHOLD_PIN", "4711")
    get_settings.cache_clear()
    client = TestClient(create_app())
    assert client.get("/api/v1/session").json() == {"pin_required": True, "authenticated": False}
    assert client.get("/api/v1/readers").status_code == 401
    assert client.post("/api/v1/session", json={"pin": "0000"}).status_code == 401
    assert client.post("/api/v1/session", json={"pin": "4711"}).json()["authenticated"] is True
    assert client.get("/api/v1/readers").status_code == 200
    client.delete("/api/v1/session")
    assert client.get("/api/v1/readers").status_code == 401
    assert client.get("/health/live").status_code == 200  # probes never need the PIN


def test_web_ui_client_matches_api() -> None:
    """frontend/openapi.json (source of the typed client) must match the API. Fix: see message."""
    import json
    from pathlib import Path

    committed = json.loads((Path(__file__).parents[1] / "frontend" / "openapi.json").read_text("utf-8"))
    assert committed == create_app().openapi(), (
        "API changed: run `uv run eilkurier openapi > frontend/openapi.json && (cd frontend && npm run api)`"
    )
