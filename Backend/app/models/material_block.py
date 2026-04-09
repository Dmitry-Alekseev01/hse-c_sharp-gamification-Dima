from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class MaterialBlock(Base):
    __tablename__ = "material_blocks"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    block_type = Column(String(50), nullable=False, index=True)
    title = Column(String(300), nullable=True)
    body = Column(Text, nullable=True)
    url = Column(String(1000), nullable=True)
    order_index = Column(Integer, nullable=False, default=0, index=True)

    material = relationship("Material", back_populates="blocks", lazy="selectin")
