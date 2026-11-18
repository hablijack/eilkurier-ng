import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.sessions import SessionMiddleware

from eilkurier import __version__
from eilkurier.catalog import load_catalog, source_fields
from eilkurier.db import (
    Article,
    Edition,
    Interest,
    Letter,
    Reader,
    ReaderSource,
    Source,
    Status,
    Story,
    session_factory,
)
from eilkurier.deliver import deliver, new_link_code
from eilkurier.edition import build_edition
from eilkurier.http import make_client
from eilkurier.llm import LLM, BadAnswer, Unavailable
from eilkurier.render import EditionRenderer, Theme
from eilkurier.schemas import (
    Catalog,
    CatalogEntry,
    CatalogTopic,
    EditionOut,
    EditionSummary,
    InterestIO,
    LanguageModelStatus,
    LetterIn,
    LetterOut,
    PipelineCounts,
    ReaderIn,
    ReaderOut,
    SessionIn,
    SessionOut,
    SourceIn,
    SourceOut,
    StatusOut,
)
from eilkurier.settings import Settings, get_settings

API_PREFIX = "/api/v1"

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_session() -> Iterator[Session]:
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]


def get_renderer(settings: SettingsDep) -> EditionRenderer:
    return EditionRenderer(settings.resource_root)


@lru_cache
def get_llm() -> LLM | None:
    settings = get_settings()
    return LLM(settings) if settings.llm_enabled else None


def require_auth(request: Request, settings: SettingsDep) -> None:
    if settings.household_pin and not request.session.get("auth"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "PIN required")


# ---------------------------------------------------------------------------------------------
# mapping helpers
# ---------------------------------------------------------------------------------------------


def reader_out(reader: Reader) -> ReaderOut:
    return ReaderOut(
        id=reader.id,
        name=reader.name,
        language=reader.language,  # type: ignore[arg-type]
        theme=Theme(reader.theme),
        paper=reader.paper,  # type: ignore[arg-type]
        font_scale=reader.font_scale,
        paper_tint=reader.paper_tint,
        story_count=reader.story_count,
        channel=reader.channel,  # type: ignore[arg-type]
        email=reader.email,
        delivery_time=reader.delivery_time,
        delivery_days=reader.delivery_days,
        active=reader.active,
        telegram_linked=reader.telegram_chat_id is not None,
        telegram_link_code=reader.telegram_link_code,
        interests=[InterestIO.model_validate(i) for i in reader.interests],
        source_ids=[s.id for s in reader.sources],
    )


def edition_summary(edition: Edition) -> EditionSummary:
    payload = edition.payload or {}
    return EditionSummary(
        id=edition.id,
        reader_id=edition.reader_id,
        number=edition.number,
        issue_date=edition.issue_date,
        lead_headline=(payload.get("lead") or {}).get("headline"),
        story_count=len(payload.get("meta", {}).get("article_ids", [])),
        edited_count=payload.get("meta", {}).get("edited", 0),
        delivery_status=edition.delivery_status,
        delivery_error=edition.delivery_error,
        delivered_at=edition.delivered_at,
    )


def load_reader(session: Session, reader_id: int) -> Reader:
    reader = session.scalar(
        select(Reader)
        .options(selectinload(Reader.interests), selectinload(Reader.sources))
        .where(Reader.id == reader_id)
    )
    if reader is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "reader not found")
    return reader


# ---------------------------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------------------------

public = APIRouter(prefix=API_PREFIX)
api = APIRouter(prefix=API_PREFIX, dependencies=[Depends(require_auth)])


@public.get("/session", tags=["session"])
def get_session_state(request: Request, settings: SettingsDep) -> SessionOut:
    required = bool(settings.household_pin)
    return SessionOut(pin_required=required, authenticated=not required or bool(request.session.get("auth")))


