# Backend File Manifest

## Root
- `.env.example` - environment template
- `alembic.ini` - Alembic configuration
- `docker-compose.yml` - backend stack (app, worker, db, redis)
- `requirements.txt` - Python dependencies
- `start.sh` - backend startup helper

## Application (`app/`)
- `main.py` - FastAPI app factory and lifespan hooks
- `core/` - settings and security
- `db/` - engine/session setup
- `models/` - SQLAlchemy entities
- `schemas/` - API contracts (Pydantic)
- `repositories/` - database query layer
- `services/` - business/domain logic
- `api/` - routers and dependencies
- `cache/redis_cache.py` - unified Redis cache/lock helper
- `health/` - liveness/readiness endpoints
- `middleware/` - request middleware (rate limiting)
- `tasks/` - async background worker logic

## Migrations
- `migrations/` - Alembic revisions and env
- `scripts/` - operational scripts (run app/worker/migrations)

## Documentation and Tests
- `docs/api-contract.yaml` - OpenAPI-style contract for frontend
- `tests/` - unit/integration tests
