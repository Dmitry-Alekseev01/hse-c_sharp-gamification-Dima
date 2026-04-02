#!/usr/bin/env sh
set -eu

echo "Starting worker..."
exec python -u -m app.tasks.worker
