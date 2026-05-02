"""compatibility no-op for removed streak wallet feature

Revision ID: 0018_add_user_streak_wallets
Revises: 0017_contract_hardening
Create Date: 2026-04-22 23:10:00.000000
"""

revision = "0018_add_user_streak_wallets"
down_revision = "0017_contract_hardening"
branch_labels = None
depends_on = None


def upgrade():
    # Feature removed. Keep revision as no-op for migration chain compatibility.
    pass


def downgrade():
    pass
