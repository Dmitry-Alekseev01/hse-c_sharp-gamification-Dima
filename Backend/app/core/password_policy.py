import string

from app.core.config import settings


def validate_password_policy(password: str) -> None:
    if len(password) < settings.password_policy_min_length:
        raise ValueError(
            f"New password must be at least {settings.password_policy_min_length} characters long"
        )
    if settings.password_policy_disallow_whitespace and any(char.isspace() for char in password):
        raise ValueError("New password must not contain whitespace")
    if settings.password_policy_require_uppercase and not any(char.isupper() for char in password):
        raise ValueError("New password must include at least one uppercase letter")
    if settings.password_policy_require_lowercase and not any(char.islower() for char in password):
        raise ValueError("New password must include at least one lowercase letter")
    if settings.password_policy_require_digit and not any(char.isdigit() for char in password):
        raise ValueError("New password must include at least one digit")
    if settings.password_policy_require_special:
        special_chars = set(string.punctuation)
        if not any(char in special_chars for char in password):
            raise ValueError("New password must include at least one special character")
