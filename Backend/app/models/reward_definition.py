from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class RewardDefinition(Base):
    __tablename__ = "reward_definitions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    reward_type = Column(String(50), nullable=False, default="badge", index=True)
    payload_json = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    unlock_rules = relationship(
        "UnlockRule",
        back_populates="reward_definition",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    user_rewards = relationship(
        "UserReward",
        back_populates="reward_definition",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
