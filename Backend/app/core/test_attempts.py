from datetime import UTC, datetime
from typing import Literal, TypedDict

ProgressState = Literal["not_started", "in_progress", "completed"]
AttemptState = Literal["can_start", "can_resume", "blocked"]
AttemptBlockReason = Literal["no_attempts", "deadline_passed", "time_limit_exceeded", "level_locked", "test_unpublished"]


class AttemptViewState(TypedDict):
    progress_state: ProgressState
    user_status: ProgressState
    attempt_state: AttemptState
    can_start: bool
    can_resume: bool
    block_reason: AttemptBlockReason | None
    max_attempts: int
    completed_attempts: int
    remaining_attempts: int
    has_active_attempt: bool


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def is_deadline_passed(deadline: datetime | None, now: datetime | None = None) -> bool:
    if deadline is None:
        return False
    return (now or utcnow_naive()) >= deadline


def build_attempt_view_state(
    *,
    max_attempts: int | None,
    completed_attempts: int,
    has_active_attempt: bool,
    deadline_passed: bool = False,
    forced_block_reason: AttemptBlockReason | None = None,
) -> AttemptViewState:
    normalized_max_attempts = max(int(max_attempts or 1), 1)
    normalized_completed_attempts = max(int(completed_attempts or 0), 0)
    remaining_attempts = max(normalized_max_attempts - normalized_completed_attempts, 0)

    if has_active_attempt:
        progress_state: ProgressState = "in_progress"
    elif normalized_completed_attempts > 0:
        progress_state = "completed"
    else:
        progress_state = "not_started"

    block_reason: AttemptBlockReason | None = forced_block_reason
    attempt_state: AttemptState
    can_start = False
    can_resume = False

    if block_reason is not None:
        attempt_state = "blocked"
    elif has_active_attempt and not deadline_passed:
        attempt_state = "can_resume"
        can_resume = True
    elif deadline_passed:
        attempt_state = "blocked"
        block_reason = "deadline_passed"
    elif remaining_attempts > 0:
        attempt_state = "can_start"
        can_start = True
    else:
        attempt_state = "blocked"
        block_reason = "no_attempts"

    # Human-readable status for UI labels.
    # Action buttons should rely on can_start/can_resume/attempt_state.
    if has_active_attempt:
        user_status: ProgressState = "in_progress"
    elif normalized_completed_attempts > 0:
        user_status = "completed"
    else:
        user_status = "not_started"

    return {
        "progress_state": progress_state,
        "user_status": user_status,
        "attempt_state": attempt_state,
        "can_start": can_start,
        "can_resume": can_resume,
        "block_reason": block_reason,
        "max_attempts": normalized_max_attempts,
        "completed_attempts": normalized_completed_attempts,
        "remaining_attempts": remaining_attempts,
        "has_active_attempt": has_active_attempt,
    }
