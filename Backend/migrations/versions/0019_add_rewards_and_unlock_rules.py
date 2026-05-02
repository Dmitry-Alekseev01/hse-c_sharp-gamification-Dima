"""add rewards and unlock rules

Revision ID: 0019_rewards_unlocks
Revises: 0018_add_user_streak_wallets
Create Date: 2026-04-22 23:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_rewards_unlocks"
down_revision = "0018_add_user_streak_wallets"
branch_labels = None
depends_on = None


def upgrade():
    # Cleanup legacy table if someone ran the old streak-wallet migration locally.
    op.execute("DROP TABLE IF EXISTS user_streak_wallets CASCADE")

    op.create_table(
        "reward_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reward_type", sa.String(length=50), nullable=False, server_default="badge"),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_reward_definitions_code", "reward_definitions", ["code"])
    op.create_index("ix_reward_definitions_reward_type", "reward_definitions", ["reward_type"])
    op.create_index("ix_reward_definitions_is_active", "reward_definitions", ["is_active"])

    op.create_table(
        "unlock_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reward_definition_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_code", sa.String(length=100), nullable=True),
        sa.Column("min_level_required", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "source_type IN ('achievement', 'challenge', 'level')",
            name="ck_unlock_rules_source_type_valid",
        ),
        sa.ForeignKeyConstraint(["reward_definition_id"], ["reward_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reward_definition_id",
            "source_type",
            "source_code",
            "min_level_required",
            name="uq_unlock_rule_identity",
        ),
    )
    op.create_index("ix_unlock_rules_reward_definition_id", "unlock_rules", ["reward_definition_id"])
    op.create_index("ix_unlock_rules_source_type", "unlock_rules", ["source_type"])
    op.create_index("ix_unlock_rules_source_code", "unlock_rules", ["source_code"])
    op.create_index("ix_unlock_rules_is_active", "unlock_rules", ["is_active"])

    op.create_table(
        "user_rewards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reward_definition_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_ref", sa.String(length=120), nullable=True),
        sa.Column("earned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reward_definition_id"], ["reward_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "reward_definition_id", name="uq_user_reward_user_definition"),
    )
    op.create_index("ix_user_rewards_user_id", "user_rewards", ["user_id"])
    op.create_index("ix_user_rewards_reward_definition_id", "user_rewards", ["reward_definition_id"])
    op.create_index("ix_user_rewards_source_type", "user_rewards", ["source_type"])
    op.create_index("ix_user_rewards_earned_at", "user_rewards", ["earned_at"])


def downgrade():
    op.drop_index("ix_user_rewards_earned_at", table_name="user_rewards")
    op.drop_index("ix_user_rewards_source_type", table_name="user_rewards")
    op.drop_index("ix_user_rewards_reward_definition_id", table_name="user_rewards")
    op.drop_index("ix_user_rewards_user_id", table_name="user_rewards")
    op.drop_table("user_rewards")

    op.drop_index("ix_unlock_rules_is_active", table_name="unlock_rules")
    op.drop_index("ix_unlock_rules_source_code", table_name="unlock_rules")
    op.drop_index("ix_unlock_rules_source_type", table_name="unlock_rules")
    op.drop_index("ix_unlock_rules_reward_definition_id", table_name="unlock_rules")
    op.drop_table("unlock_rules")

    op.drop_index("ix_reward_definitions_is_active", table_name="reward_definitions")
    op.drop_index("ix_reward_definitions_reward_type", table_name="reward_definitions")
    op.drop_index("ix_reward_definitions_code", table_name="reward_definitions")
    op.drop_table("reward_definitions")
