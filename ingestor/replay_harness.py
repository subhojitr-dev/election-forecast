"""
replay_harness.py  —  Phase 2 archived-replay testing
Election Forecast Dashboard

Since there is no live 2026 data yet (and Clarity's CDN blocks scraping today),
the most realistic way to exercise the whole pipeline is to REPLAY a real past
election we already trust: the certified precinct results sitting in baseline.db.

ReplayFeed takes a real (state, race, year) from results_historical and reveals
its precincts a batch at a time — exactly how precinct-level results trickle in
on election night (each precinct appears with its full count once it reports).
The poller writes each batch to results_live, so we can watch the live totals
build up and confirm they converge to the certified result at 100%.

Run:
    python ingestor/replay_harness.py                 # GA 2020 President, 12 steps
    python ingestor/replay_harness.py PA senate 2024  # any race we have loaded
"""

from __future__ import annotations

import math
import os
import random
import sqlite3
import sys
from typing import Optional

from clarity_poller import (DB_PATH, FeedSource, LiveRow, Snapshot, log,
                            run_poller)


# --- Synthetic ballot-mode profile for the turnout / red-mirage TEST scenario ---
# dfrac/rfrac = how each mode splits a precinct's DEM / REP votes (each sums to 1),
# chosen so MAIL leans Democratic and ELECTION-DAY leans Republican while the
# precinct totals stay exact. MODE_RELEASE = which batch each mode starts showing
# up in, so day-of reports first and mail lands later (the red-mirage -> blue-shift).
MODE_ORDER = ["election_day", "early", "mail", "military"]
MODE_DFRAC = {"election_day": 0.40, "early": 0.22, "mail": 0.35, "military": 0.03}
MODE_RFRAC = {"election_day": 0.58, "early": 0.22, "mail": 0.17, "military": 0.03}
MODE_RELEASE = {"election_day": 1, "early": 1, "mail": 3, "military": 4}


