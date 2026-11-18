"""Collecting: feeds (RSS/Atom), full article text and calendars (ICS)."""

import calendar
import logging
from datetime import UTC, date, datetime, timedelta

import feedparser
import httpx
import icalendar
import recurring_ical_events
import trafilatura
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from eilkurier import images
from eilkurier.db import Article, CalendarEvent, Source, SourceKind, Status
from eilkurier.http import HostThrottle
from eilkurier.settings import Settings
from eilkurier.text import looks_scrambled, strip_html

log = logging.getLogger(__name__)

# Below this many characters an extraction is treated as a paywall/teaser page.
MIN_FULLTEXT_CHARS = 500
# Consent walls and paywalls that extractors mistake for the article.
WALL_MARKERS = (
    "werbung und tracking",
    "cookies zustimmen",
    "privacy center",
    "pur-abo",
    "werbefrei lesen",
    "jetzt abonnieren",
    "abo abschließen",
    "zustimmung zu cookies",
    "consent",
    "accept all cookies",
    "subscribe to continue",
    "subscribe to read",
)
# Bot blocks ("Ihre Anfrage wurde blockiert") can be long: matched at the start, regardless of length.
BLOCK_MARKERS = (
    "anfrage wurde blockiert",
    "automatisierten zugriffen",
    "automatisiert abgerufen",
    "access denied",
    "request blocked",
    "you have been blocked",
    "are you a robot",
)


def _entry_time(entry: feedparser.FeedParserDict) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), tz=UTC)
    return None


def due_sources(session: Session, settings: Settings, now: datetime) -> list[Source]:
    threshold = now - timedelta(minutes=settings.fetch_interval_minutes)
    return list(
        session.scalars(
            select(Source).where(
                Source.enabled,
                (Source.last_fetched_at.is_(None)) | (Source.last_fetched_at < threshold),
            )
        )
    )


def collect_source(session: Session, source: Source, http: httpx.Client, settings: Settings) -> int:
    """Fetch one source. Returns the number of new items. Errors are recorded on the source."""
    now = datetime.now(UTC)
    try:
        count = (
            _collect_ics(session, source, http, now)
            if source.kind == SourceKind.ICS
            else _collect_rss(session, source, http, settings, now)
        )
        source.last_error = None
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("source %s failed: %s", source.url, exc)
        source.last_error = f"{type(exc).__name__}: {exc}"[:1000]
        count = 0
    source.last_fetched_at = now
    return count


def _collect_rss(
    session: Session, source: Source, http: httpx.Client, settings: Settings, now: datetime
) -> int:
    headers = {}
    if source.etag:
        headers["If-None-Match"] = source.etag
    if source.last_modified:
        headers["If-Modified-Since"] = source.last_modified
    response = http.get(source.url, headers=headers)
    if response.status_code == 304:
        return 0
    response.raise_for_status()
    source.etag = response.headers.get("etag")
    source.last_modified = response.headers.get("last-modified")

    feed = feedparser.parse(response.content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"not a feed: {feed.get('bozo_exception')}")

    oldest = now - timedelta(days=settings.article_retention_days)
    rows = []
    for entry in feed.entries:
        published = _entry_time(entry) or now
        if published < oldest:
            continue
        published = min(published, now)  # some feeds publish dates in the future
        link = entry.get("link")
        guid = entry.get("id") or link or entry.get("title")
        title = strip_html(entry.get("title"))
        if not guid or not title:
            continue
        teaser = strip_html(entry.get("summary") or entry.get("description") or "")
        picture = images.from_feed(entry, link) if images.wants_feed(source.image_mode) else None
        look_on_page = images.wants_page(source.image_mode) and bool(link)
        rows.append(
            {
                "image_url": picture.url[:2000] if picture else None,
                "image_alt": picture.alt if picture else None,
                "image_credit": picture.credit if picture else None,
                "image_status": Status.PENDING if (picture or look_on_page) else Status.SKIPPED,
                "source_id": source.id,
                "guid": guid[:1000],
                "url": link,
                "title": title,
                "teaser": teaser[:4000],
                "published_at": published,
                "fulltext_status": Status.PENDING if (source.fetch_fulltext and link) else Status.SKIPPED,
            }
        )
    if not rows:
        return 0
    result = session.execute(
        insert(Article)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["source_id", "guid"])
        .returning(Article.id)
    )
    return len(result.all())


def _collect_ics(session: Session, source: Source, http: httpx.Client, now: datetime) -> int:
    response = http.get(source.url)
    response.raise_for_status()
    cal = icalendar.Calendar.from_ical(response.content)
    start = now.date()
    end = start + timedelta(days=14)
    session.execute(delete(CalendarEvent).where(CalendarEvent.source_id == source.id))
    count = 0
    for event in recurring_ical_events.of(cal).between(start, end):
        dtstart = event.get("DTSTART").dt
        all_day = isinstance(dtstart, date) and not isinstance(dtstart, datetime)
        if all_day:
            starts_at = datetime(dtstart.year, dtstart.month, dtstart.day, tzinfo=UTC)
        else:
            starts_at = dtstart if dtstart.tzinfo else dtstart.replace(tzinfo=UTC)
        session.add(
            CalendarEvent(
                source_id=source.id,
                uid=str(event.get("UID", ""))[:500],
                summary=str(event.get("SUMMARY", "")).strip() or "Termin",
                starts_at=starts_at,
                all_day=all_day,
            )
        )
        count += 1
    return count


def extract_fulltext(html: str, url: str | None = None) -> str | None:
    text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        deduplicate=True,
    )
    if not text or len(text) < MIN_FULLTEXT_CHARS:
        return None
    lowered = text.casefold()
    if any(marker in lowered[:600] for marker in BLOCK_MARKERS):
        return None  # the site blocked the automated request
    if len(text) < 2500 and sum(marker in lowered for marker in WALL_MARKERS) >= 2:
        return None  # consent or pay wall, not the article
    if looks_scrambled(text):
        return None  # pay wall that ships the article with shuffled letters
    return text


def fetch_fulltexts(session: Session, http: httpx.Client, settings: Settings, throttle: HostThrottle) -> int:
    """Load and extract the article page for pending articles. Paywalled/teaser-only pages are SKIPPED."""
    articles = session.scalars(
        select(Article)
        .where(Article.fulltext_status == Status.PENDING)
        .order_by(Article.published_at.desc())
        .limit(settings.fulltext_batch)
        .with_for_update(skip_locked=True)
    ).all()
    done = 0
    for article in articles:
        if not article.url:
            article.fulltext_status = Status.SKIPPED
            continue
        throttle.wait(article.url)
        try:
            response = http.get(article.url)
            response.raise_for_status()
            text = extract_fulltext(response.text, article.url)
        except httpx.HTTPError as exc:
            log.info("fulltext failed for %s: %s", article.url, exc)
            text = None
        else:
            # The page is loaded anyway: its preview picture is usually larger than the feed's.
            if images.wants_page(article.source.image_mode):
                images.apply(article, images.from_page(response.content, str(response.url)))
                if not article.image_url:
                    article.image_status = Status.SKIPPED
        if text:
            article.fulltext = text
            article.fulltext_status = Status.DONE
            done += 1
        else:
            article.fulltext_status = Status.SKIPPED
    return done


def purge_old(session: Session, settings: Settings, now: datetime) -> None:
    """Retention: editions keep their own copy of the texts, so old articles can go."""
    cutoff = now - timedelta(days=settings.article_retention_days)
    session.execute(delete(Article).where(Article.published_at < cutoff))
