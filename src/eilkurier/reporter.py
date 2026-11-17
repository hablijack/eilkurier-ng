"""The reporter: enrich each article once (LLM), embed it, and assign it to a running story."""

import logging
import math
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from eilkurier.db import Article, Interest, Status, Story
from eilkurier.llm import LLM, BadAnswer, Unavailable
from eilkurier.settings import Settings

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
MAX_INPUT_CHARS = 6000  # ~1.5k tokens: fits small context windows (Ollama default) with room for the answer
STORY_CANDIDATES = 5

ENRICH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "subhead", "summary", "event", "topics", "importance"],
    "properties": {
        "headline": {"type": "string"},
        "subhead": {"type": "string"},
        "summary": {"type": "array", "items": {"type": "string"}},
        "event": {"type": "string"},
        "topics": {"type": "array", "items": {"type": "string"}},
        "importance": {"type": "integer"},
    },
}

STORY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["story"],
    "properties": {"story": {"type": "integer"}},
}

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def load_prompt(settings: Settings, name: str) -> str:
    prompts = settings.resource_root / "prompts"
    path = prompts / f"{name}.{settings.language}.md"
    if not path.exists():
        path = prompts / f"{name}.de.md"
    return Path(path).read_text("utf-8")


def _numbers(text: str) -> set[str]:
    return {n.replace(".", "").replace(",", "") for n in _NUMBER.findall(text)}


def validate_enrichment(raw: dict[str, Any], source_text: str) -> dict[str, Any]:
    """Normalise the model answer and reject unsupported numbers (a common small-model hallucination)."""
    headline = str(raw.get("headline", "")).strip()
    summary = [str(p).strip() for p in raw.get("summary", []) if str(p).strip()][:3]
    event = str(raw.get("event", "")).strip()
    if not headline or not summary or not event:
        raise BadAnswer("incomplete")
    invented = (_numbers(" ".join([headline, *summary, event]))) - _numbers(source_text)
    if invented:
        raise BadAnswer(f"unsupported_numbers:{','.join(sorted(invented))}")
    topics = []
    for topic in raw.get("topics", []):
        t = str(topic).strip().lower().lstrip("#")
        if t and t not in topics:
            topics.append(t[:40])
    return {
        "headline": headline[:120],
        "subhead": str(raw.get("subhead", "")).strip()[:160] or None,
        "summary": summary,
        "event": event[:300],
        "topics": topics[:6],
        "importance": max(1, min(5, int(raw.get("importance", 3) or 3))),
    }


def enrich_article(llm: LLM, settings: Settings, article: Article) -> None:
    text = article.best_text[:MAX_INPUT_CHARS]
    user = f"TITEL: {article.title}\nQUELLE: {article.source.name}\n\nTEXT:\n{text}"
    article.enrichment_attempts += 1
    try:
        raw = llm.ask(
            load_prompt(settings, "enrich"), user, schema=ENRICH_SCHEMA, name="enrichment", max_tokens=700
        )
        article.enrichment = validate_enrichment(raw, f"{article.title}\n{text}")
        article.enrichment_status = Status.DONE
    except BadAnswer as exc:
        log.info("enrichment of article %s rejected: %s", article.id, exc)
        if article.enrichment_attempts >= MAX_ATTEMPTS:
            article.enrichment_status = Status.FAILED
            article.story_status = Status.SKIPPED
        return
    if llm.embedding_model:
        try:
            article.embedding = llm.embed([_embedding_text(article)])[0]
        except BadAnswer as exc:
            log.info("embedding of article %s failed: %s", article.id, exc)


