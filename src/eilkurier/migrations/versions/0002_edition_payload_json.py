"""Edition payload as JSON (keeps key order; JSONB sorts keys).

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE editions ALTER COLUMN payload TYPE json USING payload::json")


def downgrade() -> None:
    op.execute("ALTER TABLE editions ALTER COLUMN payload TYPE jsonb USING payload::jsonb")
