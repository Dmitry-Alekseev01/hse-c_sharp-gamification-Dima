# HSE C# Gamification Backend

Async backend for the learning platform (FastAPI + PostgreSQL + Redis + Alembic).

## Local Run (Backend-only)

1. Create env file:
   - copy `.env.example` to `.env`
2. Start services:
   - `docker compose up --build`
3. API endpoints:
   - API: `http://localhost:8000`
   - Swagger: `http://localhost:8000/docs`
   - Liveness: `http://localhost:8000/health/live`
   - Readiness: `http://localhost:8000/health/ready`

## Migrations

- Current revision:
  - `docker compose exec backend alembic current`
- Apply latest migration:
  - `docker compose exec backend alembic upgrade head`
- History:
  - `docker compose exec backend alembic history`

## Core Architecture

- `app/api` - HTTP routers and dependency wiring
- `app/services` - business logic and domain invariants
- `app/repositories` - DB access via SQLAlchemy
- `app/models` - ORM entities
- `app/schemas` - request/response contracts
- `app/cache/redis_cache.py` - Redis client + cache helpers
- `app/main.py` - app factory + lifespan startup/shutdown

## Notes

- Redis is used for caching and rate limiting.
- Readiness probe returns `503` when DB or Redis is unavailable.
- Schema changes are managed through Alembic migrations.

## AI Gamification (Backend)

- Feature flag: `AI_GAMIFICATION_ENABLED=true`
- Required secret: `OPENROUTER_API_KEY`
- Main flow: `POST /api/v1/ai/gamify` -> poll `GET /api/v1/ai/gamify/{job_id}` -> `POST /api/v1/ai/gamify/{job_id}/apply`
- Admin ops endpoint: `GET /api/v1/ai/ops/metrics`
- Detailed documentation: `docs/ai-gamification.md`
- Reliability behavior:
  - queue retry + DLQ for provider failures;
  - semantic fallback when draft is formally valid JSON but content is empty;
  - metric `jobs_semantic_fallback_used` tracks fallback activation frequency.
- Prompting behavior:
  - rewrites assignment text into a gamified/anime-style narrative;
  - keeps original assignment logic and numeric constraints unchanged.
