from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.associations import material_test_links

class Test(Base):
    __tablename__ = "tests"
    __test__ = False 

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    time_limit_minutes = Column(Integer, nullable=True)
    max_score = Column(Integer, nullable=True)
    published = Column(Boolean, default=False, nullable=False)
    published_at = Column(DateTime, server_default=func.now(), nullable=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=True, index=True)
    deadline = Column(DateTime, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    required_level_id = Column(Integer, ForeignKey("levels.id"), nullable=True, index=True)

    author = relationship(
        "User",
        back_populates="tests_authored",
        lazy="selectin",
    )

    required_level = relationship(
        "Level",
        back_populates="tests",
        lazy="selectin",
    )

    # Test.questions <-> Question.test
    questions = relationship(
        "Question",
        back_populates="test",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    materials = relationship(
        "Material",
        secondary=material_test_links,
        back_populates="tests",
        lazy="selectin",
    )

    attempts = relationship(
        "TestAttempt",
        back_populates="test",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def material_ids(self) -> list[int]:
        return [material.id for material in self.materials]
