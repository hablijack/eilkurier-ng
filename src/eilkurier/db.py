"""Database schema (SQLAlchemy 2.0) and session handling. Postgres + pgvector is the only state store."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, time
from enum import StrEnum
from functools import lru_cache
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    Time,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from eilkurier.settings import get_settings

JsonDict = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class SourceKind(StrEnum):
    RSS = "rss"
    ICS = "ics"  # calendar: appointments and birthdays


class Status(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class ImageMode(StrEnum):
    """Where a source's pictures come from."""

    AUTO = "auto"  # from the feed, otherwise from the article page
    FEED = "feed"  # only the picture the feed entry carries (media:content, enclosure, <img>)
    PAGE = "page"  # only the article page's preview picture (og:image / twitter:image)
    NONE = "none"  # never: logos only, stock photos, or the family does not want them


class Channel(StrEnum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    NONE = "none"


class Reader(Base):
    __tablename__ = "readers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    language: Mapped[str] = mapped_column(String(8), default="de")
    theme: Mapped[str] = mapped_column(String(32), default="epaper")
    paper: Mapped[str] = mapped_column(String(8), default="a4")
    font_scale: Mapped[float] = mapped_column(Float, default=1.0)
    paper_tint: Mapped[bool] = mapped_column(Boolean, default=True)
    story_count: Mapped[int] = mapped_column(Integer, default=8)
    channel: Mapped[str] = mapped_column(String(16), default=Channel.NONE)
    email: Mapped[str | None] = mapped_column(String(254))
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32))
    telegram_link_code: Mapped[str | None] = mapped_column(String(16), unique=True)
    delivery_time: Mapped[time] = mapped_column(Time, default=time(6, 0))
    # ISO weekdays 1 (Monday) … 7 (Sunday)
    delivery_days: Mapped[list[int]] = mapped_column(JsonDict, default=lambda: [1, 2, 3, 4, 5, 6, 7])
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    interests: Mapped[list["Interest"]] = relationship(
        back_populates="reader", cascade="all, delete-orphan", order_by="Interest.id"
    )
    # Ordered by importance (ReaderSource.position); set it with `set_reader_sources`.
    sources: Mapped[list["Source"]] = relationship(
        secondary="reader_sources", back_populates="readers", order_by="ReaderSource.position"
    )


class Interest(Base):
    __tablename__ = "interests"

    id: Mapped[int] = mapped_column(primary_key=True)
    reader_id: Mapped[int] = mapped_column(ForeignKey("readers.id", ondelete="CASCADE"), index=True)
    term: Mapped[str] = mapped_column(String(80))
    weight: Mapped[float] = mapped_column(Float, default=1.0)  # negative = "please less of this"
    embedding: Mapped[list[float] | None] = mapped_column(Vector())

    reader: Mapped[Reader] = relationship(back_populates="interests")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default=SourceKind.RSS)
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    category: Mapped[str] = mapped_column(String(80), default="Allgemein")
    fetch_fulltext: Mapped[bool] = mapped_column(Boolean, default=True)
    image_mode: Mapped[str] = mapped_column(String(16), default=ImageMode.AUTO, server_default="auto")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    etag: Mapped[str | None] = mapped_column(String(300))
    last_modified: Mapped[str | None] = mapped_column(String(100))
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    readers: Mapped[list[Reader]] = relationship(secondary="reader_sources", back_populates="sources")


class ReaderSource(Base):
    __tablename__ = "reader_sources"

    reader_id: Mapped[int] = mapped_column(ForeignKey("readers.id", ondelete="CASCADE"), primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Story(Base):
    """A running story across days. Its articles' `event` sentences form "Was bisher geschah"."""

    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    topics: Mapped[list[str]] = mapped_column(JsonDict, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(Vector())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_article_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    articles: Mapped[list["Article"]] = relationship(back_populates="story")


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("source_id", "guid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    guid: Mapped[str] = mapped_column(String(1000))
    url: Mapped[str | None] = mapped_column(String(2000))
    title: Mapped[str] = mapped_column(Text)
    teaser: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    fulltext: Mapped[str | None] = mapped_column(Text)
    fulltext_status: Mapped[str] = mapped_column(String(16), default=Status.PENDING, index=True)

    # LLM enrichment: {"headline", "summary": [..], "event", "facts": [..], "topics": [..], "importance"}
    enrichment: Mapped[dict[str, Any] | None] = mapped_column(JsonDict)
    enrichment_status: Mapped[str] = mapped_column(String(16), default=Status.PENDING, index=True)
    enrichment_attempts: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(Vector())

    story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"), index=True)
    story_status: Mapped[str] = mapped_column(String(16), default=Status.PENDING, index=True)

    # Picture: found in the feed at collection time, or on the page with the full text (`image_url`);
    # downloaded and downscaled only for articles that are likely to be printed (`images.fetch`).
    image_url: Mapped[str | None] = mapped_column(String(2000))
    image_alt: Mapped[str | None] = mapped_column(Text)
    image_credit: Mapped[str | None] = mapped_column(String(300))
    image_status: Mapped[str] = mapped_column(
        String(16), default=Status.SKIPPED, server_default="skipped", index=True
    )
    image_id: Mapped[int | None] = mapped_column(ForeignKey("images.id", ondelete="SET NULL"), index=True)

    source: Mapped[Source] = relationship()
    image: Mapped["Image | None"] = relationship()
    story: Mapped[Story | None] = relationship(back_populates="articles")

    @property
    def teaser_only(self) -> bool:
        return self.fulltext_status != Status.DONE

    @property
    def best_text(self) -> str:
        return self.fulltext or self.teaser or ""


class Image(Base):
    """A downscaled JPEG, shared by all articles (and editions) that use the same picture URL."""

    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(2000), unique=True)
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CalendarEvent(Base):
    """Appointments from ICS sources, expanded for the next days at collection time."""

    __tablename__ = "calendar_events"
    __table_args__ = (UniqueConstraint("source_id", "uid", "starts_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    uid: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)


class Letter(Base):
    """'Leserbrief': a short message from a family member, printed in everyone's next edition."""

    __tablename__ = "letters"

    id: Mapped[int] = mapped_column(primary_key=True)
    author: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(Text)
    reader_id: Mapped[int | None] = mapped_column(ForeignKey("readers.id", ondelete="SET NULL"))
    via: Mapped[str] = mapped_column(String(16), default="web")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Edition(Base):
    __tablename__ = "editions"
    __table_args__ = (UniqueConstraint("reader_id", "issue_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reader_id: Mapped[int] = mapped_column(ForeignKey("readers.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    issue_date: Mapped[date] = mapped_column(Date)
    # Plain JSON, not JSONB: JSONB reorders keys, and the order is content (e.g. almanac entries).
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    pdf: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    status: Mapped[str] = mapped_column(String(16), default=Status.PENDING)
    delivery_status: Mapped[str] = mapped_column(String(16), default=Status.PENDING)
    delivery_error: Mapped[str | None] = mapped_column(Text)
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reader: Mapped[Reader] = relationship()


class KeyValue(Base):
    """Small persistent worker state (e.g. Telegram update offset)."""

    __tablename__ = "kv"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


@lru_cache
def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=2)


def session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(engine or get_engine(), expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    session = session_factory(engine)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def kv_get(session: Session, key: str, default: str | None = None) -> str | None:
    row = session.get(KeyValue, key)
    return row.value if row else default


def kv_set(session: Session, key: str, value: str) -> None:
    row = session.get(KeyValue, key)
    if row:
        row.value = value
    else:
        session.add(KeyValue(key=key, value=value))
