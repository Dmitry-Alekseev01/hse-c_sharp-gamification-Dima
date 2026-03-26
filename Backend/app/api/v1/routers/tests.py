from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_user, require_roles
from app.models.user import User
from app.schemas.test_ import TestCreate, TestRead, TestUpdate
from app.schemas.analytics import TestSummary
from app.schemas.test_attempt import TestAttemptRead
from app.repositories import test_repo, test_attempt_repo

router = APIRouter()


@router.get("/", response_model=List[TestRead], status_code=status.HTTP_200_OK)
async def list_tests(
    published_only: bool = True,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not published_only and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    items = await test_repo.list_tests(db, published_only=published_only, limit=limit)
    return items


@router.get("/{test_id}", response_model=TestRead, status_code=status.HTTP_200_OK)
async def get_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = await test_repo.get_test(db, test_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if not t.published and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return t


@router.post("/", response_model=TestRead, status_code=status.HTTP_201_CREATED)
async def create_test(
    payload: TestCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    test = await test_repo.create_test(
        db,
        title=payload.title,
        description=payload.description,
        time_limit_minutes=payload.time_limit_minutes,
        max_score=payload.max_score,
        published=payload.published,
        material_id=payload.material_id,
        material_ids=payload.material_ids,
        deadline=payload.deadline,
    )
    return test


@router.patch("/{test_id}", response_model=TestRead, status_code=status.HTTP_200_OK)
async def update_test(
    test_id: int,
    payload: TestUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    test = await test_repo.update_test(db, test_id, **payload.model_dump(exclude_unset=True))
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return test


@router.post("/{test_id}/publish", response_model=TestRead, status_code=status.HTTP_200_OK)
async def publish_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    test = await test_repo.update_test(db, test_id, published=True)
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return test


@router.post("/{test_id}/hide", response_model=TestRead, status_code=status.HTTP_200_OK)
async def hide_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    test = await test_repo.update_test(db, test_id, published=False)
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return test


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    deleted = await test_repo.delete_test(db, test_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return {}


@router.get("/{test_id}/summary", response_model=TestSummary, status_code=status.HTTP_200_OK)
async def test_summary(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = await test_repo.get_test(db, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if not test.published and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    summary = await test_repo.get_test_summary(db, test_id)
    return summary


@router.post("/{test_id}/attempts/start", response_model=TestAttemptRead, status_code=status.HTTP_201_CREATED)
async def start_test_attempt(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = await test_repo.get_test(db, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if not test.published and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    existing_attempt = await test_attempt_repo.get_active_attempt(db, current_user.id, test_id)
    if existing_attempt is not None:
        return existing_attempt
    return await test_attempt_repo.create_attempt(db, current_user.id, test_id)


@router.get("/{test_id}/attempts/me", response_model=List[TestAttemptRead], status_code=status.HTTP_200_OK)
async def list_my_test_attempts(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = await test_repo.get_test(db, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if not test.published and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return await test_attempt_repo.list_attempts_for_user(db, current_user.id, test_id=test_id)


@router.post("/attempts/{attempt_id}/complete", response_model=TestAttemptRead, status_code=status.HTTP_200_OK)
async def complete_test_attempt(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = await test_attempt_repo.get_attempt(db, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != current_user.id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if attempt.status == "completed":
        return attempt
    return await test_attempt_repo.complete_attempt(db, attempt)
