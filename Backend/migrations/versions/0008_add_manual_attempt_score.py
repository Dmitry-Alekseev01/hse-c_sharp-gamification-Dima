"""add manual attempt score override

Revision ID: 0008_add_manual_attempt_score
Revises: 0007_add_test_ownership
Create Date: 2026-04-06 16:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_add_manual_attempt_score"
down_revision = "0007_add_test_ownership"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("test_attempts", sa.Column("manual_score", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("test_attempts", "manual_score")
