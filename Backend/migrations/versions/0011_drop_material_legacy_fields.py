"""drop legacy material content fields

Revision ID: 0011_drop_material_legacy_fields
Revises: 0010_material_content_units
Create Date: 2026-04-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_drop_material_legacy_fields"
down_revision = "0010_material_content_units"
branch_labels = None
depends_on = None


def upgrade():
    # Backfill legacy text into blocks before dropping columns.
    op.execute(
        """
        INSERT INTO material_blocks (material_id, block_type, title, body, url, order_index)
        SELECT
            m.id,
            'text',
            'Основной текст',
            m.content_text,
            NULL,
            COALESCE((SELECT MAX(mb.order_index) + 1 FROM material_blocks mb WHERE mb.material_id = m.id), 0)
        FROM materials m
        WHERE m.content_text IS NOT NULL
          AND btrim(m.content_text) <> ''
          AND NOT EXISTS (
              SELECT 1
              FROM material_blocks mb
              WHERE mb.material_id = m.id
                AND mb.block_type = 'text'
                AND COALESCE(mb.body, '') = m.content_text
          )
        """
    )

    op.execute(
        """
        INSERT INTO material_blocks (material_id, block_type, title, body, url, order_index)
        SELECT
            m.id,
            'documentation_link',
            'Документация',
            NULL,
            m.content_url,
            COALESCE((SELECT MAX(mb.order_index) + 1 FROM material_blocks mb WHERE mb.material_id = m.id), 0)
        FROM materials m
        WHERE m.content_url IS NOT NULL
          AND btrim(m.content_url) <> ''
          AND NOT EXISTS (
              SELECT 1
              FROM material_blocks mb
              WHERE mb.material_id = m.id
                AND mb.block_type = 'documentation_link'
                AND COALESCE(mb.url, '') = m.content_url
          )
        """
    )

    op.execute(
        """
        INSERT INTO material_blocks (material_id, block_type, title, body, url, order_index)
        SELECT
            m.id,
            'video_link',
            'Видеозапись',
            NULL,
            m.video_url,
            COALESCE((SELECT MAX(mb.order_index) + 1 FROM material_blocks mb WHERE mb.material_id = m.id), 0)
        FROM materials m
        WHERE m.video_url IS NOT NULL
          AND btrim(m.video_url) <> ''
          AND NOT EXISTS (
              SELECT 1
              FROM material_blocks mb
              WHERE mb.material_id = m.id
                AND mb.block_type = 'video_link'
                AND COALESCE(mb.url, '') = m.video_url
          )
        """
    )

    op.drop_column("materials", "video_url")
    op.drop_column("materials", "content_url")
    op.drop_column("materials", "content_text")


def downgrade():
    op.add_column("materials", sa.Column("content_text", sa.Text(), nullable=False, server_default=""))
    op.add_column("materials", sa.Column("content_url", sa.String(length=1000), nullable=True))
    op.add_column("materials", sa.Column("video_url", sa.String(length=1000), nullable=True))

    op.execute(
        """
        UPDATE materials m
        SET content_text = COALESCE((
            SELECT mb.body
            FROM material_blocks mb
            WHERE mb.material_id = m.id
              AND mb.block_type = 'text'
            ORDER BY mb.order_index ASC, mb.id ASC
            LIMIT 1
        ), '')
        """
    )
    op.execute(
        """
        UPDATE materials m
        SET content_url = (
            SELECT mb.url
            FROM material_blocks mb
            WHERE mb.material_id = m.id
              AND mb.block_type = 'documentation_link'
            ORDER BY mb.order_index ASC, mb.id ASC
            LIMIT 1
        )
        """
    )
    op.execute(
        """
        UPDATE materials m
        SET video_url = (
            SELECT mb.url
            FROM material_blocks mb
            WHERE mb.material_id = m.id
              AND mb.block_type = 'video_link'
            ORDER BY mb.order_index ASC, mb.id ASC
            LIMIT 1
        )
        """
    )

    op.alter_column("materials", "content_text", server_default=None)