def _embedding_text(article: Article) -> str:
    e = article.enrichment or {}
    return " ".join([e.get("headline", article.title), *e.get("summary", [article.teaser])])


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def story_candidates(session: Session, settings: Settings, article: Article, now: datetime) -> list[Story]:
    open_stories = session.scalars(
        select(Story).where(Story.last_article_at >= now - timedelta(days=settings.story_window_days))
    ).all()
    topics = (article.enrichment or {}).get("topics", [])
    scored = []
    for story in open_stories:
        score = _jaccard(topics, story.topics)
        if article.embedding is not None and story.embedding is not None:
            score = max(score, _cosine(list(article.embedding), list(story.embedding)))
        if score > 0.15:
            scored.append((score, story))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [s for _, s in scored[:STORY_CANDIDATES]]


def assign_story(session: Session, llm: LLM, settings: Settings, article: Article, now: datetime) -> None:
    e = article.enrichment or {}
    candidates = story_candidates(session, settings, article, now)
    chosen: Story | None = None
    if candidates:
        listing = "\n".join(
            f"{i}. {s.title} – {_latest_event(session, s)}" for i, s in enumerate(candidates, 1)
        )
        user = f"NEUE MELDUNG: {e.get('headline')}: {e.get('event')}\n\nLAUFENDE GESCHICHTEN:\n{listing}"
        try:
            answer = llm.ask(
                load_prompt(settings, "story"), user, schema=STORY_SCHEMA, name="story", max_tokens=20
            )
            index = int(answer.get("story", 0))
        except (BadAnswer, ValueError, TypeError):
            index = 0
        if 1 <= index <= len(candidates):
            chosen = candidates[index - 1]
    if chosen is None:
        chosen = Story(
            title=e.get("headline", article.title), topics=list(e.get("topics", [])), last_article_at=now
        )
        if article.embedding is not None:
            chosen.embedding = list(article.embedding)
        session.add(chosen)
    else:
        chosen.topics = list(dict.fromkeys([*chosen.topics, *e.get("topics", [])]))[:12]
        chosen.last_article_at = max(chosen.last_article_at, article.published_at)
        if article.embedding is not None and chosen.embedding is not None:
            mixed = [0.7 * a + 0.3 * b for a, b in zip(chosen.embedding, article.embedding, strict=False)]
            norm = math.sqrt(sum(x * x for x in mixed)) or 1.0
            chosen.embedding = [x / norm for x in mixed]
    article.story = chosen
    article.story_status = Status.DONE


def _latest_event(session: Session, story: Story) -> str:
    article = session.scalars(
        select(Article)
        .where(Article.story_id == story.id, Article.enrichment.is_not(None))
        .order_by(Article.published_at.desc())
        .limit(1)
    ).first()
    return (article.enrichment or {}).get("event", "") if article else ""


def embed_interests(session: Session, llm: LLM) -> None:
    """Interests saved while the model was away get their embedding now."""
    if not llm.embedding_model:
        return
    missing = session.scalars(select(Interest).where(Interest.embedding.is_(None)).limit(64)).all()
    if missing:
        for interest, vector in zip(missing, llm.embed([i.term for i in missing]), strict=True):
            interest.embedding = vector
        session.commit()


def run(session: Session, llm: LLM, settings: Settings, budget_seconds: float = 120.0) -> int:
    """Enrich and assign as much as the time budget allows. Returns the number of processed articles."""
    if not settings.llm_enabled or not llm.available():
        return 0
    deadline = time.monotonic() + budget_seconds
    processed = 0
    now = datetime.now(UTC)
    try:
        embed_interests(session, llm)
        while time.monotonic() < deadline:
            article = session.scalars(
                select(Article)
                .where(
                    Article.enrichment_status == Status.PENDING,
                    Article.fulltext_status != Status.PENDING,
                )
                .order_by(Article.published_at.desc())
                .limit(1)
                .with_for_update(skip_locked=True)
            ).first()
            if article is None:
                break
            enrich_article(llm, settings, article)
            if article.enrichment_status == Status.DONE:
                assign_story(session, llm, settings, article, now)
            session.commit()
            processed += 1
    except Unavailable as exc:
        log.info("language model unavailable (%s); work resumes later", exc)
        session.rollback()
    return processed
