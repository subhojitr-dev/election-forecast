#!/bin/sh
# Backend container entrypoint: ensure the DB exists, then start the API.
set -e
python download_db.py
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
