from types import SimpleNamespace

from app.middleware.rate_limit import RateLimitMiddleware


class _DummyRequest:
    def __init__(self, headers: dict[str, str], client_host: str = "127.0.0.1"):
        self.headers = headers
        self.client = SimpleNamespace(host=client_host)


def test_scope_for_admin_login_post():
    scope, limit = RateLimitMiddleware._get_scope_and_limit("/admin/login", "POST")
    assert scope == "admin_login"
    assert isinstance(limit, int)


def test_scope_for_admin_pages():
    scope, limit = RateLimitMiddleware._get_scope_and_limit("/admin/user/list", "GET")
    assert scope == "admin"
    assert isinstance(limit, int)


def test_identifier_prefers_x_real_ip_over_forwarded_for():
    request = _DummyRequest(
        headers={
            "x-real-ip": "203.0.113.10",
            "x-forwarded-for": "198.51.100.1, 198.51.100.2",
        },
        client_host="172.19.0.10",
    )
    identifier = RateLimitMiddleware._get_identifier(request)
    assert identifier == "203.0.113.10"


def test_identifier_uses_last_hop_from_x_forwarded_for():
    request = _DummyRequest(
        headers={"x-forwarded-for": "198.51.100.1, 198.51.100.2"},
        client_host="172.19.0.10",
    )
    identifier = RateLimitMiddleware._get_identifier(request)
    assert identifier == "198.51.100.2"

