from sqlalchemy import Table, Column, Integer, ForeignKey

from app.db.session import Base


material_test_links = Table(
    "material_test_links",
    Base.metadata,
    Column("material_id", Integer, ForeignKey("materials.id", ondelete="CASCADE"), primary_key=True),
    Column("test_id", Integer, ForeignKey("tests.id", ondelete="CASCADE"), primary_key=True),
)
