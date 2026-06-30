# DEPLOY.md — Phase 7 deployment plan

How to put the dashboard on a public URL. The reference plan is below; the
**AS-BUILT record (the exact steps that worked)** is first.

---

## ✅ AS-BUILT — live deployment (done 2026-06-30)

| Piece | URL |
|-------|-----|
| **Frontend (Vercel)** | **https://election-forecast-silk.vercel.app** |
| **Backend (Render)** | **https://election-forecast.onrender.com** |
| **GitHub repo** | github.com/subhojitr-dev/election-forecast (branch `main`) |
| **DB (GitHub Release)** | tag `db-v1`, asset `baseline.db.gz` (43 MB) |

### A. Backend on Render (do this FIRST — frontend needs its URL)
1. **render.com** → Sign up **with GitHub** → in the GitHub-app prompt, choose
   **Only select repositories → `election-forecast`** → Install.
2. **New + → Web Service** → pick the repo. Render auto-detects the **Dockerfile**
   (Environment = Docker). Instance type = **Free**.
3. **The database (217 MB, NOT in Git):** uploaded gzipped (43 MB) as a **GitHub
   Release** (Releases → Draft new release → tag `db-v1` → attach
   `data/db/baseline.db.gz` → Publish). On boot, `entrypoint.sh` → `download_db.py`
   pulls it via the `DB_URL` env var and unzips to `data/db/`.
4. **Environment variable** → add `DB_URL =
   https://github.com/subhojitr-dev/election-forecast/releases/download/db-v1/baseline.db.gz`
   (CORS_ORIGINS optional — defaults to `*`).
5. **Deploy.** Logs show `[db] baseline.db ready (226,824,192 bytes)` → uvicorn up →
   "service is live". Verify: `…onrender.com/api/health` → `{"status":"ok",…}`.

### B. Frontend on Vercel
1. **vercel.com/new**. If `election-forecast` isn't in the import list, click
   **"Adjust GitHub App Permissions"** → add the repo → Save. Then **Import** it
   (⚠️ NOT the immigration repo).
2. ⚠️ Vercel first auto-detects the **backend** (FastAPI / Root `./`) — FIX BOTH:
   - **Root Directory → Edit → `ui`** (the Vite/React folder; it shows the Vite logo).
   - **Application Preset** then flips to **Vite** (set it manually if not).
3. **Environment Variables** → `VITE_API_BASE =
   https://election-forecast.onrender.com`.
4. **Deploy** → production URL appears under **Overview → Domains**
   (here: `election-forecast-silk.vercel.app`).

### C. Lock down CORS (the one remaining step)
On Render → service → **Environment** → add
`CORS_ORIGINS = https://election-forecast-silk.vercel.app` → save (auto-redeploys).
Until then the API accepts any origin (`*`), so the site already works.

### Operating notes
- **Render free tier spins down after ~15 min idle** → first visit then takes
  ~30–60 s (cold start re-downloads the 43 MB DB). For election night → Starter
  ($7/mo) + a persistent disk mounted at `data/db/`.
- **Updating the app:** push to `main` → both Vercel and Render auto-redeploy.
- **Updating the DB:** re-gzip `baseline.db`, upload a NEW release asset, update `DB_URL`.

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
