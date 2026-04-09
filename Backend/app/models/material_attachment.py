from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class MaterialAttachment(Base):
    __tablename__ = "material_attachments"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    file_url = Column(String(1000), nullable=False)
    file_kind = Column(String(50), nullable=False, default="other", index=True)
    order_index = Column(Integer, nullable=False, default=0, index=True)
    is_downloadable = Column(Boolean, nullable=False, default=True)

    material = relationship("Material", back_populates="attachments", lazy="selectin")
