"""Retain explicit editorial reading recommendations on book-topic links."""

from alembic import op
import sqlalchemy as sa

revision = "0003_featured_reading"
down_revision = "0002_courses"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("book_topic", sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def downgrade():
    op.drop_column("book_topic", "is_featured")
