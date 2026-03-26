"""expand domain model for technical specification

Revision ID: 0004_expand_tz_domain_model
Revises: 97fa3f420770
Create Date: 2026-03-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_expand_tz_domain_model"
down_revision = "97fa3f420770"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("materials", sa.Column("content_text", sa.Text(), nullable=False, server_default=""))
    op.add_column("materials", sa.Column("video_url", sa.String(length=1000), nullable=True))
    op.add_column("tests", sa.Column("deadline", sa.DateTime(), nullable=True))
    op.add_column("questions", sa.Column("material_urls", sa.JSON(), nullable=True))

    op.create_table(
        "material_test_links",
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("test_id", sa.Integer(), sa.ForeignKey("tests.id", ondelete="CASCADE"), primary_key=True),
    )
    op.execute(
        """
        INSERT INTO material_test_links (material_id, test_id)
        SELECT material_id, id
        FROM tests
        WHERE material_id IS NOT NULL
        """
    )

    op.create_table(
        "test_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("test_id", sa.Integer(), sa.ForeignKey("tests.id"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="in_progress"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=True),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_test_attempts_user_id", "test_attempts", ["user_id"], unique=False)
    op.create_index("ix_test_attempts_test_id", "test_attempts", ["test_id"], unique=False)
    op.create_index("ix_test_attempts_status", "test_attempts", ["status"], unique=False)

    op.add_column("answers", sa.Column("attempt_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_answers_attempt_id_test_attempts", "answers", "test_attempts", ["attempt_id"], ["id"])
    op.create_index("ix_answers_attempt_id", "answers", ["attempt_id"], unique=False)

    op.alter_column("materials", "content_text", server_default=None)


def downgrade():
    op.drop_index("ix_answers_attempt_id", table_name="answers")
    op.drop_constraint("fk_answers_attempt_id_test_attempts", "answers", type_="foreignkey")
    op.drop_column("answers", "attempt_id")

    op.drop_index("ix_test_attempts_status", table_name="test_attempts")
    op.drop_index("ix_test_attempts_test_id", table_name="test_attempts")
    op.drop_index("ix_test_attempts_user_id", table_name="test_attempts")
    op.drop_table("test_attempts")

    op.drop_table("material_test_links")

    op.drop_column("questions", "material_urls")
    op.drop_column("tests", "deadline")
    op.drop_column("materials", "video_url")
    op.drop_column("materials", "content_text")
