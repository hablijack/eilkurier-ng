"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-17 14:31:37.611075
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "kv",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "readers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("theme", sa.String(length=32), nullable=False),
        sa.Column("paper", sa.String(length=8), nullable=False),
        sa.Column("font_scale", sa.Float(), nullable=False),
        sa.Column("paper_tint", sa.Boolean(), nullable=False),
        sa.Column("story_count", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("telegram_chat_id", sa.String(length=32), nullable=True),
        sa.Column("telegram_link_code", sa.String(length=16), nullable=True),
        sa.Column("delivery_time", sa.Time(), nullable=False),
        sa.Column(
            "delivery_days",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_link_code"),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("fetch_fulltext", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("etag", sa.String(length=300), nullable=True),
        sa.Column("last_modified", sa.String(length=100), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_table(
        "stories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "topics",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "last_article_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("guid", sa.String(length=1000), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("teaser", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("fulltext", sa.Text(), nullable=True),
        sa.Column("fulltext_status", sa.String(length=16), nullable=False),
        sa.Column(
            "enrichment",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("enrichment_status", sa.String(length=16), nullable=False),
        sa.Column("enrichment_attempts", sa.Integer(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(), nullable=True),
        sa.Column("story_id", sa.Integer(), nullable=True),
        sa.Column("story_status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "guid"),
    )
    op.create_index(op.f("ix_articles_enrichment_status"), "articles", ["enrichment_status"], unique=False)
    op.create_index(op.f("ix_articles_fulltext_status"), "articles", ["fulltext_status"], unique=False)
    op.create_index(op.f("ix_articles_published_at"), "articles", ["published_at"], unique=False)
    op.create_index(op.f("ix_articles_source_id"), "articles", ["source_id"], unique=False)
    op.create_index(op.f("ix_articles_story_id"), "articles", ["story_id"], unique=False)
    op.create_index(op.f("ix_articles_story_status"), "articles", ["story_status"], unique=False)
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("uid", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "uid", "starts_at"),
    )
    op.create_index(op.f("ix_calendar_events_source_id"), "calendar_events", ["source_id"], unique=False)
    op.create_index(op.f("ix_calendar_events_starts_at"), "calendar_events", ["starts_at"], unique=False)
    op.create_table(
        "editions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reader_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("pdf", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("delivery_status", sa.String(length=16), nullable=False),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reader_id"], ["readers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reader_id", "issue_date"),
    )
    op.create_index(op.f("ix_editions_reader_id"), "editions", ["reader_id"], unique=False)
    op.create_table(
        "interests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reader_id", sa.Integer(), nullable=False),
        sa.Column("term", sa.String(length=80), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(), nullable=True),
        sa.ForeignKeyConstraint(["reader_id"], ["readers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interests_reader_id"), "interests", ["reader_id"], unique=False)
    op.create_table(
        "letters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=80), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("reader_id", sa.Integer(), nullable=True),
        sa.Column("via", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reader_id"], ["readers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_letters_created_at"), "letters", ["created_at"], unique=False)
    op.create_table(
        "reader_sources",
        sa.Column("reader_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["reader_id"], ["readers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("reader_id", "source_id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("reader_sources")
    op.drop_index(op.f("ix_letters_created_at"), table_name="letters")
    op.drop_table("letters")
    op.drop_index(op.f("ix_interests_reader_id"), table_name="interests")
    op.drop_table("interests")
    op.drop_index(op.f("ix_editions_reader_id"), table_name="editions")
    op.drop_table("editions")
    op.drop_index(op.f("ix_calendar_events_starts_at"), table_name="calendar_events")
    op.drop_index(op.f("ix_calendar_events_source_id"), table_name="calendar_events")
    op.drop_table("calendar_events")
    op.drop_index(op.f("ix_articles_story_status"), table_name="articles")
    op.drop_index(op.f("ix_articles_story_id"), table_name="articles")
    op.drop_index(op.f("ix_articles_source_id"), table_name="articles")
    op.drop_index(op.f("ix_articles_published_at"), table_name="articles")
    op.drop_index(op.f("ix_articles_fulltext_status"), table_name="articles")
    op.drop_index(op.f("ix_articles_enrichment_status"), table_name="articles")
    op.drop_table("articles")
    op.drop_table("stories")
    op.drop_table("sources")
    op.drop_table("readers")
    op.drop_table("kv")
    # ### end Alembic commands ###
