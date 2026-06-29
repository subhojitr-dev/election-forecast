"""
main.py — FastAPI server
Election Forecast Dashboard (Phase 4)

Exposes the Phase 3 analytics over HTTP (REST) + a live WebSocket, so the
React UI (Phase 5) can render the 10 panels. The API is read-only: it computes
analytics on demand from the DB that the ingestor (Phase 2) keeps current.

Run:
    uvicorn api.main:app --reload --port 8000
    # then:  http://localhost:8000/docs   (interactive API explorer)

Endpoints (mapped to the UI panels):
    GET  /api/health
    GET  /api/states?race=president          -> swing-state strip + EV (Panels 1,10)
    GET  /api/state/{abbr}?race=president     -> full detail bundle for one state
    GET  /api/state/{abbr}/series?race=...    -> convergence time-series (Panel 5)
    WS   /ws?race=president                   -> pushes updated strip when live changes
"""

from __future__ import annotations

import asyncio
import os
import sys

from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                              # so `from db import ...` works
sys.path.insert(0, os.path.join(ROOT, "analytics"))
sys.path.insert(0, os.path.join(ROOT, "ingestor"))

import bayesian_model as bm
import elections
import engine  # analytics orchestrator
import rollup
import simulation
from db import get_conn

# Electoral votes (2024+ apportionment) + display names, for the EV tracker.
EV = {"GA": 16, "PA": 19, "AZ": 11, "NV": 6, "WI": 10, "MI": 15, "NC": 16, "TX": 40}
STATE_NAMES = {"GA": "Georgia", "PA": "Pennsylvania", "AZ": "Arizona",
               "NV": "Nevada", "WI": "Wisconsin", "MI": "Michigan",
               "NC": "North Carolina", "TX": "Texas"}
STATES = list(EV.keys())
# Per-election ballot manifest lives in elections.py (which races, which states,
# which baseline year per state). The dashboard reads from it, so a real election
# night only shows the contests actually happening (e.g. Nov-2026 = Senate Class-2
# seats, no President). baseline_for / states_for default to the "demo" election
# (= the historical all-races behavior) so existing callers stay simple.
DEFAULT_ELECTION = elections.DEFAULT_ELECTION


def baseline_for(state, race, election=DEFAULT_ELECTION):
    return elections.baseline_year(election, state, race)


def states_for(race, election=DEFAULT_ELECTION):
    return elections.states_for(election, race)

app = FastAPI(title="Election Forecast API", version="0.4.0")
# CORS: open in dev; in production set CORS_ORIGINS=https://your-app.vercel.app
# (comma-separated for multiple). See DEPLOY.md.
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"], allow_headers=["*"],
)

# Read endpoints change only ~every 60s -> cacheable. This header lets a CDN/edge
# cache absorb election-night traffic so only cache-misses hit FastAPI (DEPLOY.md §3).
READ_CACHE = "public, max-age=15, stale-while-revalidate=30"


def _summary(bundle: dict) -> dict:
    """Trim a full analytics bundle to the swing-state-strip fields."""
    return {
        "state": bundle["state"],
        "name": STATE_NAMES.get(bundle["state"], bundle["state"]),
        "ev": EV.get(bundle["state"]),
        "race_type": bundle["race_type"],
        "pct_reporting": round(bundle["pct_reporting"], 1),
        "precincts_reporting": bundle["precincts_reporting"],
        "total_precincts": bundle["total_precincts"],
        "dem_votes": bundle["dem_votes"], "rep_votes": bundle["rep_votes"],
        "dem_share_2pty": bundle["dem_share_2pty"],
        "statewide_shift": bundle["statewide_shift"],
        "projected_dem_share": bundle["projected_dem_share"],
        "win_prob_dem": bundle["win_prob_dem"],
        "lean": bundle["lean"], "confidence_tier": bundle["confidence_tier"],
    }


