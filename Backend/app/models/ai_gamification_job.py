import json

from sqlalchemy import CheckConstraint, Column, Integer, String, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class AIGamificationJob(Base):
    __tablename__ = "ai_gamification_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'applied')",
            name="ck_ai_jobs_status_valid",
        ),
        CheckConstraint(
            "source_type IN ('material', 'question', 'raw_text')",
            name="ck_ai_jobs_source_type_valid",
        ),
        CheckConstraint(
            "target_level IS NULL OR target_level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_ai_jobs_target_level_valid",
        ),
        CheckConstraint(
            "style IS NULL OR style IN ('quest', 'mission', 'challenge', 'story')",
            name="ck_ai_jobs_style_valid",
        ),
        CheckConstraint(
            "tone IS NULL OR tone IN ('neutral', 'friendly', 'energetic')",
            name="ck_ai_jobs_tone_valid",
        ),
        CheckConstraint(
            "applied_target_type IS NULL OR applied_target_type IN ('material', 'question')",
            name="ck_ai_jobs_applied_target_type_valid",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(String(30), nullable=False, default="pending", index=True)
    source_type = Column(String(30), nullable=False, index=True)
    source_id = Column(Integer, nullable=True, index=True)
    raw_text = Column(Text, nullable=True)
    source_snapshot = Column(Text, nullable=True)

    target_level = Column(String(30), nullable=True)
    language = Column(String(16), nullable=False, default="ru")
    style = Column(String(30), nullable=True)
    tone = Column(String(30), nullable=True)
    constraints_json = Column(JSON, nullable=True)

    draft_json = Column(JSON, nullable=True)
    error_text = Column(Text, nullable=True)
    model = Column(String(120), nullable=True)
    provider = Column(String(120), nullable=True)
    usage_json = Column(JSON, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    applied_target_type = Column(String(30), nullable=True)
    applied_target_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    creator = relationship("User", lazy="selectin")

    @property
    def draft_preview_text(self) -> str | None:
        if not isinstance(self.draft_json, dict):
            return None
        try:
            return json.dumps(self.draft_json, ensure_ascii=False, indent=2)
        except Exception:
            return str(self.draft_json)
