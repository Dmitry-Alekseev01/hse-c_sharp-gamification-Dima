from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.level import LevelRead

class AnalyticsRead(BaseModel):
    user_id: int
    total_points: float
    tests_taken: int
    last_active: datetime | None
    streak_days: int
    current_level_id: int | None

    model_config = ConfigDict(from_attributes=True)

class LeaderboardEntry(BaseModel):
    user_id: int
    username: str
    total_points: float

    model_config = ConfigDict(from_attributes=True)

class TestSummary(BaseModel):
    test_id: int
    total_questions: int
    total_attempts: int
    completed_attempts: int
    avg_score: float | None
    avg_time_seconds: float | None

    model_config = ConfigDict(from_attributes=True)

class QuestionStats(BaseModel):
    question_id: int
    attempts: int
    avg_score: float | None
    correct_count: int
    correct_rate: float | None
    distinct_users: int

    model_config = ConfigDict(from_attributes=True)


class AnalyticsOverviewRead(BaseModel):
    total_users: int
    total_materials: int
    total_tests: int
    published_tests: int
    total_questions: int
    total_answers: int
    completed_attempts: int
    pending_open_answers: int
    active_users_7d: int


class UserPerformanceRead(BaseModel):
    user_id: int
    username: str
    full_name: str | None
    total_points: float
    tests_taken: int
    streak_days: int
    current_level_id: int | None
    completed_attempts: int
    avg_score: float | None
    avg_time_seconds: float | None
    last_active: datetime | None


class GamificationBadgeRead(BaseModel):
    code: str
    title: str
    description: str
    reward: str | None
    earned: bool


class UserAchievementRead(BaseModel):
    code: str
    title: str
    description: str
    reward: str | None
    criteria_type: str
    threshold_value: int
    earned: bool
    earned_at: datetime | None


class PointsLedgerEntryRead(BaseModel):
    id: int
    user_id: int
    delta: float
    reason_code: str
    source_type: str | None
    source_id: int | None
    idempotency_key: str | None
    metadata: dict[str, object] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metadata", "metadata_json"),
    )
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PointsLedgerPageRead(BaseModel):
    items: list[PointsLedgerEntryRead]
    limit: int
    offset: int


class UserRewardRead(BaseModel):
    id: int
    code: str
    title: str
    description: str | None
    reward_type: str
    payload: dict[str, object]
    source_type: str
    source_ref: str | None
    earned_at: datetime


class UserUnlockRead(BaseModel):
    reward_code: str
    reward_title: str
    source_type: str
    source_code: str | None
    min_level_required: int | None
    is_eligible: bool
    is_unlocked: bool
    earned_at: datetime | None


class UserGamificationProgressRead(BaseModel):
    user_id: int
    username: str
    total_points: float
    streak_days: int
    completed_attempts: int
    current_level: LevelRead | None
    next_level: LevelRead | None
    points_to_next_level: float
    progress_percent: float
    earned_badges_count: int
    badges: list[GamificationBadgeRead]


class LearningTestResultRead(BaseModel):
    test_id: int
    title: str
    deadline: datetime | None
    user_status: Literal["not_started", "in_progress", "completed"]
    has_active_attempt: bool
    completed_attempts: int
    remaining_attempts: int
    score_percent: float | None
    score_value: float | None
    max_score: float | None
    completed_at: datetime | None


class LearningDashboardRead(BaseModel):
    user_id: int
    username: str
    total_points: float
    streak_days: int
    total_materials: int
    total_tests: int
    completed_tests: int
    tests_with_score: int
    average_score_percent: float
    current_level: LevelRead | None
    next_level: LevelRead | None
    points_to_next_level: float
    progress_percent: float
    badges: list[GamificationBadgeRead]
    test_results: list[LearningTestResultRead]


class GroupAnalyticsSummaryRead(BaseModel):
    group_id: int
    members_count: int
    active_members_7d: int
    total_points: float
    avg_points: float | None
    completed_attempts: int
    avg_completed_attempts: float | None
    avg_score: float | None
    avg_time_seconds: float | None


class ScoreBucketRead(BaseModel):
    label: str
    count: int


class UserBriefRead(BaseModel):
    user_id: int
    username: str


class TestAverageScoreRead(BaseModel):
    test_id: int
    avg_score: float | None


class TestAverageTimeRead(BaseModel):
    test_id: int
    avg_time_seconds: float | None


