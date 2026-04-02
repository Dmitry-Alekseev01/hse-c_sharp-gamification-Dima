"""add test ownership

Revision ID: 0007_add_test_ownership
Revises: 0006_add_perf_indexes
Create Date: 2026-03-31 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_add_test_ownership"
down_revision = "0006_add_perf_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tests", sa.Column("author_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_tests_author_id_users", "tests", "users", ["author_id"], ["id"])
    op.create_index("ix_tests_author_id", "tests", ["author_id"], unique=False)

    op.execute(
        """
        UPDATE tests
        SET author_id = materials.author_id
        FROM materials
        WHERE tests.author_id IS NULL
          AND tests.material_id IS NOT NULL
          AND tests.material_id = materials.id
          AND materials.author_id IS NOT NULL
        """
    )

    op.execute(
        """
        UPDATE tests
        SET author_id = links.author_id
        FROM (
            SELECT mtl.test_id, MIN(m.author_id) AS author_id
            FROM material_test_links AS mtl
            JOIN materials AS m ON m.id = mtl.material_id
            WHERE m.author_id IS NOT NULL
            GROUP BY mtl.test_id
        ) AS links
        WHERE tests.id = links.test_id
          AND tests.author_id IS NULL
        """
    )


def downgrade():
    op.drop_index("ix_tests_author_id", table_name="tests")
    op.drop_constraint("fk_tests_author_id_users", "tests", type_="foreignkey")
    op.drop_column("tests", "author_id")
