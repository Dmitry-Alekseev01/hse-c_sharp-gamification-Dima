from __future__ import annotations

import asyncio
import json
import os
import random
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx


API_HOST = os.getenv("LOADCHECK_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("LOADCHECK_API_PORT", "8000"))
API_BASE = "/api/v1"

USERNAME = os.getenv("LOADCHECK_USERNAME", "csharp_student_demo@example.com")
PASSWORD = os.getenv("LOADCHECK_PASSWORD", "Stud123!")
TIMEOUT_SECONDS = float(os.getenv("LOADCHECK_TIMEOUT_SECONDS", "20"))
SCENARIO_TESTS_LIMIT = int(os.getenv("LOADCHECK_TESTS_LIMIT", "5"))

RPS_LEVELS = [int(v.strip()) for v in os.getenv("LOADCHECK_RPS_LEVELS", "8,20").split(",") if v.strip()]
DURATION_SECONDS = int(os.getenv("LOADCHECK_DURATION_SECONDS", "45"))
WARMUP_SECONDS = int(os.getenv("LOADCHECK_WARMUP_SECONDS", "5"))


@dataclass
class RequestResult:
    path: str
    method: str
    status_code: int
    latency_ms: float
    ok: bool
    error: str | None = None


def _summarize_latencies(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0, "avg": 0.0}
    sorted_values = sorted(values)
    return {
        "min": round(sorted_values[0], 2),
        "p50": round(statistics.median(sorted_values), 2),
        "p95": round(_percentile(sorted_values, 95), 2),
        "max": round(sorted_values[-1], 2),
        "avg": round(statistics.fmean(sorted_values), 2),
    }


def _percentile(sorted_values: list[float], p: int) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    index = (len(sorted_values) - 1) * (p / 100.0)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return (sorted_values[lower] * (1 - weight)) + (sorted_values[upper] * weight)


async def _request(client: httpx.AsyncClient, method: str, path: str, headers: dict[str, str]) -> RequestResult:
    started = time.perf_counter()
    try:
        response = await client.request(method, path, headers=headers)
        latency_ms = (time.perf_counter() - started) * 1000.0
        return RequestResult(
            path=path,
            method=method,
            status_code=int(response.status_code),
            latency_ms=latency_ms,
            ok=200 <= response.status_code < 400,
            error=None,
        )
    except Exception as exc:  # pragma: no cover - observational script
        latency_ms = (time.perf_counter() - started) * 1000.0
        return RequestResult(
            path=path,
            method=method,
            status_code=0,
            latency_ms=latency_ms,
            ok=False,
            error=str(exc),
        )


async def _login(client: httpx.AsyncClient) -> str:
    response = await client.post(
        f"{API_BASE}/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Login failed ({response.status_code}). "
            f"Provide valid LOADCHECK_USERNAME/LOADCHECK_PASSWORD or seed demo data first."
        )
    return str(response.json()["access_token"])


async def _build_scenario_paths(client: httpx.AsyncClient, headers: dict[str, str]) -> list[str]:
    response = await client.get(f"{API_BASE}/tests/", headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"Cannot load tests list for scenario: {response.status_code} {response.text}")

    tests = response.json()
    test_ids = [int(item["id"]) for item in tests[: max(SCENARIO_TESTS_LIMIT, 0)]]
    paths = [
        f"{API_BASE}/tests/",
        f"{API_BASE}/analytics/me/learning-dashboard",
    ]
    for test_id in test_ids:
        paths.append(f"{API_BASE}/tests/{test_id}/content")
        paths.append(f"{API_BASE}/answers/test/{test_id}")
    if not test_ids:
        # Fallback keeps script runnable even on empty datasets.
        paths.append(f"{API_BASE}/tests/catalog/me")
    return paths


async def _run_stage(
    client: httpx.AsyncClient,
    *,
    rps: int,
    duration_seconds: int,
    paths: list[str],
    headers: dict[str, str],
) -> dict[str, Any]:
    if rps <= 0:
        raise ValueError("RPS must be > 0")
    if duration_seconds <= 0:
        raise ValueError("Duration must be > 0")
    if not paths:
        raise ValueError("Scenario paths cannot be empty")

    interval = 1.0 / float(rps)
    total_requests = int(rps * duration_seconds)
    results: list[RequestResult] = []

    start = time.perf_counter()
    tasks: list[asyncio.Task[RequestResult]] = []
    for i in range(total_requests):
        due = start + (i * interval)
        now = time.perf_counter()
        if due > now:
            await asyncio.sleep(due - now)
        path = random.choice(paths)
        tasks.append(asyncio.create_task(_request(client, "GET", path, headers=headers)))

    for task in tasks:
        results.append(await task)

    total_duration = time.perf_counter() - start
    ok_results = [item for item in results if item.ok]
    failed_results = [item for item in results if not item.ok]
    latencies = [item.latency_ms for item in results]

    by_path: dict[str, list[RequestResult]] = {}
    for item in results:
        by_path.setdefault(item.path, []).append(item)

    return {
        "rps_target": rps,
        "duration_seconds": duration_seconds,
        "requests_scheduled": total_requests,
        "requests_completed": len(results),
        "requests_ok": len(ok_results),
        "requests_failed": len(failed_results),
        "error_rate_percent": round((len(failed_results) / len(results) * 100.0) if results else 0.0, 3),
        "observed_rps": round((len(results) / total_duration) if total_duration > 0 else 0.0, 2),
        "latency_ms": _summarize_latencies(latencies),
        "sample_errors": [
            {
                "path": item.path,
                "status_code": item.status_code,
                "error": item.error,
            }
            for item in failed_results[:10]
        ],
        "per_path": {
            path: {
                "count": len(items),
                "errors": sum(1 for item in items if not item.ok),
                "latency_ms": _summarize_latencies([item.latency_ms for item in items]),
            }
            for path, items in sorted(by_path.items(), key=lambda pair: pair[0])
        },
    }


async def _health_check(client: httpx.AsyncClient) -> dict[str, Any]:
    result: dict[str, Any] = {
        "live_status": None,
        "ready_status": None,
        "live_ok": False,
        "ready_ok": False,
        "error": None,
    }
    try:
        live = await client.get("/health/live")
        result["live_status"] = live.status_code
        result["live_ok"] = live.status_code == 200
    except Exception as exc:  # pragma: no cover - observational script
        result["error"] = f"live check failed: {exc}"

    try:
        ready = await client.get("/health/ready")
        result["ready_status"] = ready.status_code
        result["ready_ok"] = ready.status_code == 200
    except Exception as exc:  # pragma: no cover - observational script
        existing = result.get("error")
        extra = f"ready check failed: {exc}"
        result["error"] = f"{existing}; {extra}" if existing else extra

    return result


async def main() -> None:
    base_url = f"http://{API_HOST}:{API_PORT}"
    async with httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT_SECONDS) as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        paths = await _build_scenario_paths(client, headers)

        warmup_summary = await _run_stage(
            client,
            rps=max(1, min(RPS_LEVELS)),
            duration_seconds=max(1, WARMUP_SECONDS),
            paths=paths,
            headers=headers,
        )

        stages = []
        for rps in RPS_LEVELS:
            stages.append(
                await _run_stage(
                    client,
                    rps=rps,
                    duration_seconds=DURATION_SECONDS,
                    paths=paths,
                    headers=headers,
                )
            )

        health_after = await _health_check(client)

    output = {
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "scenario_paths": paths,
        "config": {
            "rps_levels": RPS_LEVELS,
            "duration_seconds": DURATION_SECONDS,
            "warmup_seconds": WARMUP_SECONDS,
            "timeout_seconds": TIMEOUT_SECONDS,
            "tests_limit": SCENARIO_TESTS_LIMIT,
            "username": USERNAME,
        },
        "warmup": warmup_summary,
        "stages": stages,
        "health_after": health_after,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
