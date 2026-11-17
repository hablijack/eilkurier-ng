"""Editorial desk: select articles for one reader and compose the edition document (see layout/sample)."""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from eilkurier import almanac
from eilkurier.db import Article, CalendarEvent, Edition, Letter, Reader, ReaderSource, Status
from eilkurier.render import EditionRenderer
from eilkurier.reporter import _cosine
from eilkurier.settings import Settings
from eilkurier.text import sentences, shorten

log = logging.getLogger(__name__)

LOOKBACK_HOURS = 36
MAX_PER_SOURCE = 3
BRIEF_COUNT = 5
BACKGROUND_EVENTS = 4
TEXT_BUDGET = {"lead": 1200, "large": 700, "medium": 480, "small": 320}

_NAMES = {
    "de": {
        "weekdays": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
        "months": [
            "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember",
        ],
        "slogan": "Nachrichten, wie Sie sein sollten",
        "region": "Das Internet",
        "since": "Seit 2018",
        "family": "Familie",
        "all_day": "ganztägig",
    },
    "en": {
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "months": [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ],
        "slogan": "News as it should be",
        "region": "The Internet",
        "since": "Since 2018",
        "family": "Family",
        "all_day": "all day",
    },
}  # fmt: skip


def names(lang: str) -> dict[str, Any]:
    return _NAMES.get(lang, _NAMES["de"])


def date_label(day: date, lang: str) -> str:
    n = names(lang)
    if lang == "en":
        return f"{n['weekdays'][day.weekday()]}, {n['months'][day.month - 1]} {day.day}, {day.year}"
    return f"{n['weekdays'][day.weekday()]}, {day.day}. {n['months'][day.month - 1]} {day.year}"


@dataclass
class Scored:
    article: Article
    score: float


def _matches(term: str, haystack: str) -> bool:
    return term.casefold() in haystack


def score_article(article: Article, reader: Reader, now: datetime) -> float:
    e = article.enrichment or {}
    haystack = " ".join(
        [
            article.title,
            article.teaser,
            e.get("headline", ""),
            " ".join(e.get("summary", [])),
            *e.get("topics", []),
        ]
    ).casefold()
    score = 0.0
    for interest in reader.interests:
        hit = 1.0 if _matches(interest.term, haystack) else 0.0
        if interest.embedding is not None and article.embedding is not None:
            hit = max(hit, (_cosine(list(interest.embedding), list(article.embedding)) - 0.3) * 2)
        score += interest.weight * max(0.0, hit)
    score += 0.5 * e.get("importance", 2)
    age_hours = (now - article.published_at).total_seconds() / 3600
    score += max(0.0, 1 - age_hours / LOOKBACK_HOURS)
    if article.fulltext_status == Status.DONE:
        score += 0.2
    return score


def select_articles(session: Session, reader: Reader, now: datetime) -> list[Scored]:
    printed: set[int] = set()
    for payload in session.scalars(
        select(Edition.payload)
        .where(Edition.reader_id == reader.id)
        .order_by(Edition.issue_date.desc())
        .limit(7)
    ):
        printed.update(payload.get("meta", {}).get("article_ids", []))
    source_ids = select(ReaderSource.source_id).where(ReaderSource.reader_id == reader.id)
    candidates = session.scalars(
        select(Article)
        .options(selectinload(Article.source))
        .where(
            Article.source_id.in_(source_ids),
            Article.published_at >= now - timedelta(hours=LOOKBACK_HOURS),
            Article.fulltext_status != Status.PENDING,
        )
    ).all()
    scored = sorted(
        (Scored(a, score_article(a, reader, now)) for a in candidates if a.id not in printed),
        key=lambda s: s.score,
        reverse=True,
    )
    picked: list[Scored] = []
    per_source: dict[int, int] = {}
    stories: set[int] = set()
    for s in scored:
        if s.score <= 0:
            continue
        if per_source.get(s.article.source_id, 0) >= MAX_PER_SOURCE:
            continue
        if s.article.story_id is not None and s.article.story_id in stories:
            continue  # one article per running story
        picked.append(s)
        per_source[s.article.source_id] = per_source.get(s.article.source_id, 0) + 1
        if s.article.story_id is not None:
            stories.add(s.article.story_id)
        if len(picked) >= reader.story_count + BRIEF_COUNT:
            break
    return picked


def _background(session: Session, article: Article, tz: ZoneInfo) -> list[str]:
    if article.story_id is None:
        return []
    earlier = session.scalars(
        select(Article)
        .where(
            Article.story_id == article.story_id,
            Article.id != article.id,
            Article.published_at < article.published_at,
            Article.enrichment.is_not(None),
        )
        .order_by(Article.published_at.desc())
        .limit(BACKGROUND_EVENTS)
    ).all()
    return [f"{a.published_at.astimezone(tz):%d.%m.}: {a.enrichment['event']}" for a in reversed(earlier)]


