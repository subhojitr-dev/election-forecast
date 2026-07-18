# Backend container (FastAPI) for Render / Fly.io. See DEPLOY.md.
# The 217 MB baseline.db is NOT baked in — mount a persistent disk at /app/data/db
# and provision baseline.db there (or fetch from object storage on boot).
#
# This SAME image also runs the MI live-feed poller (a separate Render service,
# same repo/Dockerfile, different start command — see DEPLOY.md §4). MI's site
# blocks HEADLESS Chromium, so that poller needs a real (virtual) display: Xvfb.
# Everyone else's live-feed scripts are plain httpx or headless Playwright and
# don't need any of this — it's included unconditionally to keep one Dockerfile,
# at the cost of a larger image (Chromium + its OS deps + Xvfb, ~400-500 MB).
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "uvicorn[standard]"

# Xvfb (virtual display, for MI's headed-browser requirement) + Playwright's own
# OS-level deps for Chromium, then the Chromium browser binary itself.
RUN apt-get update && apt-get install -y --no-install-recommends xvfb \
    && rm -rf /var/lib/apt/lists/*
RUN playwright install --with-deps chromium

COPY . .

ENV PORT=8000
EXPOSE 8000
# entrypoint.sh downloads baseline.db (from DB_URL) on boot, then starts uvicorn.
# Single worker keeps the in-memory SimController + SQLite consistent. For higher
# load, move to Postgres + multiple workers (DEPLOY.md §3).
CMD ["sh", "entrypoint.sh"]
