# Election Forecast Dashboard

A real-time election-night forecasting dashboard. It holds certified past results
(2020 President; most-recent Senate per state) as a baseline, ingests live results
as precincts report, and compares live-vs-baseline to show each candidate's
current win probability — an open, precinct-level version of the "election needle".

> New here? Read **`DASHBOARD_GUIDE.md`** (how to read/use it) and **`CONTEXT.md`**
> (current project state). Full spec: `HANDOVER_BRIEF.md`.

## 🚀 Deployed
- **Backend (live):** https://election-forecast.onrender.com (Render). Try
  `/api/health`, `/docs`, or `/api/states?race=president&election=demo`.
- **Frontend:** Vercel — pending (deploy the `ui/` folder with `VITE_API_BASE`=the
  Render URL). Full plan + caching + scaling: **`DEPLOY.md`**.
- **Source:** github.com/subhojitr-dev/election-forecast (the 1.4 GB of data is
  gitignored — see `DATA_SETUP.md` to obtain/rebuild it).

---

## Running it locally

The app is **two programs** that run at the same time, each in its own terminal:

| # | Program | Port | What it does |
|---|---------|------|--------------|
| 1 | **API server** (FastAPI / Python) | `8000` | The data engine — runs the analysis and serves the numbers |
| 2 | **Web server** (Vite / React)     | `5173` | The dashboard you actually look at; it asks the API for data |

You only ever **open the dashboard (5173)** in your browser — it talks to the API
(8000) for you in the background. Both must be running.

### One-time setup (only needed once)
```powershell
# Python dependencies (from the project root)
cd C:\Users\subho\election-forecast
pip install -r requirements.txt

# Frontend dependencies
cd C:\Users\subho\election-forecast\ui
npm install
```

### Start the servers (each in its own PowerShell window — leave both open)

**Terminal 1 — API server** (run from the **project root**):
```powershell
cd C:\Users\subho\election-forecast
python -m uvicorn api.main:app --port 8000
```
You should see `Uvicorn running on http://127.0.0.1:8000`. Leave this window open.
(API docs, if curious: http://localhost:8000/docs)

**Terminal 2 — Web server** (run from the **`ui` folder**):
```powershell
cd C:\Users\subho\election-forecast\ui
npm run dev
```

### Then open the dashboard

> ### → http://localhost:5173

If you see a red **"API error … is the backend running on :8000?"** banner, it
just means Terminal 1 (the API) isn't running — start it and the banner clears.

---

## Stopping & restarting the servers

**When do you need to?**
- Changed **Python** code (`api/`, `analytics/`, `ingestor/`) → **restart the API**
  (it does not auto-reload). Then click **Reset** in the dashboard.
- Changed **UI** code (`ui/src/`) → nothing to do; the web server hot-reloads
  (a browser refresh at most). You rarely restart it.

### API server (port 8000)
```powershell
# STOP: in the API's PowerShell window, press  Ctrl + C
# ...or, if that window is gone, stop it by port:
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# RESTART (from the project root):
cd C:\Users\subho\election-forecast
python -m uvicorn api.main:app --port 8000
```
> After restarting the API, click **Reset** in the dashboard — it rebuilds the
> simulation so code changes take effect.

### Web server (port 5173)
```powershell
# STOP: in the Vite / npm window, press  Ctrl + C   (answer Y if asked)
# ...or stop it by port:
Get-NetTCPConnection -LocalPort 5173 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# RESTART (from the ui folder):
cd C:\Users\subho\election-forecast\ui
npm run dev
```
> Note: the web server auto-reloads UI changes, so you seldom need to restart it.

**"Port already in use" (Errno 10048)?** Something is still running on that port —
use the matching `Get-NetTCPConnection … Stop-Process` line above to free it, then
start again.

---

## Using the dashboard (quick version)

- Pick an **Election** (dropdown) — only the races on that ballot appear (e.g. the
  Nov-2026 midterm shows Senate only, no President).
- Use the **President / Senate / GA Special** toggle and click any **state card** to drill in.
- To simulate an election night: pick a **Scenario**, click **Reset**, then click
  **Next Batch ▶** repeatedly to reveal results 20% → 40% → … → 100%.
- Click a **county** in the table → the **County Insight** box (top-right) explains
  what's happening (turnout vs benchmark, votes pending + which way they lean); the
  **ballot-type tabs** (mail / early / election-day) show each bucket's status.
- Full walkthrough: **`DASHBOARD_GUIDE.md`**; step-by-step tests: **`TESTING.md`**.

To (re)load a race's data directly from the command line:
```powershell
python analytics/engine.py GA president 2020        # replay Georgia 2020
```

---

## Notes
- Windows PowerShell: don't chain with `&&` (use separate lines, or `;`).
- If `uvicorn` isn't recognized, the `python -m uvicorn …` form above always works.
- The API is started without auto-reload, so restart Terminal 1 after changing
  code under `api/`.

## Project docs
| File | Purpose |
|------|---------|
| `CONTEXT.md` | Current state — start here each session |
| `DASHBOARD_GUIDE.md` | How to read, run, and simulate the dashboard |
| `TESTING.md` | Plain-language test guide: what to click, what you should see |
| `HANDOVER_BRIEF.md` | Full spec (panels, model, schema, phase plan) |
| `QUICK_REFERENCE.md` | At-a-glance cheat sheet (schema, endpoints, URLs) |
| `DATA_SETUP.md` | Every data file: full path, contents, source/DOI |
| `DEPLOY.md` | Phase 7 deployment plan (Vercel + Render + caching) |
| `FEED_AUDIT.md` | Per-state live ENR feed audit (Clarity vs own; mode availability) |
| `PREP.md` | Election-night live-data readiness plan + timeline |
| `PROGRESS.md` | Chronological work log |
| `Issues.md` | Known issues, fixes, and the election-night readiness plan |
