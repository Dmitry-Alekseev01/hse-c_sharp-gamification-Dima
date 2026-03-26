"""add study groups

Revision ID: 0005_add_study_groups
Revises: 0004_expand_tz_domain_model
Create Date: 2026-03-26 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_add_study_groups"
down_revision = "0004_expand_tz_domain_model"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "study_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_study_groups_teacher_id", "study_groups", ["teacher_id"], unique=False)

    op.create_table(
        "group_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("study_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_membership_group_user"),
    )
    op.create_index("ix_group_memberships_group_id", "group_memberships", ["group_id"], unique=False)
    op.create_index("ix_group_memberships_user_id", "group_memberships", ["user_id"], unique=False)


def downgrade():
    op.drop_index("ix_group_memberships_user_id", table_name="group_memberships")
    op.drop_index("ix_group_memberships_group_id", table_name="group_memberships")
    op.drop_table("group_memberships")

    op.drop_index("ix_study_groups_teacher_id", table_name="study_groups")
    op.drop_table("study_groups")
