# Backend Access Matrix

This document describes the role policy for user-scoped analytics access.

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

## Admin Panel Role Matrix

`AdminOnlyAuthProvider` allows admin-panel login for roles:

- `admin`
- `teacher`

### Views Available To `teacher`

- `Materials` (CRUD, only own records by `author_id`)
- `Material Blocks` (CRUD, only for own materials)
- `Material Attachments` (CRUD, only for own materials)
- `Tests` (CRUD, only own records by `author_id`)
- `Questions` (CRUD, only for own tests)
- `Choices` (CRUD, only for own tests)
- `Study Groups` (CRUD, only own records by `teacher_id`)
- `Group Memberships` (CRUD, only for own groups)

### Views Restricted To `admin` Only

- `Users` (read-only)
- `Levels`
- `Analytics`
- `Test Attempts`
- `Answers`
- `Points Ledger`
- `User Achievements`
- `User Rewards`
- `Reward Definitions`
- `Unlock Rules`
- `Challenges`
- `Challenge Progress`
- `Challenge Claims`
- `AI Jobs`
- `Seasons`
- `Leaderboard Snapshots`

### Additional Guardrails

- Teacher cannot assign foreign ownership during create/edit in owner-scoped views.
- Teacher cannot link foreign materials to tests in admin form validation.
