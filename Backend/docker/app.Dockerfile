# docker/app.Dockerfile
# Minimal image for development (change for production)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential libpq-dev --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

CMD ["sh", "-ec", "\
MIGRATION_MAX_ATTEMPTS=${DB_MIGRATION_MAX_ATTEMPTS:-30}; \
MIGRATION_RETRY_SECONDS=${DB_MIGRATION_RETRY_SECONDS:-2}; \
echo \"Starting backend app...\"; \
echo \"Applying migrations (max attempts: ${MIGRATION_MAX_ATTEMPTS})\"; \
attempt=1; \
while true; do \
  if alembic upgrade head; then \
    echo \"Migrations applied successfully.\"; \
    break; \
  fi; \
  if [ \"$attempt\" -ge \"$MIGRATION_MAX_ATTEMPTS\" ]; then \
    echo \"Migration failed after ${attempt} attempts. Exiting.\"; \
    exit 1; \
  fi; \
  echo \"Migration attempt ${attempt} failed. Retrying in ${MIGRATION_RETRY_SECONDS}s...\"; \
  attempt=$((attempt + 1)); \
  sleep \"$MIGRATION_RETRY_SECONDS\"; \
done; \
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
"]
