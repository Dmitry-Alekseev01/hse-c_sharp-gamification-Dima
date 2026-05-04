from datetime import datetime

import pytest

from app.core import security
from app.models.user import User


def test_build_user_principal_preserves_created_at_from_cached_payload():
    created_at = datetime(2026, 5, 4, 12, 30, 0)

    user = security._build_user_principal(
        {
            "id": 1,
            "username": "cached_profile@example.com",
            "role": "user",
            "full_name": "Cached Profile",
            "password_hash": "hash",
            "created_at": created_at.isoformat(),
        }
    )

    assert user.created_at == created_at


@pytest.mark.asyncio
async def test_set_cached_auth_payload_includes_created_at(monkeypatch):
    created_at = datetime(2026, 5, 4, 12, 30, 0)
    user = User(
        id=1,
        username="cached_profile@example.com",
        role="user",
        full_name="Cached Profile",
        password_hash="hash",
        created_at=created_at,
    )
    captured: dict[str, object] = {}

    async def fake_cache_set(key, value, ttl=None):
        captured["key"] = key
        captured["value"] = value
        captured["ttl"] = ttl

    monkeypatch.setattr(security, "cache_set", fake_cache_set)

    await security._set_cached_auth_payload(username=user.username, user=user, pwdv="pwdv")

    payload = captured["value"]
    assert isinstance(payload, dict)
    assert payload["created_at"] == created_at.isoformat()
