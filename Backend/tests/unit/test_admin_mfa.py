from app.admin.mfa import is_valid_totp_secret, split_password_and_totp, verify_totp_code


def test_split_password_and_totp():
    password, code = split_password_and_totp("my-password::123456")
    assert password == "my-password"
    assert code == "123456"


def test_split_password_without_totp():
    password, code = split_password_and_totp("my-password")
    assert password == "my-password"
    assert code is None


def test_verify_totp_code_with_known_vector():
    # Known token for secret JBSWY3DPEHPK3PXP at Unix time 0 and period=30.
    assert verify_totp_code(
        secret="JBSWY3DPEHPK3PXP",
        code="282760",
        period_seconds=30,
        digits=6,
        drift_windows=0,
        now_ts=0,
    )


def test_is_valid_totp_secret():
    assert is_valid_totp_secret("JBSWY3DPEHPK3PXP") is True
    assert is_valid_totp_secret("not-base32") is False
