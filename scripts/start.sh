#!/usr/bin/env bash
# Build the SPA, then serve API + static files from one process.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/webapp/frontend"
npm ci
npm run build
cd "$ROOT"
exec python -m uvicorn main:app \
  --app-dir webapp/api \
  --host 0.0.0.0 \
  --port "${PORT:-8017}"