def _summary_from_snapshot(snap, st, race) -> dict:
    """Build the strip summary from a precomputed live_snapshots row (fast path)."""
    return {
        "state": st, "name": STATE_NAMES.get(st, st), "ev": EV.get(st),
        "race_type": race,
        "pct_reporting": round(snap["pct_reporting"], 1),
        "precincts_reporting": snap["precincts_reporting"],
        "total_precincts": snap["total_precincts"],
        "dem_votes": snap["dem_votes"], "rep_votes": snap["rep_votes"],
        "dem_share_2pty": snap["dem_share_2pty"],
        "statewide_shift": snap["statewide_shift"],
        "projected_dem_share": snap["projected_dem_share"],
        "win_prob_dem": snap["win_prob_dem"],
        "lean": bm.lean_label(snap["win_prob_dem"] or 0.5),
        "confidence_tier": snap["confidence_tier"],
    }


def _states_payload(race: str, election: str = DEFAULT_ELECTION) -> dict:
    """
    Read the LATEST snapshot per state (fast). The simulation/poller write these,
    so reads never trigger a heavy recompute. Any state missing a snapshot is
    seeded once (lazy) with a light compute. Only the election's states for this
    race are included (so Nov-2026 Senate shows just GA/MI/NC/TX, etc.).
    """
    conn = get_conn()
    try:
        engine.ensure_schema(conn)
        latest = {r["state"]: r for r in conn.execute(
            """SELECT s.* FROM live_snapshots s
               JOIN (SELECT state, MAX(id) mid FROM live_snapshots
                     WHERE race_type=? GROUP BY state) m ON s.id = m.mid""",
            (race,))}
        rows = []
        for st in states_for(race, election):
            snap = latest.get(st)
            if snap is None:  # seed once
                b = engine.compute_state_analytics(conn, st, race, baseline_for(st, race, election), light=True)
                engine.record_snapshot(conn, b)
                rows.append(_summary(b))
            else:
                rows.append(_summary_from_snapshot(snap, st, race))
    finally:
        conn.close()
    ev_dem = sum(r["ev"] for r in rows if (r["win_prob_dem"] or 0) >= 0.5)
    ev_rep = sum(r["ev"] for r in rows if (r["win_prob_dem"] or 0) < 0.5)
    return {"race_type": race, "election": election, "states": rows,
            "ev_leaning": {"dem": ev_dem, "rep": ev_rep}}


# ---- Simulation scenarios (the "for fun" hypotheticals plug in here) ----
SCENARIOS = {
    "president": {
        "true":        {"name": "True (real 2020 results)", "swing": 0.0, "noise": 0.0},
        "ossoff_vance": {"name": "Ossoff vs Vance · D+5", "swing": 0.05, "noise": 0.02,
                         "dem": "JON OSSOFF", "rep": "JD VANCE"},
        "aoc_vance":   {"name": "AOC vs Vance · D+5", "swing": 0.05, "noise": 0.02,
                        "dem": "ALEXANDRIA OCASIO-CORTEZ", "rep": "JD VANCE"},
        # SYNTHETIC test: +4% turnout in each state's 2 most-populous counties,
        # votes split by ballot type (mail leans D & reports late -> red mirage).
        "turnout_buckets": {"name": "TEST · +4% big-county turnout, by ballot type",
                            "swing": 0.02, "noise": 0.015, "mode_split": True,
                            "turnout_bump": 0.04, "bump_top_counties": 2},
    },
    "senate": {
        "true": {"name": "True (most-recent real results)", "swing": 0.0, "noise": 0.0},
        "dems_plus5": {"name": "Democrats D+5 (real candidates)", "swing": 0.05, "noise": 0.02},
    },
    # GA-only special seat — the Jan-2021 Warnock vs Loeffler runoff.
    "senate_special": {
        "true": {"name": "True (2021 GA runoff · Warnock)", "swing": 0.0, "noise": 0.0},
        "dems_plus5": {"name": "Democrats D+5 (real candidates)", "swing": 0.05, "noise": 0.02},
    },
}

