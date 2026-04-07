from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.associations import material_test_links

class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False, index=True)
    material_type = Column(String(50), nullable=False, default="lesson", index=True)
    status = Column(String(30), nullable=False, default="published", index=True)
    description = Column(Text, nullable=True)
    published_at = Column(DateTime, server_default=func.now(), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    required_level_id = Column(Integer, ForeignKey("levels.id"), nullable=True, index=True)

    # relation to User.author <-> User.materials
    author = relationship(
        "User",
        back_populates="materials",
        lazy="selectin",
    )

    required_level = relationship(
        "Level",
        back_populates="materials",
        lazy="selectin",
    )

    tests = relationship(
        "Test",
        secondary=material_test_links,
        back_populates="materials",
        lazy="selectin",
    )

    blocks = relationship(
        "MaterialBlock",
        back_populates="material",
        cascade="all, delete-orphan",
        order_by="MaterialBlock.order_index",
        lazy="selectin",
    )

    attachments = relationship(
        "MaterialAttachment",
        back_populates="material",
        cascade="all, delete-orphan",
        order_by="MaterialAttachment.order_index",
        lazy="selectin",
    )

    @property
    def related_test_ids(self) -> list[int]:
        return [test.id for test in self.tests]
