from __future__ import annotations

from typing import Any


def serialize_group_detail(
    group: Any,
    *,
    member_user_id: int | None = None,
) -> dict[str, Any]:
    """
    Serialize StudyGroup for API responses.

    If member_user_id is provided, members are filtered to that participant only.
    This is used by /groups/my to return membership-scoped view for the caller.
    """
    memberships = list(getattr(group, "memberships", []) or [])
    if member_user_id is not None:
        memberships = [membership for membership in memberships if int(membership.user_id) == int(member_user_id)]

    return {
        "id": group.id,
        "name": group.name,
        "teacher_id": group.teacher_id,
        "members": [
            {
                "user_id": membership.user_id,
                "username": membership.user.username if membership.user else "",
                "full_name": membership.user.full_name if membership.user else None,
            }
            for membership in memberships
        ],
    }
