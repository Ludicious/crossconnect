#!/bin/bash
# update.sh — pull latest and apply any pending migrations
set -e

echo "→ Pulling latest..."
git pull

echo "→ Syncing dependencies..."
.venv/bin/pip install -e ".[dev]" --quiet  # no-op if nothing changed, safe to always run

echo "→ Applying migrations..."
.venv/bin/alembic upgrade head

echo "→ Done. Restart uvicorn to pick up code changes."
