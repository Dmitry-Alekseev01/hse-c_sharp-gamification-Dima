import time

from starlette.requests import Request
from starlette.responses import Response
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.exceptions import LoginFailed

from app.admin.mfa import split_password_and_totp, verify_totp_code
from app.cache.redis_cache import get_redis_client
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.repositories import auth_repo, user_repo


class _AdminSecurityBackendUnavailable(Exception):
    pass


class AdminOnlyAuthProvider(AuthProvider):
    session_user_id_key = "admin_user_id"
    session_username_key = "admin_username"

    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        del remember_me
        username = (username or "").strip()
        if not username or not password:
            raise LoginFailed("Invalid username or password")

        password, mfa_code = await self._extract_password_and_mfa_code(request, password)
        identifier = self._get_identifier(request)
        username_key = username.lower()

        try:
            security_client = await self._get_security_redis_client()
            if await self._is_login_temporarily_blocked(identifier, username_key, security_client):
                raise LoginFailed("Too many attempts. Try again later.")

            async with AsyncSessionLocal() as db:
                user = await auth_repo.authenticate_user(db, username, password)

            if user is None or str(user.role).lower() != "admin":
                await self._register_failed_attempt(identifier, username_key, security_client)
                raise LoginFailed("Invalid username or password")

            if settings.admin_mfa_enabled:
                is_mfa_ok = verify_totp_code(
                    secret=settings.admin_mfa_totp_secret or "",
                    code=mfa_code,
                    period_seconds=settings.admin_mfa_totp_period_seconds,
                    digits=settings.admin_mfa_totp_digits,
                    drift_windows=settings.admin_mfa_totp_drift_windows,
                )
                if not is_mfa_ok:
                    await self._register_failed_attempt(identifier, username_key, security_client)
                    raise LoginFailed("Invalid username or password")

            await self._clear_failed_attempts(identifier, username_key, security_client)
        except _AdminSecurityBackendUnavailable:
            raise LoginFailed("Admin login is temporarily unavailable")

        request.session.update(
            {
                self.session_user_id_key: int(user.id),
                self.session_username_key: str(user.username),
                "admin_role": str(user.role).lower(),
            }
        )
        return response

    async def is_authenticated(self, request: Request) -> bool:
        raw_user_id = request.session.get(self.session_user_id_key)
        if raw_user_id is None:
            return False

        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            request.session.clear()
            return False

        async with AsyncSessionLocal() as db:
            user = await user_repo.get_user_by_id(db, user_id)

        if user is None or str(user.role).lower() != "admin":
            request.session.clear()
            return False

        request.state.admin_user = user
        return True

    def get_admin_user(self, request: Request) -> AdminUser | None:
        user = getattr(request.state, "admin_user", None)
        username = getattr(user, "username", None) if user is not None else None
        if not username:
            username = request.session.get(self.session_username_key)
        if not username:
            return None
        return AdminUser(username=str(username))

    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response

    @staticmethod
    def _get_identifier(request: Request) -> str:
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            parts = [part.strip() for part in forwarded_for.split(",") if part.strip()]
            if parts:
                return parts[-1]

        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    @staticmethod
    def _block_key(identifier: str, username: str) -> str:
        return f"admin:login:block:{identifier}:{username}"

    @staticmethod
    def _attempt_key(identifier: str, username: str) -> str:
        window = max(settings.admin_login_window_seconds, 1)
        bucket = int(time.time() // window)
        return f"admin:login:attempt:{identifier}:{username}:{bucket}"

    async def _is_login_temporarily_blocked(self, identifier: str, username: str, client) -> bool:
        ttl = await client.ttl(self._block_key(identifier, username))
        return ttl is not None and int(ttl) > 0

    async def _register_failed_attempt(self, identifier: str, username: str, client) -> None:
        key = self._attempt_key(identifier, username)
        attempts = await client.incr(key)
        if attempts == 1:
            await client.expire(key, max(settings.admin_login_window_seconds, 1) + 1)
        if attempts >= max(settings.admin_login_max_attempts, 1):
            await client.set(
                self._block_key(identifier, username),
                "1",
                ex=max(settings.admin_login_block_seconds, 1),
            )

    async def _clear_failed_attempts(self, identifier: str, username: str, client) -> None:
        await client.delete(self._block_key(identifier, username), self._attempt_key(identifier, username))

    async def _get_security_redis_client(self):
        try:
            client = get_redis_client()
            await client.ping()
            return client
        except Exception as exc:
            raise _AdminSecurityBackendUnavailable from exc

    @staticmethod
    async def _extract_password_and_mfa_code(request: Request, raw_password: str) -> tuple[str, str | None]:
        password, mfa_code = split_password_and_totp(raw_password)
        if mfa_code:
            return password, mfa_code

        try:
            form = await request.form()
            code = form.get("otp_code") or form.get("mfa_code")
            if code is None:
                return password, None
            return password, str(code).strip()
        except Exception:
            return password, None
