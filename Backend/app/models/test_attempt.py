from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import relationship

from app.db.session import Base


class TestAttempt(Base):
    __tablename__ = "test_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed')",
            name="ck_test_attempts_status_valid",
        ),
        Index(
            "ux_test_attempts_active_user_test",
            "user_id",
            "test_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="in_progress")
    score = Column(Float, nullable=True)
    manual_score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", lazy="selectin")
    test = relationship("Test", back_populates="attempts", lazy="selectin")
    answers = relationship("Answer", back_populates="attempt", lazy="selectin")
