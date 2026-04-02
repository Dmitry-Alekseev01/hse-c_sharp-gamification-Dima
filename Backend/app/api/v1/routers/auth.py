# app/api/v1/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.user import UserRead, UserCreate
from app.schemas.token import TokenRead, LoginRequest
from app.repositories import auth_repo
from app.core.security import create_access_token, get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/token", response_model=TokenRead)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await auth_repo.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    access_token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=TokenRead)
async def login_with_json(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_repo.authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    access_token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    from app.repositories.user_repo import get_user_by_username
    if await get_user_by_username(db, payload.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    user = await auth_repo.create_user(db, payload.username, payload.password, payload.full_name)
    return user


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
