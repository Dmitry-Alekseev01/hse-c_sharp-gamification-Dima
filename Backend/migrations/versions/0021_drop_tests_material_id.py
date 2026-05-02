"""make test-material relation m2m-only (drop tests.material_id)

Revision ID: 0021_drop_tests_material_id
Revises: 0020_add_test_max_attempts
Create Date: 2026-04-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_drop_tests_material_id"
down_revision = "0020_add_test_max_attempts"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "tests", "material_id"):
        return

    # Preserve all legacy direct links before dropping the legacy column.
    op.execute(
        """
        INSERT INTO material_test_links (material_id, test_id)
        SELECT t.material_id, t.id
        FROM tests AS t
        WHERE t.material_id IS NOT NULL
          AND NOT EXISTS (
                SELECT 1
                FROM material_test_links AS mtl
                WHERE mtl.material_id = t.material_id
                  AND mtl.test_id = t.id
            )
        """
    )

    foreign_keys = inspector.get_foreign_keys("tests")
    for foreign_key in foreign_keys:
        constrained_columns = foreign_key.get("constrained_columns") or []
        name = foreign_key.get("name")
        if name and "material_id" in constrained_columns:
            op.drop_constraint(name, "tests", type_="foreignkey")

    indexes = inspector.get_indexes("tests")
    for index in indexes:
        index_name = index.get("name")
        column_names = index.get("column_names") or []
        if index_name and "material_id" in column_names:
            op.drop_index(index_name, table_name="tests")

    op.drop_column("tests", "material_id")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_column(inspector, "tests", "material_id"):
        return

    op.add_column("tests", sa.Column("material_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tests_material_id_materials",
        "tests",
        "materials",
        ["material_id"],
        ["id"],
    )
    op.create_index("ix_tests_material_id", "tests", ["material_id"], unique=False)

    # Restore a single representative material per test from the m2m links.
    op.execute(
        """
        UPDATE tests AS t
        SET material_id = links.material_id
        FROM (
            SELECT mtl.test_id, MIN(mtl.material_id) AS material_id
            FROM material_test_links AS mtl
            GROUP BY mtl.test_id
        ) AS links
        WHERE t.id = links.test_id
          AND t.material_id IS NULL
        """
    )
