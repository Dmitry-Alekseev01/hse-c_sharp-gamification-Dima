# app/models/__init__.py
"""
Ensure all model modules are imported so SQLAlchemy sees every mapped class.
"""
from app.models import user  # noqa: F401
from app.models import level  # noqa: F401
from app.models import material  # noqa: F401
from app.models import test_  # noqa: F401
from app.models import question  # noqa: F401
from app.models import choice  # noqa: F401
from app.models import answer  # noqa: F401
from app.models import analytics  # noqa: F401
from app.models import associations  # noqa: F401
from app.models import test_attempt  # noqa: F401
from app.models import group  # noqa: F401
from app.models import material_block  # noqa: F401
from app.models import material_attachment  # noqa: F401
from app.models import ai_gamification_job  # noqa: F401
from app.models import achievement_definition  # noqa: F401
from app.models import user_achievement  # noqa: F401
from app.models import points_ledger  # noqa: F401
from app.models import challenge  # noqa: F401
from app.models import season  # noqa: F401
from app.models import reward_definition  # noqa: F401
from app.models import unlock_rule  # noqa: F401
from app.models import user_reward  # noqa: F401
