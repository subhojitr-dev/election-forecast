#!/bin/sh
# Backend container entrypoint: ensure the DB exists, optionally start the
# live-results poller in the background, then start the API.
#
# The poller is OFF by default (ENABLE_POLLER unset) — this keeps the free
# tier, and any moment we're not actively polling, a complete no-op: same
# behavior as before this was added. Turn it on via Render's Environment
# tab: set ENABLE_POLLER=1 and POLLER_MODE=mi-primary (or test / prod).
set -e
python download_db.py

if [ "${ENABLE_POLLER:-0}" = "1" ]; then
    echo "[entrypoint] ENABLE_POLLER=1 -> starting production_poller.py (mode=${POLLER_MODE:-test}) in background"
    python ingestor/production_poller.py --mode "${POLLER_MODE:-test}" &
fi

exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
