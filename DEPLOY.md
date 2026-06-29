# DEPLOY.md — Phase 7 deployment plan

How to put the dashboard on a public URL. **Today it runs locally (two terminals);
Phase 7 makes it reachable + able to scale for election night.**

---

## 0. The architecture decision (why a split)

The backend is **FastAPI + a 217 MB SQLite file + an in-memory simulator + a
WebSocket + a 60s poller**. That is NOT a fit for Vercel/serverless (no persistent
disk, no in-memory state across calls, no long-lived WebSocket, no always-on
background loop). So:

```
            ┌─────────────────────┐         ┌──────────────────────────────┐
  viewers → │  FRONTEND on Vercel │  /api → │  BACKEND on Render / Fly.io  │
            │  (static React/Vite)│  /ws  → │  FastAPI + SQLite + poller   │
            │  CDN — scales huge  │ ◀─cache─│  persistent disk for the DB  │
            └─────────────────────┘         └──────────────────────────────┘
                         ▲ CDN / edge cache on the read API (the scale lever)
```

- **Frontend → Vercel** (static build, CDN-served → effectively unlimited viewers).
- **Backend → a persistent host** (Render Web Service or Fly.io) where the SQLite
  file, WebSocket, and poller can live.
- **A cache in front of the read endpoints** is what lets it survive election-night
  traffic (data changes only ~every 60s, so all viewers can hit cache).

---

## 1. Frontend → Vercel

The UI currently calls **relative** `/api` + `/ws` (Vite proxies them in dev). In
production the backend is a different host, so point the UI at it.

**Code change (small):** read a base URL from an env var.
- `ui/src/api.js`: prefix REST calls with `import.meta.env.VITE_API_BASE` (e.g.
  `https://election-api.onrender.com`).
- The WebSocket: `new WebSocket(`${VITE_WS_BASE}/ws?...`)` (e.g. `wss://election-api.onrender.com`).

**Vercel setup:**
1. Import the GitHub repo at vercel.com → **Root Directory = `ui`**.
2. Framework preset **Vite**; build `npm run build`; output `dist`.
3. Env vars: `VITE_API_BASE=https://<backend-host>`, `VITE_WS_BASE=wss://<backend-host>`.
4. Deploy → you get `https://election-forecast.vercel.app`.

(Alternative: a `vercel.json` rewrite proxying `/api/*` to the backend so the UI code
stays unchanged — but WebSockets still need a direct `wss://` to the backend, so the
env-var approach is cleaner.)

---

## 2. Backend → Render (or Fly.io)

**Add a `Dockerfile`** (project root):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn[standard]
COPY . .
ENV PORT=8000
CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

**The database (217 MB) is NOT in Git** — provision it to the host:
- **Option A (simplest):** attach a **persistent disk** (Render Disk / Fly Volume) at
  `data/db/`, then upload `baseline.db` once (scp / Render shell / Fly volume).
- **Option B:** store `baseline.db` in **object storage** (S3/R2) and download it on
  container boot (a small entrypoint step).
- **Option C:** rebuild on the host from the CSVs (needs the 1.2 GB of CSVs up there —
  heaviest; avoid unless you want a fully reproducible build).

**Render setup:** New **Web Service** → repo → Docker → add a **Disk** mounted at
`/app/data/db` → deploy. **Fly:** `fly launch` + `fly volumes create` mounted at
`/app/data/db`.

**Lock down CORS** (`api/main.py`): change `allow_origins=["*"]` to your Vercel domain.

---

## 3. Caching — the scale lever (do this for election night)

Data changes only when the poller writes (~60s), and every viewer sees the same
statewide numbers, so the read API is highly cacheable.

- **Add cache headers** to `/api/states` and `/api/state/{abbr}` responses:
  `Cache-Control: public, max-age=15, stale-while-revalidate=30`.
- Put **Cloudflare** (free) in front of the backend, or use Vercel's edge cache for
  proxied `/api`. Result: thousands of viewers hit the cache; only a few requests/min
  reach FastAPI.
- The **WebSocket** bypasses cache (it's the live-push channel) — fine, it's one mostly
  idle connection per viewer; a single uvicorn holds thousands.

**Capacity:** without caching, one backend ≈ **100–300 concurrent viewers**. With the
cache in front, **effectively unlimited** (backend only serves cache-misses + the poller).
If you expect very high election-night load, also: run **multiple uvicorn workers** and
swap **SQLite → Postgres** (so workers share one DB).

---

## 4. The live poller in production (election night)

Today the "Next Batch" button stands in for the poller. In production, run
`ingestor/clarity_poller.run_poller(LiveClarityFeed(...), interval=60, on_write=...)`
as a **background worker** — either a FastAPI startup task or a separate Render
**Background Worker** / Fly process sharing the same DB/disk. It writes `results_live`;
the WebSocket then pushes updates to all viewers. (Gated on Issues #1/#3/#8 — see PREP.md.)

---

## 5. Phase-7 checklist

- [ ] Frontend: env-based API/WS base URL in `ui/src/api.js`
- [ ] Frontend: deploy on Vercel (root = `ui`), set `VITE_API_BASE` / `VITE_WS_BASE`
- [ ] Backend: add `Dockerfile`; lock CORS to the Vercel domain
- [ ] Backend: deploy on Render/Fly with a persistent disk at `data/db/`
- [ ] Provision `baseline.db` to the host (upload to the disk, or fetch from object storage)
- [ ] Caching: cache-control headers + Cloudflare/edge cache on read endpoints
- [ ] Smoke test: `/api/health`, strip loads, sim steps, WebSocket pushes
- [ ] (Later, for live night) background poller worker; SQLite→Postgres if high load
