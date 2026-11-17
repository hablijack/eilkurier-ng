import pytest
from fastapi.testclient import TestClient

from eilkurier.app import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ok"}


def test_openapi_is_published(client: TestClient) -> None:
    spec = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/samples/edition.pdf" in spec["paths"]


@pytest.mark.parametrize("theme", ["klassisch", "feuilleton", "grossdruck"])
def test_sample_edition_pdf(client: TestClient, theme: str) -> None:
    response = client.get("/api/v1/samples/edition.pdf", params={"theme": theme})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_unknown_theme_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/samples/edition.pdf", params={"theme": "comic"}).status_code == 422
