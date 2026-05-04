import pytest

from app.core.config import settings

pytestmark = pytest.mark.asyncio


async def test_health_metrics_endpoint_returns_runtime_snapshot(client):
    baseline_response = await client.get("/health/metrics")
    assert baseline_response.status_code == 200
    baseline_payload = baseline_response.json()
    baseline_requests_total = int(baseline_payload["requests_total"])

    live_response = await client.get("/health/live")
    assert live_response.status_code == 200

    snapshot_response = await client.get("/health/metrics")
    assert snapshot_response.status_code == 200
    payload = snapshot_response.json()

    assert payload["requests_total"] >= baseline_requests_total + 1
    assert payload["errors_total"] >= 0
    assert payload["rate_limited_total"] >= 0
    assert "status_class_counts" in payload
    assert "last_minute" in payload
    assert "top_endpoints" in payload
    assert isinstance(payload["top_endpoints"], list)


async def test_health_metrics_endpoint_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "monitoring_metrics_token", "metrics-secret-token")

    forbidden_no_header = await client.get("/health/metrics")
    assert forbidden_no_header.status_code == 403

    forbidden_wrong_header = await client.get("/health/metrics", headers={"X-Metrics-Token": "wrong-token"})
    assert forbidden_wrong_header.status_code == 403

    ok_response = await client.get("/health/metrics", headers={"X-Metrics-Token": "metrics-secret-token"})
    assert ok_response.status_code == 200
