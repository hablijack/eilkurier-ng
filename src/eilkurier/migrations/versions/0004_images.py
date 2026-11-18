"""Pictures: where each source gets them from, the article's picture, and the stored (downscaled) images.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(2000), nullable=False, unique=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("sources", sa.Column("image_mode", sa.String(16), nullable=False, server_default="auto"))
    op.add_column("articles", sa.Column("image_url", sa.String(2000)))
    op.add_column("articles", sa.Column("image_alt", sa.Text()))
    op.add_column("articles", sa.Column("image_credit", sa.String(300)))
    op.add_column(
        "articles", sa.Column("image_status", sa.String(16), nullable=False, server_default="skipped")
    )
    op.add_column(
        "articles",
        sa.Column("image_id", sa.Integer(), sa.ForeignKey("images.id", ondelete="SET NULL"), index=True),
    )
    op.create_index("ix_articles_image_status", "articles", ["image_status"])


def downgrade() -> None:
    op.drop_index("ix_articles_image_status", "articles")
    for column in ("image_id", "image_status", "image_credit", "image_alt", "image_url"):
        op.drop_column("articles", column)
    op.drop_column("sources", "image_mode")
    op.drop_table("images")