@public.post("/session", tags=["session"])
def login(body: SessionIn, request: Request, settings: SettingsDep) -> SessionOut:
    if settings.household_pin and not secrets.compare_digest(body.pin, settings.household_pin):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong PIN")
    request.session["auth"] = True
    return SessionOut(pin_required=bool(settings.household_pin), authenticated=True)


@public.delete("/session", tags=["session"], status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> None:
    request.session.clear()


# --- readers ----------------------------------------------------------------------------------


@api.get("/readers", tags=["readers"])
def list_readers(session: SessionDep) -> list[ReaderOut]:
    readers = session.scalars(
        select(Reader)
        .options(selectinload(Reader.interests), selectinload(Reader.sources))
        .order_by(Reader.id)
    ).all()
    return [reader_out(r) for r in readers]


@api.post("/readers", tags=["readers"], status_code=status.HTTP_201_CREATED)
def create_reader(body: ReaderIn, session: SessionDep) -> ReaderOut:
    reader = Reader(**body.model_dump(mode="python"), telegram_link_code=new_link_code())
    reader.theme = body.theme.value
    session.add(reader)
    session.flush()
    return reader_out(load_reader(session, reader.id))


@api.get("/readers/{reader_id}", tags=["readers"])
def get_reader(reader_id: int, session: SessionDep) -> ReaderOut:
    return reader_out(load_reader(session, reader_id))


@api.put("/readers/{reader_id}", tags=["readers"])
def update_reader(reader_id: int, body: ReaderIn, session: SessionDep) -> ReaderOut:
    reader = load_reader(session, reader_id)
    for key, value in body.model_dump(mode="python").items():
        setattr(reader, key, value)
    reader.theme = body.theme.value
    return reader_out(reader)


@api.delete("/readers/{reader_id}", tags=["readers"], status_code=status.HTTP_204_NO_CONTENT)
def delete_reader(reader_id: int, session: SessionDep) -> None:
    session.delete(load_reader(session, reader_id))


@api.post("/readers/{reader_id}/telegram-link", tags=["readers"])
def renew_telegram_link(reader_id: int, session: SessionDep) -> ReaderOut:
    """New link code; the reader sends it to the bot. Also unlinks a previously linked chat."""
    reader = load_reader(session, reader_id)
    reader.telegram_link_code = new_link_code()
    reader.telegram_chat_id = None
    return reader_out(reader)


@api.put("/readers/{reader_id}/interests", tags=["readers"])
def replace_interests(
    reader_id: int, body: list[InterestIO], session: SessionDep, settings: SettingsDep
) -> ReaderOut:
    reader = load_reader(session, reader_id)
    reader.interests.clear()
    session.flush()
    for item in body:
        reader.interests.append(Interest(term=item.term.strip(), weight=item.weight))
    llm = get_llm()
    if llm and settings.embedding_model and reader.interests:
        try:
            vectors = llm.embed([i.term for i in reader.interests])
            for interest, vector in zip(reader.interests, vectors, strict=True):
                interest.embedding = vector
        except (Unavailable, BadAnswer):
            pass  # the worker fills missing embeddings later
    return reader_out(reader)


@api.put("/readers/{reader_id}/sources", tags=["readers"])
def replace_reader_sources(reader_id: int, body: list[int], session: SessionDep) -> ReaderOut:
    """Set the reader's sources, most important first (the order weighs in article selection)."""
    load_reader(session, reader_id)
    known = set(session.scalars(select(Source.id).where(Source.id.in_(body))))
    ordered = list(dict.fromkeys(i for i in body if i in known))
    session.query(ReaderSource).filter(ReaderSource.reader_id == reader_id).delete()
    session.add_all(
        ReaderSource(reader_id=reader_id, source_id=sid, position=pos) for pos, sid in enumerate(ordered)
    )
    session.flush()
    session.expire_all()
    return reader_out(load_reader(session, reader_id))


# --- sources ----------------------------------------------------------------------------------


def _source_out(source: Source, count: int) -> SourceOut:
    out = SourceOut.model_validate(source)
    out.article_count = count
    return out


@api.get("/sources", tags=["sources"])
def list_sources(session: SessionDep) -> list[SourceOut]:
    counts = dict(session.execute(select(Article.source_id, func.count()).group_by(Article.source_id)).all())
    return [
        _source_out(s, counts.get(s.id, 0))
        for s in session.scalars(select(Source).order_by(Source.category, Source.name))
    ]


@api.post("/sources", tags=["sources"], status_code=status.HTTP_201_CREATED)
def create_source(body: SourceIn, session: SessionDep) -> SourceOut:
    source = Source(**body.model_dump(mode="json"))
    session.add(source)
    try:
        session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "source already exists") from None
    return _source_out(source, 0)