sim = simulation.SimController()


@app.get("/api/elections")
def list_elections():
    """The ballot manifest: which elections exist + which races each one has.
    The UI builds its Election dropdown + race toggle from this."""
    return {"elections": elections.listing(), "default": DEFAULT_ELECTION}


@app.get("/api/scenarios")
def scenarios(race: str = Query("president")):
    s = SCENARIOS.get(race, {})
    return {"race": race, "scenarios": [{"id": k, "name": v["name"]} for k, v in s.items()]}


def _baseline_closure(election, race):
    return lambda st: baseline_for(st, race, election)


def _candidates_closure(election, race):
    return lambda st: elections.candidates(election, race, st)


@app.post("/api/sim/reset")
def sim_reset(race: str = Query("president"), scenario: str = Query("true"),
              election: str = Query(DEFAULT_ELECTION)):
    cfg = SCENARIOS.get(race, {}).get(scenario)
    if cfg is None:
        raise HTTPException(404, f"Unknown scenario {scenario} for {race}")
    return sim.reset(election, race, cfg, states_for(race, election),
                     _baseline_closure(election, race), _candidates_closure(election, race))


@app.post("/api/sim/next")
def sim_next(race: str = Query("president"), scenario: str = Query("true"),
             election: str = Query(DEFAULT_ELECTION)):
    if (election, race) not in sim.sessions:
        cfg = SCENARIOS.get(race, {}).get(scenario, {"name": "true", "swing": 0.0})
        sim.reset(election, race, cfg, states_for(race, election),
                  _baseline_closure(election, race), _candidates_closure(election, race))
    return sim.next(election, race)


@app.get("/api/sim/status")
def sim_status(race: str = Query("president"), election: str = Query(DEFAULT_ELECTION)):
    return sim.status(election, race)


@app.get("/api/health")
def health():
    conn = get_conn()
    try:
        n = conn.execute("SELECT COUNT(*) FROM results_historical").fetchone()[0]
        live = conn.execute("SELECT COUNT(*) FROM results_live").fetchone()[0]
    finally:
        conn.close()
    return {"status": "ok", "historical_rows": n, "live_rows": live}


@app.get("/api/states")
def states(response: Response, race: str = Query("president"), election: str = Query(DEFAULT_ELECTION)):
    """Panel 1 (swing-state strip) + Panel 10 (EV tracker)."""
    response.headers["Cache-Control"] = READ_CACHE
    return _states_payload(race, election)


@app.get("/api/state/{abbr}")
def state_detail(abbr: str, response: Response, race: str = Query("president"),
                 election: str = Query(DEFAULT_ELECTION)):
    """Full bundle for one state: vote bar, gauge, counties, watch list, series."""
    response.headers["Cache-Control"] = READ_CACHE
    abbr = abbr.upper()
    if abbr not in STATES:
        raise HTTPException(404, f"Unknown state {abbr}")
    conn = get_conn()
    try:
        engine.ensure_schema(conn)
        b = engine.compute_state_analytics(conn, abbr, race, baseline_for(abbr, race, election))
        series = [dict(r) for r in conn.execute(
            """SELECT pct_reporting, dem_share_2pty, projected_dem_share,
                      win_prob_dem, statewide_shift, captured_at
               FROM live_snapshots WHERE state=? AND race_type=? ORDER BY id""",
            (abbr, race))]
        modes = rollup.mode_breakdown(conn, abbr, race)
    finally:
        conn.close()
    b["name"] = STATE_NAMES.get(abbr, abbr)
    b["ev"] = EV.get(abbr)
    b["series"] = series
    b["modes"] = modes
    return b


