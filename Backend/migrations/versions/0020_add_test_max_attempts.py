"""add max_attempts to tests

Revision ID: 0020_add_test_max_attempts
Revises: 0019_rewards_unlocks
Create Date: 2026-04-23 16:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_add_test_max_attempts"
down_revision = "0019_rewards_unlocks"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tests",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade():
    op.drop_column("tests", "max_attempts")
