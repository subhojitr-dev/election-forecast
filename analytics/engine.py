"""
engine.py  —  Phase 3 analytics engine (orchestrator)
Election Forecast Dashboard

Reads the current `results_live` snapshot + the 2020 baseline, runs the four
intelligence steps (shift -> rollup -> projection -> win probability), and:

  1. returns a full analytics "bundle" for a state+race (what the API/UI need),
  2. appends a row to `live_snapshots` — the time-series that powers the
     convergence chart (Panel 5) and "is the lead growing/shrinking" (Issue #4).

Run a self-contained demo that replays a real election and shows the win
probability evolving, then converging:

    python analytics/engine.py GA president 2020      # replay GA 2020 w/ analytics
    python analytics/engine.py PA senate 2024
"""

from __future__ import annotations

import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "ingestor"))   # reuse poller/replay
sys.path.insert(0, HERE)

import bayesian_model as bm
import rollup as rollup_mod
from shift_calculator import (project_final_share, two_party_share,
                              weighted_shift)

DB_PATH = os.path.join(ROOT, "data", "db", "baseline.db")


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Snapshot-history table (the time-series; addresses Issue #4)
# ---------------------------------------------------------------------------
SNAPSHOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS live_snapshots (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  captured_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  state               TEXT,
  race_type           TEXT,
  baseline_year       INTEGER,
  precincts_reporting INTEGER,
  total_precincts     INTEGER,
  pct_reporting       REAL,
  dem_votes           INTEGER,
  rep_votes           INTEGER,
  total_votes         INTEGER,
  dem_share_2pty      REAL,
  statewide_shift     REAL,
  projected_dem_share REAL,
  win_prob_dem        REAL,
  confidence_tier     TEXT
);
CREATE INDEX IF NOT EXISTS idx_snap ON live_snapshots(state, race_type, captured_at);
-- performance: results_live is scanned per state every poll/sim step
CREATE INDEX IF NOT EXISTS idx_rl_race ON results_live(race_type, precinct_id);
CREATE INDEX IF NOT EXISTS idx_rl_precinct ON results_live(precinct_id);
"""


def ensure_schema(conn):
    conn.executescript(SNAPSHOT_SCHEMA)
    # results_live gained a 'mode' column (ballot type: election_day / early /
    # mail / military / all) for the outstanding-vote + red-mirage analysis.
    # Add it in place on existing DBs so we don't force a full ETL rebuild.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(results_live)")]
    if "mode" not in cols:
        conn.execute("ALTER TABLE results_live ADD COLUMN mode TEXT DEFAULT 'all'")
    conn.commit()


# ---------------------------------------------------------------------------
# The core computation
# ---------------------------------------------------------------------------
# The 2020/2024 baseline never changes at runtime — load each (state,race,year)
# once and cache it in memory. This is the single biggest speedup: it turns every
# analytics call from a ~0.4s disk aggregation into in-memory arithmetic.
_BASELINE_CACHE = {}


def _load_baseline(conn, state_abbr, race_type, baseline_year):
    key = (state_abbr, race_type, baseline_year)
    cached = _BASELINE_CACHE.get(key)
    if cached is None:
        cached = {}
        for pid, d, r in conn.execute(
            """SELECT rh.precinct_id,
                      SUM(CASE WHEN rh.party='DEM' THEN rh.votes ELSE 0 END),
                      SUM(CASE WHEN rh.party='REP' THEN rh.votes ELSE 0 END)
               FROM results_historical rh JOIN precincts p ON rh.precinct_id=p.id
               WHERE p.state_abbr=? AND rh.race_type=? AND rh.election_year=?
               GROUP BY rh.precinct_id""", (state_abbr, race_type, baseline_year)):
            cached[pid] = (d or 0, r or 0)
        _BASELINE_CACHE[key] = cached
    return cached


def compute_state_analytics(conn, state_abbr, race_type, baseline_year=2020, light=False):
    """Run all four steps for one state+race against the current results_live.
    light=True skips the per-county rollups + watch list (Panels 7/8/9) — used by
    the multi-state strip and the simulation, which only need statewide numbers."""
    # --- baseline two-party per precinct (cached in memory; static data) ---
    base = _load_baseline(conn, state_abbr, race_type, baseline_year)

    # --- live two-party per precinct ---
    live = {}
    for pid, d, r in conn.execute(
        """SELECT precinct_id,
                  SUM(CASE WHEN party='DEM' THEN votes ELSE 0 END),
                  SUM(CASE WHEN party='REP' THEN votes ELSE 0 END)
           FROM results_live
           WHERE race_type=? AND precinct_id LIKE ?
           GROUP BY precinct_id""",
            (race_type, f"{state_abbr}-%")):
        live[pid] = (d or 0, r or 0)

    # --- counted totals ---
    counted_dem = sum(d for d, r in live.values())
    counted_rep = sum(r for d, r in live.values())

    # --- Step 1+2: per-precinct shift -> statewide weighted shift ---
    shift_items = []
    for pid, (ld, lr) in live.items():
        if pid not in base:
            continue                      # unmatched precinct (crosswalk territory)
        bd, br = base[pid]
        bs, ls = two_party_share(bd, br), two_party_share(ld, lr)
        if bs is None or ls is None:
            continue
        shift_items.append((ls - bs, ld + lr))   # weight = two-party votes cast
    statewide_shift = weighted_shift(shift_items)

    # --- remaining (not-yet-reported) baseline ---
    remaining = [pid for pid in base if pid not in live]
    rem_dem = sum(base[pid][0] for pid in remaining)
    rem_rep = sum(base[pid][1] for pid in remaining)
    rem_total2 = rem_dem + rem_rep
    rem_dem_share = two_party_share(rem_dem, rem_rep)

    # --- % reporting (prefer the feed's own counts in results_live) ---
    row = conn.execute(
        """SELECT MAX(precincts_reporting), MAX(total_precincts)
           FROM results_live WHERE race_type=? AND precinct_id LIKE ?""",
        (race_type, f"{state_abbr}-%")).fetchone()
    reporting = row[0] or len(live)
    total_prec = row[1] or len(base)
    pct = (100.0 * reporting / total_prec) if total_prec else 0.0

    # --- Step 3: projection, with swing damped by how much is in ---
    weight = bm.reporting_weight(pct)
    projected = project_final_share(counted_dem, counted_rep, rem_total2,
                                    rem_dem_share, statewide_shift, weight)

    # --- Step 4: win probability + labels ---
    prob, sigma = bm.win_probability(projected, pct)
    tier = bm.confidence_tier(pct)
    lean = bm.lean_label(prob)

    # --- baseline statewide two-party share (the dashed line in Panel 5) ---
    base_dem_tot = sum(d for d, r in base.values())
    base_rep_tot = sum(r for d, r in base.values())
    baseline_dem_share = two_party_share(base_dem_tot, base_rep_tot)

    # --- leading D / R candidate names (for the vote bar, Panel 4) ---
    dem_candidate = rep_candidate = None
    for party, cand in conn.execute(
        """SELECT party, candidate FROM results_live
           WHERE race_type=? AND precinct_id LIKE ? AND party IN ('DEM','REP')
           GROUP BY candidate ORDER BY SUM(votes) DESC""",
            (race_type, f"{state_abbr}-%")):
        if party == "DEM" and dem_candidate is None:
            dem_candidate = cand
        elif party == "REP" and rep_candidate is None:
            rep_candidate = cand

    # --- county rollups + watch list (Panels 7/8/9) — skipped in light mode ---
    if light:
        counties, watch = [], []
    else:
        counties = rollup_mod.county_rollups(conn, state_abbr, race_type, baseline_year)
        watch = rollup_mod.watch_list(counties)

    return {
        "baseline_dem_share": baseline_dem_share,
        "dem_candidate": dem_candidate, "rep_candidate": rep_candidate,
        "state": state_abbr, "race_type": race_type, "baseline_year": baseline_year,
        "precincts_reporting": reporting, "total_precincts": total_prec,
        "pct_reporting": pct,
        "dem_votes": counted_dem, "rep_votes": counted_rep,
        "total_votes": counted_dem + counted_rep,
        "dem_share_2pty": two_party_share(counted_dem, counted_rep),
        "statewide_shift": statewide_shift,
        "projected_dem_share": projected,
        "win_prob_dem": prob, "sigma": sigma,
        "confidence_tier": tier, "lean": lean,
        "counties": counties, "watch_list": watch,
    }


def record_snapshot(conn, b, commit=True):
    """Append the statewide bundle to live_snapshots (the time-series)."""
    conn.execute(
        """INSERT INTO live_snapshots
           (state, race_type, baseline_year, precincts_reporting, total_precincts,
            pct_reporting, dem_votes, rep_votes, total_votes, dem_share_2pty,
            statewide_shift, projected_dem_share, win_prob_dem, confidence_tier)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (b["state"], b["race_type"], b["baseline_year"], b["precincts_reporting"],
         b["total_precincts"], b["pct_reporting"], b["dem_votes"], b["rep_votes"],
         b["total_votes"], b["dem_share_2pty"], b["statewide_shift"],
         b["projected_dem_share"], b["win_prob_dem"], b["confidence_tier"]))
    if commit:
        conn.commit()


