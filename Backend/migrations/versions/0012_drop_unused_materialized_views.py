"""drop unused materialized views

Revision ID: 0012_drop_unused_mvs
Revises: 0011_drop_material_legacy_fields
Create Date: 2026-04-07 20:00:00.000000
"""

from alembic import op


revision = "0012_drop_unused_mvs"
down_revision = "0011_drop_material_legacy_fields"
branch_labels = None
depends_on = None


def upgrade():
    # These views are not used by the runtime code and add maintenance overhead.
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_question_stats;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_test_summary;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_leaderboard;")


def downgrade():
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_leaderboard AS
        SELECT a.user_id, u.username, a.total_points
        FROM analytics a
        JOIN users u ON u.id = a.user_id
        ORDER BY a.total_points DESC;
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_leaderboard_user_id ON mv_leaderboard (user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mv_leaderboard_points ON mv_leaderboard (total_points DESC);")

    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_test_summary AS
        SELECT t.id as test_id,
               count(distinct q.id) as total_questions,
               count(a.id) as total_attempts,
               avg(a.score) as avg_score
        FROM tests t
        LEFT JOIN questions q ON q.test_id = t.id
        LEFT JOIN answers a ON a.test_id = t.id
        GROUP BY t.id;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_mv_test_summary_test_id ON mv_test_summary (test_id);")

    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_question_stats AS
        SELECT q.id as question_id,
               count(a.id) as attempts,
               avg(a.score) as avg_score,
               count(distinct a.user_id) as distinct_users
        FROM questions q
        LEFT JOIN answers a ON a.question_id = q.id
        GROUP BY q.id;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_mv_question_stats_qid ON mv_question_stats (question_id);")
