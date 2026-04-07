"""add rich material content units

Revision ID: 0010_material_content_units
Revises: 0009_add_level_unlocks
Create Date: 2026-04-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_material_content_units"
down_revision = "0009_add_level_unlocks"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("materials", sa.Column("material_type", sa.String(length=50), nullable=False, server_default="lesson"))
    op.add_column("materials", sa.Column("status", sa.String(length=30), nullable=False, server_default="published"))
    op.create_index("ix_materials_material_type", "materials", ["material_type"], unique=False)
    op.create_index("ix_materials_status", "materials", ["status"], unique=False)

    op.create_table(
        "material_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_material_blocks_material_id", "material_blocks", ["material_id"], unique=False)
    op.create_index("ix_material_blocks_block_type", "material_blocks", ["block_type"], unique=False)
    op.create_index("ix_material_blocks_order_index", "material_blocks", ["order_index"], unique=False)

    op.create_table(
        "material_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("file_url", sa.String(length=1000), nullable=False),
        sa.Column("file_kind", sa.String(length=50), nullable=False, server_default="other"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_downloadable", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_material_attachments_material_id", "material_attachments", ["material_id"], unique=False)
    op.create_index("ix_material_attachments_file_kind", "material_attachments", ["file_kind"], unique=False)
    op.create_index("ix_material_attachments_order_index", "material_attachments", ["order_index"], unique=False)

    op.alter_column("materials", "material_type", server_default=None)
    op.alter_column("materials", "status", server_default=None)


def downgrade():
    op.drop_index("ix_material_attachments_order_index", table_name="material_attachments")
    op.drop_index("ix_material_attachments_file_kind", table_name="material_attachments")
    op.drop_index("ix_material_attachments_material_id", table_name="material_attachments")
    op.drop_table("material_attachments")

    op.drop_index("ix_material_blocks_order_index", table_name="material_blocks")
    op.drop_index("ix_material_blocks_block_type", table_name="material_blocks")
    op.drop_index("ix_material_blocks_material_id", table_name="material_blocks")
    op.drop_table("material_blocks")

    op.drop_index("ix_materials_status", table_name="materials")
    op.drop_index("ix_materials_material_type", table_name="materials")
    op.drop_column("materials", "status")
    op.drop_column("materials", "material_type")
