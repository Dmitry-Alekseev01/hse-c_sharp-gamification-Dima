"""add level-based unlock fields

Revision ID: 0009_add_level_unlocks
Revises: 0008_add_manual_attempt_score
Create Date: 2026-04-06 18:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_add_level_unlocks"
down_revision = "0008_add_manual_attempt_score"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("materials", sa.Column("required_level_id", sa.Integer(), nullable=True))
    op.add_column("tests", sa.Column("required_level_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_materials_required_level_id_levels", "materials", "levels", ["required_level_id"], ["id"])
    op.create_foreign_key("fk_tests_required_level_id_levels", "tests", "levels", ["required_level_id"], ["id"])
    op.create_index("ix_materials_required_level_id", "materials", ["required_level_id"], unique=False)
    op.create_index("ix_tests_required_level_id", "tests", ["required_level_id"], unique=False)


def downgrade():
    op.drop_index("ix_tests_required_level_id", table_name="tests")
    op.drop_index("ix_materials_required_level_id", table_name="materials")
    op.drop_constraint("fk_tests_required_level_id_levels", "tests", type_="foreignkey")
    op.drop_constraint("fk_materials_required_level_id_levels", "materials", type_="foreignkey")
    op.drop_column("tests", "required_level_id")
    op.drop_column("materials", "required_level_id")
