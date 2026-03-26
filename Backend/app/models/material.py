from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.associations import material_test_links

class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False, index=True)
    description = Column(Text, nullable=True)
    content_text = Column(Text, nullable=False, default="")
    content_url = Column(String(1000), nullable=True)
    video_url = Column(String(1000), nullable=True)
    published_at = Column(DateTime, server_default=func.now(), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # relation to User.author <-> User.materials
    author = relationship(
        "User",
        back_populates="materials",
        lazy="selectin",
    )

    tests = relationship(
        "Test",
        secondary=material_test_links,
        back_populates="materials",
        lazy="selectin",
    )

    @property
    def related_test_ids(self) -> list[int]:
        return [test.id for test in self.tests]
