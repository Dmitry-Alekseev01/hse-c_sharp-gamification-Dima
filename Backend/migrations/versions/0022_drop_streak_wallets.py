"""drop legacy user_streak_wallets table if present

Revision ID: 0022_drop_streak_wallets
Revises: 0021_drop_tests_material_id
Create Date: 2026-05-01 16:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_drop_streak_wallets"
down_revision = "0021_drop_tests_material_id"
branch_labels = None
depends_on = None


def upgrade():
    # Legacy table from removed feature can still exist in long-lived/dev DBs.
    # Keep cleanup idempotent and safe across environments.
    op.execute("DROP TABLE IF EXISTS user_streak_wallets CASCADE")


def downgrade():
    op.create_table(
        "user_streak_wallets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("freeze_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_freeze_tokens", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("last_auto_used_at", sa.DateTime(), nullable=True),
        sa.Column("last_manual_repair_at", sa.DateTime(), nullable=True),
        sa.Column("last_refill_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_streak_wallets_user_id", "user_streak_wallets", ["user_id"], unique=False)
