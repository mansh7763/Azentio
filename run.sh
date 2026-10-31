#!/bin/sh
# Start the backend on :${PORT:-8000}. Frontend: cd frontend && npm run dev
cd "$(dirname "$0")/backend" || exit 1
PY=../.venv/Scripts/python; [ -x "$PY" ] || PY=../.venv/bin/python
exec "$PY" -m uvicorn app.main:app --reload --port "${PORT:-8000}"
