# Tests Page Performance Baseline

Date (UTC): 2026-05-01  
Scope: baseline for `/tests` page load chain before optimization parties.

## Current Request Pattern (as-is)

Frontend currently loads tests page in 3 steps:

1. `GET /api/v1/tests/`
2. Parallel `GET /api/v1/tests/{id}/content` for each returned test.
3. Parallel `GET /api/v1/answers/test/{id}` for each returned test.

Effective formula per page open:

`1 + N + N` requests, where `N = visible tests`.

References:

- `Frontend/c-s-game/src/pages/Tests/Tests.jsx`
- `Backend/app/api/v1/routers/tests.py`
- `Backend/app/api/v1/routers/answers.py`

## Measurement Method

Script:

- `Backend/scripts/measure_tests_page_baseline.py`

Run inside backend container:

```bash
docker compose exec -w /app backend python scripts/measure_tests_page_baseline.py
```

What script does:

- creates a dedicated temporary user and logs in;
- performs two sequential “page-open” simulations;
- measures per-request `ttfb_ms` and `total_ms`;
- aggregates timings for list/content/answers segments;
- prints StrictMode x2 projection for dev UX.

Snapshot with raw numbers:

- `Backend/docs/tests_page_performance_baseline_2026-05-01.json`

## Baseline Snapshot (measured)

Environment:

- API host: `127.0.0.1:8000` (inside backend container)
- Thread workers for parallel segment emulation: `8`
- Visible tests for baseline user: `N=2`

Run 1 (`run_1_first_open`):

- requests: `5` (`1 + 2 + 2`)
- total page load: `973.08 ms`
- `/tests` total: `169.28 ms`
- `/tests/{id}/content` (parallel, 2 req) p50 total: `385.78 ms`
- `/answers/test/{id}` (parallel, 2 req) p50 total: `187.67 ms`

Run 2 (`run_2_second_open`):

- requests: `5` (`1 + 2 + 2`)
- total page load: `427.91 ms`
- `/tests` total: `21.95 ms`
- `/tests/{id}/content` (parallel, 2 req) p50 total: `169.13 ms`
- `/answers/test/{id}` (parallel, 2 req) p50 total: `188.96 ms`

Dev StrictMode projection from script:

- first open x2: `1946.16 ms`
- second open x2: `855.82 ms`

## Interpretation

- Backend cache for tests/content works (large drop from first to second open).
- Main non-cached tail remains answers-by-test fan-out.
- With larger `N`, repeated navigation cost scales linearly in calls to `/answers/test/{id}`.

## SLA Target For Next Parties

- Repeat open `/tests` (same user/session, no hard refresh): `<= 600 ms p95` in dev, `<= 350 ms p95` in prod.
- First open `/tests`: `<= 1500 ms p95` in dev, `<= 900 ms p95` in prod.
- Request fan-out target: from `1 + N + N` to `1` (aggregated endpoint for test cards state).

## Exit Criteria For Batch 4

- Baseline script added and runnable.
- Baseline numbers documented in repo.
- SLA targets fixed for comparison in subsequent optimization batches.