@app.get("/api/state/{abbr}/series")
def state_series(abbr: str, race: str = Query("president")):
    """Panel 5 convergence time-series only (lighter payload)."""
    abbr = abbr.upper()
    conn = get_conn()
    try:
        series = [dict(r) for r in conn.execute(
            """SELECT pct_reporting, dem_share_2pty, projected_dem_share,
                      win_prob_dem, statewide_shift, confidence_tier, captured_at
               FROM live_snapshots WHERE state=? AND race_type=? ORDER BY id""",
            (abbr, race))]
    finally:
        conn.close()
    return {"state": abbr, "race_type": race, "series": series}


def _pending_lean(modes):
    """Infer which way the not-yet-counted vote likely leans from the mode mix:
    if mail (Dem-leaning) is still largely uncounted, the remainder breaks Dem."""
    md = {m["mode"]: m for m in modes}
    mail = md.get("mail", {}).get("total", 0)
    eday = md.get("election_day", {}).get("total", 0)
    if eday and mail < 0.4 * eday:
        return (" — and mail (which leans Democratic) is largely still uncounted, "
                "so the remaining vote likely breaks toward the Democrat")
    return ""


def _county_note(c, modes):
    """Plain-English read of one county for the dashboard note box."""
    pct = c.get("pct_reporting") or 0
    bits = [f"{c['county'].title()}: {pct:.0f}% of precincts reporting."]
    ds, b = c.get("dem_share_live"), c.get("dem_share_2020")
    if ds is not None and b is not None:
        diff = (ds - b) * 100
        word = "above" if diff >= 0 else "below"
        bits.append(f"Democrat at {ds*100:.1f}% vs the {b*100:.1f}% 2020 benchmark "
                    f"({diff:+.1f} pts — {word} benchmark).")
    lean = _pending_lean(modes)
    t = c.get("turnout_vs_2020")
    if t:
        if lean:   # mail still largely uncounted -> the extrapolated turnout misleads
            bits.append("Turnout vs 2020 still settling (mail not yet counted).")
        else:
            bits.append(f"Turnout tracking {(t-1)*100:+.0f}% vs 2020.")
    pend = c.get("pending_extrapolated") or 0
    if pend > 0:
        bits.append(f"~{pend:,.0f} two-party votes still to come{lean}.")
    return " ".join(bits)


@app.get("/api/state/{abbr}/county/{county}")
def county_detail(abbr: str, county: str, race: str = Query("president"),
                  election: str = Query(DEFAULT_ELECTION)):
    """One county: rollup + per-ballot-mode breakdown + a plain-English note
    (the county note box + bucket selector)."""
    abbr, cty = abbr.upper(), county.upper()
    conn = get_conn()
    try:
        engine.ensure_schema(conn)
        rollups = rollup.county_rollups(conn, abbr, race, baseline_for(abbr, race, election))
        match = next((c for c in rollups if c["county"] == cty), None)
        if match is None:
            raise HTTPException(404, f"Unknown county {county} in {abbr}")
        modes = rollup.mode_breakdown(conn, abbr, race, county=cty)
    finally:
        conn.close()
    match["modes"] = modes
    match["note"] = _county_note(match, modes)
    return match


def _fingerprint(race: str):
    """Cheap signal of whether live data changed (row count + latest timestamp)."""
    conn = get_conn()
    try:
        r = conn.execute(
            "SELECT COUNT(*), MAX(last_updated) FROM results_live WHERE race_type=?",
            (race,)).fetchone()
    finally:
        conn.close()
    return (r[0], r[1])


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    """Push the swing-state strip whenever live results change (election-night feel)."""
    await websocket.accept()
    race = websocket.query_params.get("race", "president")
    last_fp = None
    try:
        # send an initial snapshot immediately
        await websocket.send_json(_states_payload(race))
        last_fp = _fingerprint(race)
        while True:
            await asyncio.sleep(2)
            fp = _fingerprint(race)
            if fp != last_fp:
                last_fp = fp
                await websocket.send_json(_states_payload(race))
    except WebSocketDisconnect:
        return


@app.get("/")
def root():
    return {"service": "Election Forecast API", "docs": "/docs",
            "try": "/api/states?race=president"}