def story_item(session: Session, article: Article, size: str, tz: ZoneInfo) -> dict[str, Any]:
    e = article.enrichment if article.enrichment_status == Status.DONE else None
    item: dict[str, Any] = {
        "section": article.source.category,
        "size": size,
        "headline": e["headline"] if e else article.title,
        "subhead": e.get("subhead") if e else None,
        "source": article.source.name,
        "published": f"{article.published_at.astimezone(tz):%d.%m., %H:%M}",
        "url": article.url,
        "teaser_only": article.teaser_only,
        "excerpt": e is None,
        "body": e["summary"] if e else (shorten(article.best_text, TEXT_BUDGET[size]) or [article.title]),
    }
    if background := _background(session, article, tz):
        item["background"] = background
    return item


def brief_item(article: Article) -> dict[str, Any]:
    e = article.enrichment if article.enrichment_status == Status.DONE else None
    text = e["event"] if e else (sentences(article.best_text)[:1] or [article.title])[0]
    return {"headline": e["headline"] if e else article.title, "text": text, "source": article.source.name}


def _calendar(
    session: Session, reader: Reader, now: datetime, tz: ZoneInfo, lang: str
) -> list[dict[str, str]]:
    n = names(lang)
    ics_sources = select(ReaderSource.source_id).where(ReaderSource.reader_id == reader.id)
    events = session.scalars(
        select(CalendarEvent)
        .where(
            CalendarEvent.source_id.in_(ics_sources),
            CalendarEvent.starts_at >= now - timedelta(hours=12),
            CalendarEvent.starts_at < now + timedelta(days=3),
        )
        .order_by(CalendarEvent.starts_at)
        .limit(8)
    ).all()
    result = []
    for ev in events:
        local = ev.starts_at.astimezone(tz) if not ev.all_day else ev.starts_at
        when = f"{n['weekdays'][local.weekday()][:2]} {local:%d.%m.}, " + (
            n["all_day"] if ev.all_day else f"{local:%H:%M}"
        )
        result.append({"when": when, "what": ev.summary})
    return result


def _letters(session: Session, since: datetime) -> list[dict[str, str]]:
    letters = session.scalars(
        select(Letter).where(Letter.created_at >= since).order_by(Letter.created_at).limit(6)
    ).all()
    return [{"from": letter.author, "text": letter.text} for letter in letters]


def compose(
    session: Session, reader: Reader, settings: Settings, issue_date: date, http: httpx.Client | None
) -> dict[str, Any]:
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(UTC)
    lang = reader.language
    n = names(lang)
    number = (session.scalar(select(func.count()).where(Edition.reader_id == reader.id)) or 0) + 1

    picked = select_articles(session, reader, now)
    main, rest = picked[: reader.story_count], picked[reader.story_count :]
    lead = next((s for s in main if s.article.fulltext_status == Status.DONE), main[0] if main else None)
    others = [s for s in main if s is not lead]
    sizes = ["large"] * 2 + ["medium"] * 3 + ["small"] * 100
    stories = [story_item(session, s.article, sizes[i], tz) for i, s in enumerate(others)]

    previous = session.scalar(
        select(func.max(Edition.created_at)).where(
            Edition.reader_id == reader.id, Edition.issue_date < issue_date
        )
    )
    letters = _letters(session, previous or now - timedelta(days=1))
    sections = list(dict.fromkeys(s.article.source.category for s in picked))
    if letters:
        sections.append(n["family"])

    edition: dict[str, Any] = {
        "masthead": {"title": "Eilkurier", "slogan": n["slogan"], "region": n["region"], "since": n["since"]},
        "edition": {
            "number": number,
            "date": issue_date.isoformat(),
            "date_label": date_label(issue_date, lang),
            "reader": reader.name,
            "lang": lang,
        },
        "style": {
            "theme": reader.theme,
            "paper": reader.paper,
            "font_scale": reader.font_scale,
            "paper_tint": reader.paper_tint,
        },
        "weather": almanac.weather(http, settings, issue_date, lang) if http else None,
        "sections": sections or [n["region"]],
        "lead": story_item(session, lead.article, "lead", tz) if lead else None,
        "stories": stories,
        "briefs": [brief_item(s.article) for s in rest],
        "calendar": _calendar(session, reader, now, tz, lang),
        "family": letters,
        "almanac": almanac.almanac(http, settings, issue_date, lang),
        "meta": {
            "article_ids": [s.article.id for s in picked],
            "generated_at": now.isoformat(),
            "edited": sum(1 for s in picked if s.article.enrichment_status == Status.DONE),
        },
    }
    return {k: v for k, v in edition.items() if v is not None}


def build_edition(
    session: Session,
    reader: Reader,
    settings: Settings,
    issue_date: date,
    http: httpx.Client | None,
    renderer: EditionRenderer,
) -> Edition:
    """Compose, typeset and store (or replace) the reader's edition for `issue_date`."""
    payload = compose(session, reader, settings, issue_date, http)
    edition = session.scalar(
        select(Edition).where(Edition.reader_id == reader.id, Edition.issue_date == issue_date)
    )
    if edition is None:
        edition = Edition(reader_id=reader.id, issue_date=issue_date, number=payload["edition"]["number"])
        session.add(edition)
    payload["edition"]["number"] = edition.number
    edition.payload = payload
    edition.pdf = renderer.render_pdf(payload)
    edition.status = Status.DONE
    session.flush()
    return edition
