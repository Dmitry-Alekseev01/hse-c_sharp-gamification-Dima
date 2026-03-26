from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime, String, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="in_progress")
    score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", lazy="selectin")
    test = relationship("Test", back_populates="attempts", lazy="selectin")
    answers = relationship("Answer", back_populates="attempt", lazy="selectin")