@api.put("/sources/{source_id}", tags=["sources"])
def update_source(source_id: int, body: SourceIn, session: SessionDep) -> SourceOut:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "source not found")
    for key, value in body.model_dump(mode="json").items():
        setattr(source, key, value)
    source.last_fetched_at = None  # fetch again soon
    return _source_out(source, 0)


@api.delete("/sources/{source_id}", tags=["sources"], status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: int, session: SessionDep) -> None:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "source not found")
    session.delete(source)


@api.get("/catalog", tags=["sources"])
def source_catalog(session: SessionDep) -> Catalog:
    """Topics and suggested feeds for the wizard (the classic Eilkurier list, checked 2026-11)."""
    existing = dict(session.execute(select(Source.url, Source.id)).all())
    catalog = load_catalog()
    return Catalog(
        topics=[CatalogTopic(**t) for t in catalog["topics"]],
        sources=[CatalogEntry(**e, source_id=existing.get(e["url"])) for e in catalog["sources"]],
    )


@api.post("/catalog/sources", tags=["sources"])
def adopt_catalog_sources(body: list[str], session: SessionDep) -> list[SourceOut]:
    """Make sure the catalog entries with these URLs exist as sources; returns them in request order."""
    entries = {e["url"]: e for e in load_catalog()["sources"]}
    unknown = [url for url in body if url not in entries]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"not in catalog: {unknown[0]}")
    existing = {s.url: s for s in session.scalars(select(Source).where(Source.url.in_(body)))}
    for url in dict.fromkeys(body):
        if url not in existing:
            existing[url] = Source(**source_fields(entries[url]))
            session.add(existing[url])
    session.flush()
    return [_source_out(existing[url], 0) for url in dict.fromkeys(body)]


# --- editions ---------------------------------------------------------------------------------


@api.get("/editions", tags=["editions"])
def list_editions(session: SessionDep, reader_id: int | None = None, limit: int = 30) -> list[EditionSummary]:
    query = select(Edition).order_by(Edition.issue_date.desc(), Edition.id.desc()).limit(min(limit, 200))
    if reader_id is not None:
        query = query.where(Edition.reader_id == reader_id)
    return [edition_summary(e) for e in session.scalars(query)]


@api.get("/editions/{edition_id}", tags=["editions"])
def get_edition(edition_id: int, session: SessionDep) -> EditionOut:
    edition = session.get(Edition, edition_id)
    if edition is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "edition not found")
    return EditionOut(**edition_summary(edition).model_dump(), payload=edition.payload)


@api.get(
    "/editions/{edition_id}/pdf",
    tags=["editions"],
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The typeset edition"}},
)
def edition_pdf(edition_id: int, session: SessionDep) -> Response:
    edition = session.get(Edition, edition_id)
    if edition is None or edition.pdf is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "edition not found")
    return Response(
        edition.pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="eilkurier-{edition.issue_date}.pdf"'},
    )


@api.post("/readers/{reader_id}/editions", tags=["editions"], status_code=status.HTTP_201_CREATED)
def create_edition_now(
    reader_id: int,
    session: SessionDep,
    settings: SettingsDep,
    renderer: Annotated[EditionRenderer, Depends(get_renderer)],
    send: bool = False,
) -> EditionSummary:
    """Build (or rebuild) today's edition for this reader right now; optionally deliver it."""
    reader = load_reader(session, reader_id)
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    with make_client(settings) as http:
        edition = build_edition(session, reader, settings, today, http, renderer)
        if send:
            edition.delivery_attempts = 0
            deliver(edition, settings, http)
    return edition_summary(edition)