class ReplayFeed(FeedSource):
    """
    Replays a real race from baseline.db by revealing precincts incrementally.

    order='shuffle' : precincts report in a deterministic random order (default)
    order='county'  : whole counties report together (more realistic batching)
    steps           : how many snapshots from first report -> 100% reporting
    """
    def __init__(self, state_abbr: str, race_type: str, election_year: int,
                 steps: int = 12, order: str = "shuffle", seed: int = 42,
                 swing: float = 0.0, swing_noise: float = 0.0,
                 dem_name: str = None, rep_name: str = None, db_path: str = DB_PATH,
                 mode_split: bool = False, turnout_bump: float = 0.0,
                 bump_top_counties: int = 0):
        self.state_abbr = state_abbr
        self.race_type = race_type
        self.election_year = election_year
        self.steps = steps
        # optional candidate relabeling (for hypothetical scenarios, e.g.
        # "JON OSSOFF" vs "JD VANCE" over the real 2020/2024 vote geography)
        self.dem_name = dem_name
        self.rep_name = rep_name
        # swing: uniform two-party shift toward DEM (+) or REP (-) applied to
        # every precinct, e.g. -0.03 simulates "like 2020 but R+3". swing_noise
        # adds per-precinct variation (so counties move by different amounts —
        # realistic, and exercises the county-shift panels). Lets us test that
        # the analytics detect a swing the same-year replay can't show.
        self.swing = swing
        self.swing_noise = swing_noise
        # --- synthetic ballot-mode + turnout knobs (the red-mirage test scenario) ---
        self.mode_split = mode_split          # split votes into election_day/early/mail/military
        self.turnout_bump = turnout_bump      # extra turnout in the biggest counties
        self.bump_top_counties = bump_top_counties
        self.bump_counties: set = set()

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            """SELECT p.id, p.county, rh.candidate, rh.party, rh.votes
               FROM results_historical rh JOIN precincts p ON rh.precinct_id = p.id
               WHERE p.state_abbr=? AND rh.race_type=? AND rh.election_year=?""",
            (state_abbr, race_type, election_year)).fetchall()
        conn.close()
        if not rows:
            raise ValueError(f"No baseline data for {state_abbr} {race_type} "
                             f"{election_year} — is it loaded in baseline.db?")

        # group votes by precinct
        self.by_precinct: dict[str, list[tuple]] = {}
        self.county_of: dict[str, str] = {}
        for pid, county, cand, party, votes in rows:
            self.by_precinct.setdefault(pid, []).append((cand, party, votes))
            self.county_of[pid] = county

        # pick the N most populous counties (by baseline votes) to apply the
        # synthetic turnout bump to — the "populous counties" in the test scenario.
        if self.bump_top_counties:
            ctot: dict[str, int] = {}
            for pid, plist in self.by_precinct.items():
                ctot[self.county_of[pid]] = ctot.get(self.county_of[pid], 0) + sum(v for _, _, v in plist)
            self.bump_counties = set(sorted(ctot, key=ctot.get, reverse=True)[:self.bump_top_counties])

        # build the reporting order / model
        self.reveal_mode = order
        precincts = list(self.by_precinct.keys())
        rnd = random.Random(seed)
        if order == "proportional":
            # Every county reports GRADUALLY and IN PARALLEL — at X% statewide,
            # each county is ~X% in (with a per-county random "speed" so some run
            # ahead/behind). More like real life, and lets you watch a county go
            # partial -> full. (Avoids the "one whole county at a time" artifact.)
            self.county_precincts = {}
            for pid in sorted(precincts):
                self.county_precincts.setdefault(self.county_of[pid], []).append(pid)
            if all(len(pl) == 1 for pl in self.county_precincts.values()):
                # County-GRAINED data (one pseudo-precinct per county, e.g. the GA
                # runoff baselines) can't be revealed sub-county, so proportional
                # rounding makes the % jumpy and leaves the first batch empty. Fall
                # back to whole-county reveal — a smooth, even statewide % instead.
                order = self.reveal_mode = "county"
            else:
                self.county_speed = {c: min(1.6, max(0.4, rnd.gauss(1.0, 0.25)))
                                     for c in self.county_precincts}
        if order == "county":
            counties = sorted(set(self.county_of.values()))
            rnd.shuffle(counties)
            cidx = {c: i for i, c in enumerate(counties)}
            precincts.sort(key=lambda pid: (cidx[self.county_of[pid]], pid))
        elif order != "proportional":
            rnd.shuffle(precincts)
        self.order = precincts
        self.total = len(precincts)
        self._step = 0

        # precompute a per-precinct swing ONCE (so a precinct's totals are stable
        # across polls), with optional gaussian variation around the base swing.
        self.pswing = {}
        if self.swing or self.swing_noise:
            for pid in self.by_precinct:
                s = rnd.gauss(self.swing, self.swing_noise) if self.swing_noise else self.swing
                self.pswing[pid] = max(-0.25, min(0.25, s))

    def next_snapshot(self) -> Optional[Snapshot]:
        if self._step >= self.steps:
            return None
        self._step += 1
        if self.reveal_mode == "proportional":
            revealed = self._proportional_revealed()
        else:
            k = self.total if self._step == self.steps else \
                math.ceil(self.total * self._step / self.steps)
            revealed = self.order[:k]
        out: list[LiveRow] = []
        for pid in revealed:
            rows = self.by_precinct[pid]
            if self.pswing:
                rows = self._apply_swing(pid, rows)
            bump = (1.0 + self.turnout_bump) if self.county_of[pid] in self.bump_counties else 1.0
            for cand, party, votes in rows:
                name = cand
                if party == "DEM" and self.dem_name:
                    name = self.dem_name
                elif party == "REP" and self.rep_name:
                    name = self.rep_name
                v = votes * bump
                if not self.mode_split:
                    out.append(LiveRow(pid, name, party or "OTH", int(round(v)), "all"))
                    continue
                # split across ballot modes; only modes RELEASED by this batch show up
                frac = MODE_DFRAC if party == "DEM" else (MODE_RFRAC if party == "REP" else None)
                for m in MODE_ORDER:
                    if MODE_RELEASE[m] > self._step:
                        continue
                    share = frac[m] if frac else (1.0 if m == "election_day" else 0.0)
                    mv = int(round(v * share))
                    if mv:
                        out.append(LiveRow(pid, name, party or "OTH", mv, m))
        return Snapshot(version=f"step-{self._step}", rows=out,
                        precincts_reporting=len(revealed), total_precincts=self.total,
                        label=f"step {self._step}/{self.steps}")

    def _proportional_revealed(self):
        """Reveal ~the same fraction of EVERY county (×its speed). At the final
        step every county is forced to 100% so totals match certified."""
        f = self._step / self.steps
        revealed = []
        for county, plist in self.county_precincts.items():
            if self._step >= self.steps:
                cnt = len(plist)
            else:
                cnt = min(len(plist),
                          int(round(len(plist) * min(1.0, f * self.county_speed[county]))))
            revealed.extend(plist[:cnt])
        return revealed

    def _apply_swing(self, pid, rows):
        """Shift this precinct's two-party split by its precomputed swing toward
        DEM, keeping two-party total constant and minor parties unchanged."""
        swing = self.pswing.get(pid, 0.0)
        d2 = sum(v for _, p, v in rows if p == "DEM")
        r2 = sum(v for _, p, v in rows if p == "REP")
        tp = d2 + r2
        if tp == 0 or d2 == 0 or r2 == 0:
            return rows
        target_d = min(tp, max(0, round(tp * (d2 / tp + swing))))
        d_scale = target_d / d2
        r_scale = (tp - target_d) / r2
        out = []
        for cand, party, votes in rows:
            if party == "DEM":
                out.append((cand, party, round(votes * d_scale)))
            elif party == "REP":
                out.append((cand, party, round(votes * r_scale)))
            else:
                out.append((cand, party, votes))
        return out


