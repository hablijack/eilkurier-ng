"""Test setup. Database tests need a disposable Postgres with pgvector:

    docker run -d --name ek-pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_USER=test -e POSTGRES_DB=test \\
        -p 55432:5432 pgvector/pgvector:pg17
    export EILKURIER_TEST_DATABASE_URL=postgresql+psycopg://test:test@localhost:55432/test

The schema is dropped and rebuilt through the real migrations at the start of the session.
"""

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

TEST_DB = os.environ.get("EILKURIER_TEST_DATABASE_URL", "")
os.environ["EILKURIER_DATABASE_URL"] = TEST_DB or "postgresql+psycopg://invalid/none"
os.environ["EILKURIER_LLM_URL"] = ""
os.environ["EILKURIER_HOUSEHOLD_PIN"] = ""

from eilkurier.db import Base, get_engine, session_factory  # noqa: E402
from eilkurier.settings import Settings, get_settings  # noqa: E402
from eilkurier.simulator import create_app as create_simulator  # noqa: E402

needs_db = pytest.mark.skipif(not TEST_DB, reason="set EILKURIER_TEST_DATABASE_URL to run database tests")


@pytest.fixture(scope="session")
def engine():
    if not TEST_DB:
        pytest.skip("set EILKURIER_TEST_DATABASE_URL to run database tests")
    from eilkurier.migrate import upgrade

    eng = get_engine(TEST_DB)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    upgrade(TEST_DB)
    return eng


@pytest.fixture
def clean_db(engine) -> Iterator[None]:
    yield
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def session(engine, clean_db) -> Iterator[Session]:
    s = session_factory(engine)()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def scope(engine, clean_db) -> Callable:
    """Drop-in for db.session_scope bound to the test database."""

    @contextmanager
    def _scope():
        s = session_factory(engine)()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    return _scope


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=TEST_DB or "postgresql+psycopg://invalid/none",
        llm_url="http://simulator",
        llm_model="gemma3:4b",
        embedding_model="embeddinggemma",
        location_name="Weiden",
        llm_probe_interval_seconds=0,
    )


@pytest.fixture
def simulator_http() -> TestClient:
    return TestClient(create_simulator(), base_url="http://simulator")


class Web:
    """A fake internet for httpx: register URL -> (status, body, headers); everything else is 404."""

    def __init__(self) -> None:
        self.routes: dict[str, tuple[int, Any, dict[str, str]]] = {}
        self.requests: list[httpx.Request] = []

    def add(
        self,
        url: str,
        body: bytes | str | Callable[[httpx.Request], httpx.Response],
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        """`body` may be a function of the request, for pages that answer depending on cookies."""
        self.routes[url] = (status, body, headers or {})

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = str(request.url).split("?")[0]
        for url, (status, body, headers) in self.routes.items():
            if key == url or str(request.url) == url or (url.endswith("*") and key.startswith(url[:-1])):
                if callable(body):
                    return body(request)
                content = body.encode() if isinstance(body, str) else body
                return httpx.Response(status, content=content, headers=headers)
        return httpx.Response(404)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler), follow_redirects=True)


@pytest.fixture
def web() -> Web:
    return Web()


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
