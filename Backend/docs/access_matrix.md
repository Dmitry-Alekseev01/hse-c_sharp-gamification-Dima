# Backend Access Matrix

This document describes the role policy introduced in Batch 1 for user-scoped analytics access.

## Roles

- `admin`: full access to all users.
- `teacher`: access to self and students from teacher-managed groups.
- `user`: access to self only.

## User-Scoped Analytics Endpoints

- `GET /api/v1/analytics/user/{user_id}`
- `GET /api/v1/analytics/user/{user_id}/progress`
- `GET /api/v1/analytics/user/{user_id}/performance`
- `GET /api/v1/analytics/user/{user_id}/achievements`
- `GET /api/v1/analytics/user/{user_id}/points-ledger`

## Effective Policy

- `admin`:
  - can read any `user_id`.
- `teacher`:
  - can read own `user_id`.
  - can read `user_id` only if the user is in at least one group managed by this teacher.
  - cannot read unrelated users.
- `user`:
  - can read only own `user_id`.

## Implementation Note

The policy is centralized in:

- `app/api/v1/access.py`
  - `ensure_teacher_or_admin_can_access_user(...)`

Routers now call the centralized helper instead of duplicating role checks.
