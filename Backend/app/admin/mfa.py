import base64
import binascii
import hashlib
import hmac
import time


def split_password_and_totp(raw_password: str) -> tuple[str, str | None]:
    """
    Allow entering MFA code in the same password field:
    <password>::<123456>
    """
    if "::" not in raw_password:
        return raw_password, None
    password, totp_code = raw_password.rsplit("::", 1)
    return password, totp_code.strip()


def is_valid_totp_secret(secret: str | None) -> bool:
    if not secret:
        return False
    normalized_secret = secret.strip().replace(" ", "")
    try:
        base64.b32decode(normalized_secret, casefold=True)
        return True
    except (ValueError, binascii.Error):
        return False


def _build_totp_token(secret: str, counter: int, digits: int) -> str:
    key = base64.b32decode(secret, casefold=True)
    msg = counter.to_bytes(8, byteorder="big", signed=False)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    dynamic_binary_code = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    token_int = dynamic_binary_code % (10 ** digits)
    return str(token_int).zfill(digits)


def verify_totp_code(
    *,
    secret: str,
    code: str | None,
    period_seconds: int,
    digits: int,
    drift_windows: int,
    now_ts: int | None = None,
) -> bool:
    if not secret or not code:
        return False
    if period_seconds <= 0 or digits <= 0 or digits > 10 or drift_windows < 0:
        return False

    normalized_secret = secret.strip().replace(" ", "")
    normalized_code = code.strip()
    if not normalized_code.isdigit() or len(normalized_code) != digits:
        return False

    current_ts = int(now_ts if now_ts is not None else time.time())
    counter = current_ts // period_seconds

    try:
        for offset in range(-drift_windows, drift_windows + 1):
            candidate_counter = counter + offset
            if candidate_counter < 0:
                continue
            expected = _build_totp_token(normalized_secret, candidate_counter, digits)
            if hmac.compare_digest(expected, normalized_code):
                return True
    except (ValueError, OverflowError, binascii.Error):
        return False

    return False
