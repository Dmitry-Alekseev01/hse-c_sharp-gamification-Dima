from starlette_admin.contrib.sqla import ModelView

from app.models.ai_gamification_job import AIGamificationJob
from app.models.achievement_definition import AchievementDefinition
from app.models.analytics import Analytics
from app.models.answer import Answer
from app.models.challenge import Challenge, UserChallengeClaim, UserChallengeProgress
from app.models.choice import Choice
from app.models.group import GroupMembership, StudyGroup
from app.models.level import Level
from app.models.material import Material
from app.models.material_attachment import MaterialAttachment
from app.models.material_block import MaterialBlock
from app.models.points_ledger import PointsLedger
from app.models.question import Question
from app.models.reward_definition import RewardDefinition
from app.models.season import LeaderboardSnapshot, Season
from app.models.test_ import Test
from app.models.test_attempt import TestAttempt
from app.models.unlock_rule import UnlockRule
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.models.user_reward import UserReward

from .views_base import (
    AdminAuditedModelView,
    ReadOnlyAdminView,
    TeacherAccessibleModelView,
    TeacherOwnedByFieldModelView,
    TeacherScopedByTestReadOnlyView,
)
from .views_content import (
    ChoiceAdminView,
    GroupMembershipAdminView,
    LevelAdminView,
    MaterialAdminView,
    MaterialAttachmentAdminView,
    MaterialBlockAdminView,
    QuestionAdminView,
    StudyGroupAdminView,
    TestAdminView,
    UserReadOnlyView,
)
from .views_gamification import (
    AIGamificationJobReadOnlyView,
    AchievementDefinitionAdminView,
    ChallengeAdminView,
    LeaderboardSnapshotReadOnlyView,
    RewardDefinitionAdminView,
    SeasonAdminView,
    UnlockRuleAdminView,
    UserChallengeClaimReadOnlyView,
    UserChallengeProgressReadOnlyView,
)
from .views_observability import (
    AnalyticsReadOnlyView,
    AnswerReadOnlyView,
    PointsLedgerReadOnlyView,
    TestAttemptReadOnlyView,
    UserAchievementReadOnlyView,
    UserRewardReadOnlyView,
)


def get_admin_views() -> list[ModelView]:
    return [
        UserReadOnlyView(User),
        LevelAdminView(Level),
        MaterialAdminView(Material),
        MaterialBlockAdminView(MaterialBlock),
        MaterialAttachmentAdminView(MaterialAttachment),
        TestAdminView(Test),
        QuestionAdminView(Question),
        ChoiceAdminView(Choice),
        StudyGroupAdminView(StudyGroup),
        GroupMembershipAdminView(GroupMembership),
        AnalyticsReadOnlyView(Analytics),
        TestAttemptReadOnlyView(TestAttempt),
        AnswerReadOnlyView(Answer),
        PointsLedgerReadOnlyView(PointsLedger),
        UserAchievementReadOnlyView(UserAchievement),
        UserRewardReadOnlyView(UserReward),
        AchievementDefinitionAdminView(AchievementDefinition),
        RewardDefinitionAdminView(RewardDefinition),
        UnlockRuleAdminView(UnlockRule),
        ChallengeAdminView(Challenge),
        UserChallengeProgressReadOnlyView(UserChallengeProgress),
        UserChallengeClaimReadOnlyView(UserChallengeClaim),
        AIGamificationJobReadOnlyView(AIGamificationJob),
        SeasonAdminView(Season),
        LeaderboardSnapshotReadOnlyView(LeaderboardSnapshot),
    ]


__all__ = [
    "AdminAuditedModelView",
    "TeacherAccessibleModelView",
    "TeacherOwnedByFieldModelView",
    "ReadOnlyAdminView",
    "TeacherScopedByTestReadOnlyView",
    "UserReadOnlyView",
    "MaterialAdminView",
    "TestAdminView",
    "QuestionAdminView",
    "ChoiceAdminView",
    "MaterialBlockAdminView",
    "MaterialAttachmentAdminView",
    "LevelAdminView",
    "StudyGroupAdminView",
    "GroupMembershipAdminView",
    "AnalyticsReadOnlyView",
    "TestAttemptReadOnlyView",
    "AnswerReadOnlyView",
    "PointsLedgerReadOnlyView",
    "UserAchievementReadOnlyView",
    "UserRewardReadOnlyView",
    "RewardDefinitionAdminView",
    "AchievementDefinitionAdminView",
    "UnlockRuleAdminView",
    "ChallengeAdminView",
    "UserChallengeProgressReadOnlyView",
    "UserChallengeClaimReadOnlyView",
    "AIGamificationJobReadOnlyView",
    "SeasonAdminView",
    "LeaderboardSnapshotReadOnlyView",
    "get_admin_views",
]
