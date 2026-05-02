"""harden attempts and answers integrity

Revision ID: 0023_attempts_answers_integrity
Revises: 0022_drop_streak_wallets
Create Date: 2026-05-01 16:45:00.000000
"""

from alembic import op


revision = "0023_attempts_answers_integrity"
down_revision = "0022_drop_streak_wallets"
branch_labels = None
depends_on = None


def upgrade():
    # Normalize statuses before adding strict constraint.
    op.execute(
        """
        UPDATE test_attempts
        SET status = 'in_progress'
        WHERE status IS NULL OR status NOT IN ('in_progress', 'completed')
        """
    )

    # Keep only the newest in-progress attempt per (user_id, test_id).
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id, test_id
                    ORDER BY started_at DESC NULLS LAST, id DESC
                ) AS row_num
            FROM test_attempts
            WHERE status = 'in_progress'
        )
        UPDATE test_attempts AS t
        SET
            status = 'completed',
            submitted_at = COALESCE(t.submitted_at, NOW()),
            completed_at = COALESCE(t.completed_at, t.submitted_at, NOW()),
            time_spent_seconds = COALESCE(t.time_spent_seconds, 0)
        FROM ranked
        WHERE t.id = ranked.id
          AND ranked.row_num > 1
        """
    )

    op.create_check_constraint(
        "ck_test_attempts_status_valid",
        "test_attempts",
        "status IN ('in_progress', 'completed')",
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_test_attempts_active_user_test
        ON test_attempts (user_id, test_id)
        WHERE status = 'in_progress'
        """
    )

    # Deduplicate answers for the same user/test/question/attempt slot.
    op.execute(
        """
        DELETE FROM answers AS a
        USING answers AS b
        WHERE a.id < b.id
          AND a.user_id = b.user_id
          AND a.test_id = b.test_id
          AND a.question_id = b.question_id
          AND a.attempt_id IS NOT NULL
          AND b.attempt_id IS NOT NULL
          AND a.attempt_id = b.attempt_id
        """
    )
    op.execute(
        """
        DELETE FROM answers AS a
        USING answers AS b
        WHERE a.id < b.id
          AND a.user_id = b.user_id
          AND a.test_id = b.test_id
          AND a.question_id = b.question_id
          AND a.attempt_id IS NULL
          AND b.attempt_id IS NULL
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_answers_user_test_question_attempt
        ON answers (user_id, test_id, question_id, attempt_id)
        WHERE attempt_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_answers_user_test_question_no_attempt
        ON answers (user_id, test_id, question_id)
        WHERE attempt_id IS NULL
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ux_answers_user_test_question_no_attempt")
    op.execute("DROP INDEX IF EXISTS ux_answers_user_test_question_attempt")
    op.execute("DROP INDEX IF EXISTS ux_test_attempts_active_user_test")
    op.drop_constraint("ck_test_attempts_status_valid", "test_attempts", type_="check")
