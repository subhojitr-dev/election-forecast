# Backend container (FastAPI) for Render / Fly.io. See DEPLOY.md.
# The 217 MB baseline.db is NOT baked in — mount a persistent disk at /app/data/db
# and provision baseline.db there (or fetch from object storage on boot).
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "uvicorn[standard]"

COPY . .

ENV PORT=8000
EXPOSE 8000
# entrypoint.sh downloads baseline.db (from DB_URL) on boot, then starts uvicorn.
# Single worker keeps the in-memory SimController + SQLite consistent. For higher
# load, move to Postgres + multiple workers (DEPLOY.md §3).
CMD ["sh", "entrypoint.sh"]