def verify_convergence(state_abbr, race_type, election_year, db_path=DB_PATH):
    """At 100% reporting, live totals must equal the certified baseline totals."""
    conn = sqlite3.connect(db_path)
    q = """SELECT {tbl}.party, SUM({tbl}.votes)
           FROM {join}
           WHERE {where} GROUP BY {tbl}.party"""
    live = dict(conn.execute(
        """SELECT party, SUM(votes) FROM results_live
           WHERE race_type=? AND precinct_id LIKE ? GROUP BY party""",
        (race_type, f"{state_abbr}-%")).fetchall())
    hist = dict(conn.execute(
        """SELECT rh.party, SUM(rh.votes)
           FROM results_historical rh JOIN precincts p ON rh.precinct_id=p.id
           WHERE p.state_abbr=? AND rh.race_type=? AND rh.election_year=?
           GROUP BY rh.party""",
        (state_abbr, race_type, election_year)).fetchall())
    conn.close()

    log("\n" + "=" * 60)
    log(f"CONVERGENCE CHECK — {state_abbr} {race_type} {election_year}")
    log("=" * 60)
    log(f"  {'party':6}{'live':>12}{'certified':>12}  match")
    ok = True
    for party in sorted(set(live) | set(hist)):
        lv, hv = live.get(party, 0), hist.get(party, 0)
        match = (lv == hv)
        ok = ok and match
        log(f"  {party:6}{lv:>12,}{hv:>12,}  {'✓' if match else '✗ MISMATCH'}")
    log("=" * 60)
    log(f"RESULT: {'PASS ✅ live == certified at 100%' if ok else 'FAIL ❌'}")
    return ok


def main():
    state = sys.argv[1] if len(sys.argv) > 1 else "GA"
    race = sys.argv[2] if len(sys.argv) > 2 else "president"
    year = int(sys.argv[3]) if len(sys.argv) > 3 else 2020

    log(f"REPLAY — {state} {race} {year} (real certified data, revealed in steps)\n")
    feed = ReplayFeed(state, race, year, steps=12, order="county")

    # fresh slate for this race+state in results_live
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE ?",
                 (race, f"{state}-%"))
    conn.commit(); conn.close()

    run_poller(feed, interval=0, db_path=DB_PATH)   # interval=0 = fast replay
    ok = verify_convergence(state, race, year)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
