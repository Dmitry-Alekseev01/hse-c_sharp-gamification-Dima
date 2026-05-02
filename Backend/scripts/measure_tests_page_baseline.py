from __future__ import annotations

import concurrent.futures
import http.client
import json
import os
import statistics
import time
import urllib.parse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


API_HOST = os.getenv("PERF_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("PERF_API_PORT", "8000"))
API_BASE = "/api/v1"
REQUEST_TIMEOUT_SECONDS = int(os.getenv("PERF_TIMEOUT_SECONDS", "30"))
THREAD_WORKERS = int(os.getenv("PERF_THREAD_WORKERS", "8"))
PERF_USERNAME = os.getenv("PERF_USERNAME")
PERF_PASSWORD = os.getenv("PERF_PASSWORD")


@dataclass
class RequestMetric:
    path: str
    status_code: int
    ttfb_ms: float
    total_ms: float
    size_bytes: int


def _request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: str | None = None,
) -> tuple[RequestMetric, bytes]:
    conn = http.client.HTTPConnection(API_HOST, API_PORT, timeout=REQUEST_TIMEOUT_SECONDS)
    started = time.perf_counter()
    conn.request(method, path, body=body, headers=headers or {})
    response = conn.getresponse()
    ttfb_ms = (time.perf_counter() - started) * 1000.0
    payload = response.read()
    total_ms = (time.perf_counter() - started) * 1000.0
    status_code = int(response.status)
    conn.close()
    metric = RequestMetric(
        path=path,
        status_code=status_code,
        ttfb_ms=ttfb_ms,
        total_ms=total_ms,
        size_bytes=len(payload),
    )
    return metric, payload


def _json_headers(token: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _form_headers() -> dict[str, str]:
    return {"Content-Type": "application/x-www-form-urlencoded"}


def _metric_summary(name: str, metrics: list[RequestMetric]) -> dict[str, Any]:
    if not metrics:
        return {"name": name, "count": 0}
    totals = [m.total_ms for m in metrics]
    ttfb = [m.ttfb_ms for m in metrics]
    return {
        "name": name,
        "count": len(metrics),
        "status_codes": sorted({m.status_code for m in metrics}),
        "total_ms": {
            "min": round(min(totals), 2),
            "p50": round(statistics.median(totals), 2),
            "p95": round(_percentile(totals, 95), 2),
            "max": round(max(totals), 2),
            "avg": round(statistics.fmean(totals), 2),
        },
        "ttfb_ms": {
            "min": round(min(ttfb), 2),
            "p50": round(statistics.median(ttfb), 2),
            "p95": round(_percentile(ttfb, 95), 2),
            "max": round(max(ttfb), 2),
            "avg": round(statistics.fmean(ttfb), 2),
        },
    }


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    index = (len(sorted_values) - 1) * (percentile / 100.0)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return (sorted_values[lower] * (1 - fraction)) + (sorted_values[upper] * fraction)


def _login(username: str, password: str) -> str:
    token_body = urllib.parse.urlencode({"username": username, "password": password})
    token_metric, token_payload = _request(
        "POST",
        f"{API_BASE}/auth/token",
        headers=_form_headers(),
        body=token_body,
    )
    if token_metric.status_code != 200:
        raise RuntimeError(
            f"token failed: status={token_metric.status_code}, body={token_payload.decode(errors='ignore')}"
        )
    token = json.loads(token_payload.decode("utf-8"))["access_token"]
    return str(token)


def _register_and_login() -> tuple[str, str]:
    if PERF_USERNAME and PERF_PASSWORD:
        return _login(PERF_USERNAME, PERF_PASSWORD), "existing_user_credentials"

    username = f"perf_baseline_{int(time.time())}@example.com"
    password = "PerfBaseline123!"
    register_body = json.dumps(
        {"username": username, "password": password, "full_name": "Performance Baseline User"}
    )
    register_metric, register_payload = _request(
        "POST",
        f"{API_BASE}/auth/register",
        headers=_json_headers(),
        body=register_body,
    )
    if register_metric.status_code not in {201, 400}:
        raise RuntimeError(
            f"register failed: status={register_metric.status_code}, body={register_payload.decode(errors='ignore')}"
        )

    return _login(username, password), "temporary_auto_registered_user"


def _fetch_many(paths: list[str], token: str) -> list[RequestMetric]:
    if not paths:
        return []

    def worker(path: str) -> RequestMetric:
        metric, _ = _request("GET", path, headers=_json_headers(token))
        return metric

    metrics: list[RequestMetric] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, THREAD_WORKERS)) as pool:
        for item in pool.map(worker, paths):
            metrics.append(item)
    return metrics


def _simulate_tests_page_load(token: str, run_label: str) -> dict[str, Any]:
    started = time.perf_counter()

    tests_metric, tests_payload = _request("GET", f"{API_BASE}/tests/", headers=_json_headers(token))
    if tests_metric.status_code != 200:
        raise RuntimeError(
            f"GET /tests failed: status={tests_metric.status_code}, body={tests_payload.decode(errors='ignore')}"
        )
    tests = json.loads(tests_payload.decode("utf-8"))
    test_ids = [int(item["id"]) for item in tests]

    content_paths = [f"{API_BASE}/tests/{test_id}/content" for test_id in test_ids]
    answers_paths = [f"{API_BASE}/answers/test/{test_id}" for test_id in test_ids]

    content_metrics = _fetch_many(content_paths, token)
    answers_metrics = _fetch_many(answers_paths, token)

    total_ms = (time.perf_counter() - started) * 1000.0
    all_metrics = [tests_metric, *content_metrics, *answers_metrics]
    error_metrics = [metric for metric in all_metrics if metric.status_code != 200]

    return {
        "run": run_label,
        "tests_visible": len(test_ids),
        "request_count": len(all_metrics),
        "request_count_formula": f"1 + N + N = 1 + {len(test_ids)} + {len(test_ids)}",
        "total_page_load_ms": round(total_ms, 2),
        "errors": [asdict(metric) for metric in error_metrics],
        "segments": [
            _metric_summary("tests_list", [tests_metric]),
            _metric_summary("test_content_parallel", content_metrics),
            _metric_summary("answers_by_test_parallel", answers_metrics),
        ],
    }


def main() -> None:
    token, auth_mode = _register_and_login()
    cold_run = _simulate_tests_page_load(token, "run_1_first_open")
    warm_run = _simulate_tests_page_load(token, "run_2_second_open")

    output = {
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "target_page": "/tests",
        "environment": {
            "api_host": API_HOST,
            "api_port": API_PORT,
            "thread_workers": THREAD_WORKERS,
            "auth_mode": auth_mode,
            "note": "Frontend pattern emulation: GET /tests, then parallel GET /tests/{id}/content and GET /answers/test/{id}",
        },
        "runs": [cold_run, warm_run],
        "dev_mode_projection": {
            "strict_mode_enabled_in_frontend": True,
            "approx_duplicate_effect_load_ms": {
                "run_1_first_open_x2": round(cold_run["total_page_load_ms"] * 2, 2),
                "run_2_second_open_x2": round(warm_run["total_page_load_ms"] * 2, 2),
            },
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
