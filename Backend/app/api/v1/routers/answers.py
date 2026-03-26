from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_user, require_roles
from app.schemas.answer import AnswerCreate, AnswerRead, PendingOpenAnswerRead
from app.schemas.grading import GradeRequest
from app.services.answer_service import submit_answer, manual_grade_open_answer as manual_grade_open_answer_service
from app.repositories import answer_repo, test_attempt_repo
from app.models.answer import Answer as AnswerModel
from app.models.user import User

router = APIRouter()


@router.get("/pending/open", response_model=List[PendingOpenAnswerRead], status_code=status.HTTP_200_OK)
async def list_pending_open_answers(
    test_id: Optional[int] = None,
    user_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    pending_answers = await answer_repo.get_pending_open_answers(
        db,
        limit=limit,
        offset=offset,
        test_id=test_id,
        user_id=user_id,
    )
    return [
        {
            "id": answer.id,
            "user_id": answer.user_id,
            "student_username": answer.user.username if answer.user else "",
            "test_id": answer.test_id,
            "attempt_id": answer.attempt_id,
            "question_id": answer.question_id,
            "question_text": answer.question.text if answer.question else "",
            "answer_payload": answer.answer_payload,
            "submitted_at": answer.created_at,
            "created_at": answer.created_at,
        }
        for answer in pending_answers
    ]


@router.post("/", response_model=AnswerRead, status_code=status.HTTP_201_CREATED)
async def create_answer(
    payload: AnswerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit an answer. Uses the orchestration service which:
      - records the answer
      - auto-grades MCQ
      - updates analytics
      - enqueues open answers for manual grading
      - invalidates caches (best-effort)
    """
    if payload.attempt_id is not None:
        attempt = await test_attempt_repo.get_attempt(db, payload.attempt_id)
        if attempt is None or attempt.user_id != current_user.id or attempt.test_id != payload.test_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid attempt_id")
    ans = await submit_answer(
        db,
        current_user.id,
        payload.test_id,
        payload.question_id,
        payload.answer_payload,
        attempt_id=payload.attempt_id,
    )
    if not ans:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to submit answer")
    return ans


@router.get("/{answer_id}", response_model=AnswerRead, status_code=status.HTTP_200_OK)
async def get_answer(
    answer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = await db.get(AnswerModel, answer_id)
    if not a:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
    if current_user.id != a.user_id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return a


@router.get("/test/{test_id}", response_model=List[AnswerRead], status_code=status.HTTP_200_OK)
async def get_answers_for_test(
    test_id: int,
    user_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    answers = await answer_repo.get_answers_for_test(db, test_id=test_id, limit=limit, offset=offset)
    if current_user.role not in {"teacher", "admin"}:
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        answers = [a for a in answers if a.user_id == current_user.id]
    elif user_id is not None:
        answers = [a for a in answers if a.user_id == user_id]
    return answers


@router.post("/{answer_id}/grade", response_model=AnswerRead, status_code=status.HTTP_200_OK)
async def manual_grade_answer(
    answer_id: int,
    payload: GradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    """
    Manually grade an open answer and update analytics for the answer author.
    """
    try:
        graded = await manual_grade_open_answer_service(
            db,
            answer_id=answer_id,
            grader_id=current_user.id,
            score=payload.score,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return graded
