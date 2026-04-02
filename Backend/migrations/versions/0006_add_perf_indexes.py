"""add performance indexes for analytics and hot paths

Revision ID: 0006_add_perf_indexes
Revises: 0005_add_study_groups
Create Date: 2026-03-26 00:45:00.000000
"""

from alembic import op


revision = "0006_add_perf_indexes"
down_revision = "0005_add_study_groups"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE INDEX IF NOT EXISTS ix_analytics_total_points_desc ON analytics (total_points DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_analytics_current_level_id ON analytics (current_level_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_answers_created_at_user_id ON answers (created_at, user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_answers_question_user_id ON answers (question_id, user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_test_attempts_test_status ON test_attempts (test_id, status)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_test_attempts_user_test_status_started_at "
        "ON test_attempts (user_id, test_id, status, started_at DESC)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_test_attempts_user_test_status_started_at")
    op.execute("DROP INDEX IF EXISTS ix_test_attempts_test_status")
    op.execute("DROP INDEX IF EXISTS ix_answers_question_user_id")
    op.execute("DROP INDEX IF EXISTS ix_answers_created_at_user_id")
    op.execute("DROP INDEX IF EXISTS ix_analytics_current_level_id")
    op.execute("DROP INDEX IF EXISTS ix_analytics_total_points_desc")