class DailyActiveRead(BaseModel):
    day: datetime
    dau: int


class RetentionEntryRead(BaseModel):
    user_id: int
    active_days: list[datetime | None]


class ChallengePeriodType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class ChallengeEventType(str, Enum):
    ANSWER_SUBMITTED = "answer_submitted"
    ATTEMPT_COMPLETED = "attempt_completed"
    STREAK_DAY = "streak_day"


class ChallengeCreate(BaseModel):
    code: str
    title: str
    description: str | None = None
    period_type: ChallengePeriodType
    event_type: ChallengeEventType
    target_value: int
    reward_points: float = 0.0
    is_active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class ChallengeUpdate(BaseModel):
    code: str | None = None
    title: str | None = None
    description: str | None = None
    period_type: ChallengePeriodType | None = None
    event_type: ChallengeEventType | None = None
    target_value: int | None = None
    reward_points: float | None = None
    is_active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class ChallengeRead(BaseModel):
    id: int
    code: str
    title: str
    description: str | None
    period_type: ChallengePeriodType
    event_type: ChallengeEventType
    target_value: int
    reward_points: float
    is_active: bool
    starts_at: datetime | None
    ends_at: datetime | None
    created_by: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserChallengeProgressRead(BaseModel):
    challenge_id: int
    code: str
    title: str
    description: str | None
    period_type: ChallengePeriodType
    event_type: ChallengeEventType
    target_value: int
    reward_points: float
    period_key: str
    progress_value: int
    is_completed: bool
    is_claimed: bool
    completed_at: datetime | None
    claimed_at: datetime | None


class ChallengeClaimRead(BaseModel):
    challenge_id: int
    period_key: str
    reward_points: float
    claimed_at: datetime


class SeasonCreate(BaseModel):
    code: str
    title: str
    starts_at: datetime
    ends_at: datetime
    is_active: bool = True


class SeasonUpdate(BaseModel):
    code: str | None = None
    title: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None


class SeasonRead(BaseModel):
    id: int
    code: str
    title: str
    starts_at: datetime
    ends_at: datetime
    is_active: bool
    created_by: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RewardDefinitionCreate(BaseModel):
    code: str
    title: str
    description: str | None = None
    reward_type: str = "badge"
    payload_json: dict[str, object] | None = None
    is_active: bool = True


class RewardDefinitionUpdate(BaseModel):
    code: str | None = None
    title: str | None = None
    description: str | None = None
    reward_type: str | None = None
    payload_json: dict[str, object] | None = None
    is_active: bool | None = None


class RewardDefinitionRead(BaseModel):
    id: int
    code: str
    title: str
    description: str | None
    reward_type: str
    payload_json: dict[str, object] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnlockRuleSourceType(str, Enum):
    ACHIEVEMENT = "achievement"
    CHALLENGE = "challenge"
    LEVEL = "level"


class UnlockRuleCreate(BaseModel):
    reward_definition_id: int
    source_type: UnlockRuleSourceType
    source_code: str | None = None
    min_level_required: int | None = None
    is_active: bool = True


class UnlockRuleUpdate(BaseModel):
    reward_definition_id: int | None = None
    source_type: UnlockRuleSourceType | None = None
    source_code: str | None = None
    min_level_required: int | None = None
    is_active: bool | None = None


class UnlockRuleRead(BaseModel):
    id: int
    reward_definition_id: int
    source_type: UnlockRuleSourceType
    source_code: str | None
    min_level_required: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AchievementCriteriaType(str, Enum):
    TOTAL_POINTS = "total_points"
    STREAK_DAYS = "streak_days"
    COMPLETED_ATTEMPTS = "completed_attempts"


class AchievementDefinitionCreate(BaseModel):
    code: str
    title: str
    description: str
    reward: str | None = None
    criteria_type: AchievementCriteriaType
    threshold_value: int
    is_active: bool = True


class AchievementDefinitionUpdate(BaseModel):
    code: str | None = None
    title: str | None = None
    description: str | None = None
    reward: str | None = None
    criteria_type: AchievementCriteriaType | None = None
    threshold_value: int | None = None
    is_active: bool | None = None


class AchievementDefinitionRead(BaseModel):
    id: int
    code: str
    title: str
    description: str
    reward: str | None
    criteria_type: AchievementCriteriaType
    threshold_value: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
