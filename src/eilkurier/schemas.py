"""API data transfer objects (the OpenAPI contract of /api/v1)."""

from datetime import date, datetime, time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from eilkurier.render import Theme

Language = Literal["de", "en"]
Paper = Literal["a4", "a5", "a3"]
ChannelName = Literal["telegram", "email", "none"]
Weekday = Annotated[int, Field(ge=1, le=7)]


class ReaderIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    language: Language = "de"
    theme: Theme = Theme.EPAPER
    paper: Paper = "a4"
    font_scale: float = Field(1.0, ge=0.8, le=1.6)
    paper_tint: bool = True
    story_count: int = Field(8, ge=3, le=15)
    channel: ChannelName = "none"
    email: EmailStr | None = None
    delivery_time: time = time(6, 0)
    delivery_days: list[Weekday] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7])
    active: bool = True


class InterestIO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    term: str = Field(min_length=2, max_length=80)
    weight: float = Field(1.0, ge=-2.0, le=3.0, description="Negative = please less of this topic")


class ReaderOut(ReaderIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_linked: bool
    telegram_link_code: str | None
    interests: list[InterestIO]
    source_ids: list[int] = Field(description="Most important first")


class SourceIn(BaseModel):
    kind: Literal["rss", "ics"] = "rss"
    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    category: str = Field("Allgemein", min_length=1, max_length=80)
    fetch_fulltext: bool = True
    enabled: bool = True


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    name: str
    url: str
    category: str
    fetch_fulltext: bool
    enabled: bool
    last_fetched_at: datetime | None
    last_error: str | None
    article_count: int = 0


class CatalogTopic(BaseModel):
    category: str = Field(description="Section name; sources of this topic get it as `category`")
    title: str
    description: str
    icon: str
    color: str


class CatalogEntry(BaseModel):
    name: str
    url: str
    category: str
    description: str
    language: str = "de"
    group: str | None = Field(None, description="Sub-heading within a topic, e.g. the publisher")
    recommended: bool = False
    source_id: int | None = Field(None, description="Set when the entry has been added as a source")


class Catalog(BaseModel):
    topics: list[CatalogTopic]
    sources: list[CatalogEntry]


class EditionSummary(BaseModel):
    id: int
    reader_id: int
    number: int
    issue_date: date
    lead_headline: str | None
    story_count: int
    edited_count: int
    delivery_status: str
    delivery_error: str | None
    delivered_at: datetime | None


class EditionOut(EditionSummary):
    payload: dict[str, Any]


class LetterIn(BaseModel):
    author: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=1000)


class LetterOut(LetterIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    via: str
    created_at: datetime


class LanguageModelStatus(BaseModel):
    configured: bool
    available: bool
    url: str
    model: str
    embedding_model: str


class PipelineCounts(BaseModel):
    articles_total: int
    fulltext_pending: int
    enrichment_pending: int
    enriched: int
    stories_open: int


class StatusOut(BaseModel):
    version: str
    language_model: LanguageModelStatus
    telegram: bool
    email: bool
    counts: PipelineCounts
    sources_with_errors: int


class SessionIn(BaseModel):
    pin: str


class SessionOut(BaseModel):
    pin_required: bool
    authenticated: bool
