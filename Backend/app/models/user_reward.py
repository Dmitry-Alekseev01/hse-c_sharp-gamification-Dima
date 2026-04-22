from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class UserReward(Base):
    __tablename__ = "user_rewards"
    __table_args__ = (
        UniqueConstraint("user_id", "reward_definition_id", name="uq_user_reward_user_definition"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reward_definition_id = Column(
        Integer,
        ForeignKey("reward_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type = Column(String(50), nullable=False, index=True)
    source_ref = Column(String(120), nullable=True)
    earned_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    user = relationship("User", back_populates="rewards", lazy="selectin")
    reward_definition = relationship("RewardDefinition", back_populates="user_rewards", lazy="selectin")
