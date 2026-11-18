"""Reader sources are ordered: position 0 is the reader's most important source.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reader_sources", sa.Column("position", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("reader_sources", "position")
