from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
import re
import time
from threading import Lock
from typing import Any


_UUID_SEGMENT_RE = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}(?=/|$)"
)
_INT_SEGMENT_RE = re.compile(r"/\d+(?=/|$)")


@dataclass(slots=True)
class _RequestEvent:
    ts: float
    endpoint: str
    status_code: int
    duration_ms: float


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


def _latency_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0, "avg": 0.0}
    values_sorted = sorted(values)
    total = sum(values_sorted)
    return {
        "min": round(values_sorted[0], 2),
        "p50": round(_percentile(values_sorted, 50), 2),
        "p95": round(_percentile(values_sorted, 95), 2),
        "max": round(values_sorted[-1], 2),
        "avg": round(total / len(values_sorted), 2),
    }


class RequestMetricsCollector:
    """In-memory request metrics for lightweight runtime monitoring."""

    def __init__(self, *, window_seconds: int = 300, max_events: int = 50_000) -> None:
        self._started_at = time.time()
        self._window_seconds = max(int(window_seconds), 60)
        self._max_events = max(int(max_events), 1_000)
        self._events: deque[_RequestEvent] = deque()
        self._lock = Lock()

        self._requests_total = 0
        self._errors_total = 0
        self._rate_limited_total = 0
        self._status_class_counts: Counter[str] = Counter()
        self._endpoint_total_counts: Counter[str] = Counter()
        self._endpoint_total_errors: Counter[str] = Counter()
        self._endpoint_total_rate_limited: Counter[str] = Counter()

    @staticmethod
    def _normalize_path(path: str) -> str:
        normalized = _UUID_SEGMENT_RE.sub("/{id}", path)
        normalized = _INT_SEGMENT_RE.sub("/{id}", normalized)
        return normalized

    @staticmethod
    def _status_class(status_code: int) -> str:
        if status_code < 100:
            return "unknown"
        hundred = status_code // 100
        if hundred in {1, 2, 3, 4, 5}:
            return f"{hundred}xx"
        return "other"

    def _prune(self, now: float) -> None:
        cutoff = now - self._window_seconds
        while self._events and self._events[0].ts < cutoff:
            self._events.popleft()
        while len(self._events) > self._max_events:
            self._events.popleft()

    def record(self, *, method: str, path: str, status_code: int, duration_ms: float) -> None:
        endpoint = f"{method.upper()} {self._normalize_path(path)}"
        now = time.time()
        with self._lock:
            self._requests_total += 1
            status_class = self._status_class(status_code)
            self._status_class_counts[status_class] += 1
            self._endpoint_total_counts[endpoint] += 1

            if status_code >= 500 or status_code <= 0:
                self._errors_total += 1
                self._endpoint_total_errors[endpoint] += 1
            if status_code == 429:
                self._rate_limited_total += 1
                self._endpoint_total_rate_limited[endpoint] += 1

            self._events.append(
                _RequestEvent(
                    ts=now,
                    endpoint=endpoint,
                    status_code=int(status_code),
                    duration_ms=max(float(duration_ms), 0.0),
                )
            )
            self._prune(now)

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            self._prune(now)
            events = list(self._events)
            requests_total = int(self._requests_total)
            errors_total = int(self._errors_total)
            rate_limited_total = int(self._rate_limited_total)
            status_class_counts = dict(sorted(self._status_class_counts.items()))
            endpoint_total_counts = dict(self._endpoint_total_counts)
            endpoint_total_errors = dict(self._endpoint_total_errors)
            endpoint_total_rate_limited = dict(self._endpoint_total_rate_limited)

        overall_latencies = [event.duration_ms for event in events]
        one_minute_cutoff = now - 60
        one_minute_events = [event for event in events if event.ts >= one_minute_cutoff]
        one_minute_latencies = [event.duration_ms for event in one_minute_events]
        one_minute_errors = sum(1 for event in one_minute_events if event.status_code >= 500 or event.status_code <= 0)
        one_minute_rate_limited = sum(1 for event in one_minute_events if event.status_code == 429)

        endpoint_window: dict[str, list[_RequestEvent]] = defaultdict(list)
        for event in events:
            endpoint_window[event.endpoint].append(event)

        top_endpoints = []
        for endpoint, count in sorted(endpoint_total_counts.items(), key=lambda item: item[1], reverse=True)[:20]:
            window_events = endpoint_window.get(endpoint, [])
            window_latencies = [event.duration_ms for event in window_events]
            top_endpoints.append(
                {
                    "endpoint": endpoint,
                    "requests_total": int(count),
                    "errors_total": int(endpoint_total_errors.get(endpoint, 0)),
                    "rate_limited_total": int(endpoint_total_rate_limited.get(endpoint, 0)),
                    "window_latency_ms": _latency_stats(window_latencies),
                    "window_requests": len(window_events),
                }
            )

        return {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "uptime_seconds": int(max(now - self._started_at, 0.0)),
            "window_seconds": self._window_seconds,
            "requests_total": requests_total,
            "errors_total": errors_total,
            "rate_limited_total": rate_limited_total,
            "status_class_counts": status_class_counts,
            "window_latency_ms": _latency_stats(overall_latencies),
            "window_requests": len(events),
            "last_minute": {
                "requests": len(one_minute_events),
                "rps": round(len(one_minute_events) / 60.0, 3),
                "errors": int(one_minute_errors),
                "error_rate_percent": round((one_minute_errors / len(one_minute_events) * 100.0), 3)
                if one_minute_events
                else 0.0,
                "rate_limited": int(one_minute_rate_limited),
                "latency_ms": _latency_stats(one_minute_latencies),
            },
            "top_endpoints": top_endpoints,
        }


request_metrics = RequestMetricsCollector()
