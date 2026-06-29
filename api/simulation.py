"""
simulation.py — interactive "Next Batch" election-night simulator
Election Forecast Dashboard

Holds an in-memory stepper per (election, race) so the UI can advance results batch
by batch (20% -> 40% -> ... -> 100%) on a button click, mimicking precincts reporting
over the night. On the real election day this manual stepper is replaced by the
Phase 2 poller (which pulls the live feed every ~60s); the analytics/UI path is identical.

A "scenario" picks the data: true real results (swing 0, real candidate names) or a
hypothetical (uniform swing + relabeled candidates + synthetic ballot modes/turnout).

Sessions are keyed by (election, race) so different elections/races advance
independently and don't clobber each other.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "analytics"))
sys.path.insert(0, os.path.join(ROOT, "ingestor"))

import engine
from clarity_poller import write_snapshot
from db import get_conn
from replay_harness import ReplayFeed

BATCHES = 5   # 20% / 40% / 60% / 80% / 100%


class SimController:
    def __init__(self):
        self.sessions = {}   # (election, race) -> session

    def reset(self, election, race, scenario, states, baseline_of, candidates_of=None):
        """Build a fresh feed per state for this election's race and clear its live
        rows. `states` = the election's states for this race; baseline_of(st) -> year;
        candidates_of(st) -> {"dem","rep"} real nominee labels (optional)."""
        feeds = {}
        for st in states:
            cand = (candidates_of(st) if candidates_of else {}) or {}
            # scenario relabels (hypotheticals) win; else use the election's real nominees
            dem_name = scenario.get("dem") or cand.get("dem")
            rep_name = scenario.get("rep") or cand.get("rep")
            try:
                feeds[st] = ReplayFeed(
                    st, race, baseline_of(st), steps=BATCHES, order="proportional",
                    swing=scenario.get("swing", 0.0), swing_noise=scenario.get("noise", 0.0),
                    dem_name=dem_name, rep_name=rep_name,
                    mode_split=scenario.get("mode_split", False),
                    turnout_bump=scenario.get("turnout_bump", 0.0),
                    bump_top_counties=scenario.get("bump_top_counties", 0))
            except ValueError:
                continue   # this race doesn't exist for this state
        conn = get_conn()
        engine.ensure_schema(conn)
        for st in states:
            conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE ?",
                         (race, f"{st}-%"))
            conn.execute("DELETE FROM live_snapshots WHERE state=? AND race_type=?", (st, race))
        conn.commit()
        conn.close()
        self.sessions[(election, race)] = {
            "feeds": feeds, "step": 0, "scenario": scenario,
            "baseline": {st: baseline_of(st) for st in feeds},
        }
        return self.status(election, race)

    def next(self, election, race):
        sess = self.sessions.get((election, race))
        if not sess:
            return self.status(election, race)   # caller should reset first
        conn = get_conn()
        engine.ensure_schema(conn)
        advanced = False
        for st, feed in sess["feeds"].items():
            snap = feed.next_snapshot()
            if snap:
                write_snapshot(conn, race, st, snap, commit=False)
                b = engine.compute_state_analytics(conn, st, race, sess["baseline"][st], light=True)
                engine.record_snapshot(conn, b, commit=False)
                advanced = True
        conn.commit()   # one commit for the whole batch
        conn.close()
        if advanced:
            sess["step"] += 1
        return self.status(election, race)

    def status(self, election, race):
        sess = self.sessions.get((election, race))
        if not sess:
            return {"election": election, "race": race, "step": 0, "total": BATCHES,
                    "pct": 0, "scenario": None, "started": False}
        return {"election": election, "race": race, "step": sess["step"], "total": BATCHES,
                "pct": round(100 * sess["step"] / BATCHES),
                "scenario": sess["scenario"].get("name"),
                "started": sess["step"] > 0,
                "complete": sess["step"] >= BATCHES}