def make_recorder(state_abbr, race_type, baseline_year=2020, verbose=True):
    """
    Build an on_write hook for the poller: after each poll, compute analytics
    and append a snapshot. Returns a function (conn, snap) -> None.
    """
    def _hook(conn, snap):
        ensure_schema(conn)
        b = compute_state_analytics(conn, state_abbr, race_type, baseline_year)
        record_snapshot(conn, b)
        if verbose:
            shift = b["statewide_shift"]
            shift_s = f"{shift:+.3f}" if shift is not None else "  n/a"
            proj = b["projected_dem_share"]
            proj_s = f"{proj*100:5.2f}%" if proj is not None else "  n/a"
            log(f"        ↳ shift {shift_s}  proj D {proj_s}  "
                f"P(D win) {b['win_prob_dem']*100:5.1f}%  "
                f"[{b['lean']} · {b['confidence_tier']}]")
    return _hook


# ---------------------------------------------------------------------------
# Demo: replay a real election WITH analytics recorded each poll
# ---------------------------------------------------------------------------
def main():
    state = sys.argv[1] if len(sys.argv) > 1 else "GA"
    race = sys.argv[2] if len(sys.argv) > 2 else "president"
    year = int(sys.argv[3]) if len(sys.argv) > 3 else 2020
    swing = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0  # +toward D, -toward R
    noise = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0  # per-precinct variation

    from clarity_poller import run_poller
    from replay_harness import ReplayFeed

    swing_note = f"  (synthetic swing {swing:+.3f} vs {year} baseline)" if swing else ""
    log(f"REPLAY + ANALYTICS — {state} {race} {year}{swing_note}\n")
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE ?",
                 (race, f"{state}-%"))
    conn.execute("DELETE FROM live_snapshots WHERE state=? AND race_type=?",
                 (state, race))
    conn.commit(); conn.close()

    feed = ReplayFeed(state, race, year, steps=12, order="county",
                      swing=swing, swing_noise=noise)
    run_poller(feed, interval=0, db_path=DB_PATH,
               on_write=make_recorder(state, race, year))

    # independent verification of the recorded time-series
    conn = sqlite3.connect(DB_PATH)
    log("\n" + "=" * 72)
    log("RECORDED TIME-SERIES (live_snapshots) — the convergence/trend data")
    log("=" * 72)
    log(f"  {'pct':>6} {'D votes':>10} {'R votes':>10} {'shift':>7} "
        f"{'projD':>7} {'P(Dwin)':>8}  tier")
    for r in conn.execute(
        """SELECT pct_reporting, dem_votes, rep_votes, statewide_shift,
                  projected_dem_share, win_prob_dem, confidence_tier
           FROM live_snapshots WHERE state=? AND race_type=?
           ORDER BY id""", (state, race)):
        pct, dv, rv, sh, pj, wp, tier = r
        sh = f"{sh:+.3f}" if sh is not None else "  n/a"
        pj = f"{pj*100:5.1f}%" if pj is not None else "  n/a"
        log(f"  {pct:5.1f}% {dv:>10,} {rv:>10,} {sh:>7} {pj:>7} "
            f"{wp*100:6.1f}%  {tier}")
    n = conn.execute("SELECT COUNT(*) FROM live_snapshots WHERE state=? AND race_type=?",
                     (state, race)).fetchone()[0]
    conn.close()
    log("=" * 72)
    log(f"{n} snapshots recorded. (Final projection should ~match the certified result.)")


if __name__ == "__main__":
    main()
