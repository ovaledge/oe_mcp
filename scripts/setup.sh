#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing Poetry..."
pip install poetry

echo "==> Installing dependencies..."
poetry install

echo "==> Copying .env.example to .env (if not exists)..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "    Created .env — fill in your credentials before running."
else
    echo "    .env already exists, skipping."
fi

echo "==> Running lint check..."
poetry run ruff check .

echo "==> Running type check..."
poetry run mypy server/ entrypoints/

echo "==> Setup complete."
echo "    Next: edit .env, then run 'poetry run oe-mcp-local'"
