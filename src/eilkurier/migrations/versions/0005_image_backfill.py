"""Pictures for installations from before 0.3.0: catalog picture settings and recent articles.

Sources added before 0004 got `auto`; catalog sources now get the measured setting. Recent articles (collected
before pictures existed) get another chance: the picture step looks for the page's preview picture, but only
for those a reader is likely to get.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

from eilkurier.catalog import load_catalog

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sources = sa.table("sources", sa.column("url", sa.String), sa.column("image_mode", sa.String))
    for entry in load_catalog()["sources"]:
        mode = entry.get("images", "auto")
        if mode != "auto":
            op.execute(
                sources.update()
                .where(sources.c.url == entry["url"], sources.c.image_mode == "auto")
                .values(image_mode=mode)
            )
    op.execute(
        """
        UPDATE articles SET image_status = 'pending'
        FROM sources
        WHERE articles.source_id = sources.id
          AND sources.image_mode IN ('auto', 'page')
          AND articles.image_status = 'skipped' AND articles.image_url IS NULL AND articles.url IS NOT NULL
          AND articles.published_at > now() - interval '36 hours'
        """
    )


def downgrade() -> None:
    pass  # data only