# --- letters ----------------------------------------------------------------------------------


@api.get("/letters", tags=["letters"])
def list_letters(session: SessionDep) -> list[LetterOut]:
    since = datetime.now(UTC) - timedelta(days=30)
    letters = session.scalars(
        select(Letter).where(Letter.created_at >= since).order_by(Letter.created_at.desc())
    )
    return [LetterOut.model_validate(letter) for letter in letters]


@api.post("/letters", tags=["letters"], status_code=status.HTTP_201_CREATED)
def create_letter(body: LetterIn, session: SessionDep) -> LetterOut:
    letter = Letter(author=body.author.strip(), text=body.text.strip(), via="web")
    session.add(letter)
    session.flush()
    session.refresh(letter)
    return LetterOut.model_validate(letter)


@api.delete("/letters/{letter_id}", tags=["letters"], status_code=status.HTTP_204_NO_CONTENT)
def delete_letter(letter_id: int, session: SessionDep) -> None:
    letter = session.get(Letter, letter_id)
    if letter is not None:
        session.delete(letter)


# --- status & samples -------------------------------------------------------------------------


@api.get("/status", tags=["status"])
def system_status(session: SessionDep, settings: SettingsDep) -> StatusOut:
    llm = get_llm()

    def count(*where: Any) -> int:
        return session.scalar(select(func.count()).select_from(Article).where(*where)) or 0

    window = datetime.now(UTC) - timedelta(days=settings.story_window_days)
    return StatusOut(
        version=__version__,
        language_model=LanguageModelStatus(
            configured=settings.llm_enabled,
            available=bool(llm and llm.available()),
            url=settings.llm_url,
            model=settings.llm_model,
            embedding_model=settings.embedding_model,
        ),
        telegram=settings.telegram_enabled,
        email=settings.smtp_enabled,
        counts=PipelineCounts(
            articles_total=count(),
            fulltext_pending=count(Article.fulltext_status == Status.PENDING),
            enrichment_pending=count(Article.enrichment_status == Status.PENDING),
            enriched=count(Article.enrichment_status == Status.DONE),
            stories_open=session.scalar(
                select(func.count()).select_from(Story).where(Story.last_article_at >= window)
            )
            or 0,
        ),
        sources_with_errors=session.scalar(
            select(func.count()).select_from(Source).where(Source.last_error.is_not(None))
        )
        or 0,
    )


@public.get(
    "/samples/edition.pdf",
    tags=["samples"],
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "Sample edition as PDF"}},
)
def sample_edition_pdf(
    renderer: Annotated[EditionRenderer, Depends(get_renderer)],
    theme: Theme = Theme.KLASSISCH,
) -> Response:
    """Typesets the bundled sample edition in the given theme (layout preview)."""
    pdf = renderer.render_pdf(renderer.sample_edition(theme))
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="eilkurier-beispiel-{theme.value}.pdf"'},
    )


# ---------------------------------------------------------------------------------------------
# application
# ---------------------------------------------------------------------------------------------


def _mount_web(app: FastAPI, web_root: Path) -> None:
    """Serve the static SvelteKit build; unknown paths fall back to the SPA's index.html."""
    root = web_root.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str) -> FileResponse:
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Eilkurier API",
        version=__version__,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="eilkurier_session",
        max_age=60 * 60 * 24 * 180,
        same_site="lax",
        https_only=False,  # home network, plain HTTP
    )

    @app.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def ready(session: SessionDep) -> dict[str, str]:
        session.execute(select(1))
        return {"status": "ok"}

    app.include_router(public)
    app.include_router(api)
    if settings.web_root and (settings.web_root / "index.html").is_file():
        _mount_web(app, settings.web_root)
    return app
