# app/core/security.py
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.models.user import User  # type: ignore
from app.repositories.user_repo import get_user_by_username  # existing repo
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.cache.redis_cache import delete as cache_delete, get as cache_get, set as cache_set

# build CryptContext using settings.hash_schemes
_hash_schemes = [s.strip() for s in settings.hash_schemes.split(",") if s.strip()]
if not _hash_schemes:
    _hash_schemes = ["bcrypt"]

pwd_context = CryptContext(schemes=_hash_schemes, deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=settings.oauth2_token_url)
AUTH_USER_CACHE_TTL_SECONDS = 60


def _auth_user_cache_key(username: str) -> str:
    return f"auth:user:{username}"


async def invalidate_auth_user_cache(*usernames: str) -> None:
    keys = [_auth_user_cache_key(username) for username in usernames if username]
    if not keys:
        return
    try:
        await cache_delete(*keys)
    except Exception:
        # Cache must not break auth mutations.
        pass


def _build_user_principal(payload: dict) -> User:
    return User(
        id=int(payload["id"]),
        username=str(payload["username"]),
        role=str(payload["role"]),
        full_name=payload.get("full_name"),
        password_hash=str(payload.get("password_hash") or ""),
    )


async def _get_cached_auth_payload(username: str) -> dict | None:
    try:
        cached = await cache_get(_auth_user_cache_key(username))
    except Exception:
        return None
    return cached if isinstance(cached, dict) else None


async def _set_cached_auth_payload(
    *,
    username: str,
    user: User,
    pwdv: str,
) -> None:
    payload = {
        "id": int(user.id),
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
        "password_hash": user.password_hash,
        "pwdv": pwdv,
    }
    try:
        await cache_set(_auth_user_cache_key(username), payload, ttl=AUTH_USER_CACHE_TTL_SECONDS)
    except Exception:
        # Cache write failure should not break auth path.
        pass


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def build_password_version(password_hash: str) -> str:
    digest = hashlib.sha256(password_hash.encode("utf-8")).hexdigest()
    return digest[:24]


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.get_jwt_secret_key(), algorithm=settings.algorithm)
    return encoded_jwt


def require_roles(*allowed_roles: str):
    normalized_roles = {role.lower() for role in allowed_roles}

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.lower() not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.get_jwt_secret_key(), algorithms=[settings.algorithm])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    token_pwdv = payload.get("pwdv")
    if not isinstance(token_pwdv, str):
        raise credentials_exception

    cached_payload = await _get_cached_auth_payload(username)
    if cached_payload is not None:
        cached_pwdv = cached_payload.get("pwdv")
        if isinstance(cached_pwdv, str) and hmac.compare_digest(token_pwdv, cached_pwdv):
            return _build_user_principal(cached_payload)

    user = await get_user_by_username(db, username)
    if user is None:
        raise credentials_exception
    current_pwdv = build_password_version(user.password_hash)
    if not hmac.compare_digest(token_pwdv, current_pwdv):
        raise credentials_exception

    await _set_cached_auth_payload(username=username, user=user, pwdv=current_pwdv)
    return user
