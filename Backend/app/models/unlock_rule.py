from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class UnlockRule(Base):
    __tablename__ = "unlock_rules"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('achievement', 'challenge', 'level')",
            name="ck_unlock_rules_source_type_valid",
        ),
        UniqueConstraint(
            "reward_definition_id",
            "source_type",
            "source_code",
            "min_level_required",
            name="uq_unlock_rule_identity",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    reward_definition_id = Column(
        Integer,
        ForeignKey("reward_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type = Column(String(50), nullable=False, index=True)
    source_code = Column(String(100), nullable=True, index=True)
    min_level_required = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    reward_definition = relationship("RewardDefinition", back_populates="unlock_rules", lazy="selectin")
