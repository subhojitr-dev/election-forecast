"""
integration_test.py  —  Phase 6 end-to-end integration test
Election Forecast Dashboard

Replays the TRUE results for all 8 states (President + Senate) through the real
pipeline (ReplayFeed -> poller -> results_live -> analytics) and ASSERTS that:
  1. live totals converge EXACTLY to the certified/baseline totals at 100%, and
  2. the computed winner matches the real historical winner.

This is the repeatable version of the manual checks done during the build.
Run:  python integration_test.py     (exit 0 = all pass, 1 = any fail)

Note: this repopulates results_live with the true 100% snapshot for every state.
"""

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "ingestor"))
sys.path.insert(0, os.path.join(ROOT, "analytics"))

from clarity_poller import DB_PATH, run_poller
from replay_harness import ReplayFeed
from shift_calculator import two_party_share

# per-state Senate reference year (mirrors api.main.SENATE_BASELINE)
# GA = 2021 Jan-5 runoff (Ossoff WON the seat that's up again in 2026), not the
# Nov-2020 general where Perdue led under the 50% GA majority threshold.
SENATE_YEAR = {"GA": 2021, "NC": 2020, "AZ": 2024, "MI": 2024,
               "PA": 2024, "NV": 2024, "WI": 2024, "TX": 2024}

# real winners
PRES_WIN = {"GA": "D", "PA": "D", "AZ": "D", "NV": "D", "WI": "D", "MI": "D",
            "NC": "R", "TX": "R"}
# GA Senate = D: Ossoff won the Jan-2021 runoff (the Nov general went to a runoff).
SEN_WIN = {"GA": "D", "NC": "R", "AZ": "D", "MI": "D", "PA": "R", "NV": "D",
           "WI": "D", "TX": "R"}
STATES = list(PRES_WIN.keys())


def totals(conn, table, state, race, year=None):
    if table == "live":
        rows = conn.execute(
            """SELECT party, SUM(votes) FROM results_live
               WHERE race_type=? AND precinct_id LIKE ? GROUP BY party""",
            (race, f"{state}-%")).fetchall()
    else:
        rows = conn.execute(
            """SELECT rh.party, SUM(rh.votes) FROM results_historical rh
               JOIN precincts p ON rh.precinct_id=p.id
               WHERE p.state_abbr=? AND rh.race_type=? AND rh.election_year=?
               GROUP BY rh.party""", (state, race, year)).fetchall()
    return {p: v for p, v in rows}


def check(state, race, year, expected_winner):
    feed = ReplayFeed(state, race, year, steps=1, order="county")  # one batch = 100%
    run_poller(feed, interval=0, db_path=DB_PATH, verbose=False)
    conn = sqlite3.connect(DB_PATH)
    live = totals(conn, "live", state, race)
    hist = totals(conn, "hist", state, race, year)
    conn.close()
    converged = all(live.get(p, 0) == hist.get(p, 0) for p in set(live) | set(hist))
    winner = "D" if live.get("DEM", 0) >= live.get("REP", 0) else "R"
    return converged, winner, (winner == expected_winner)


def main():
    print("PHASE 6 INTEGRATION TEST — replay true results, assert convergence + winners")
    print("=" * 76)
    print(f"  {'race':10}{'st':4}{'yr':6}{'converged':>11}{'winner':>8}{'expect':>8}{'result':>8}")
    ok = True
    for race, wins in (("president", PRES_WIN), ("senate", SEN_WIN)):
        for st in STATES:
            year = 2020 if race == "president" else SENATE_YEAR[st]
            conv, win, win_ok = check(st, race, year, wins[st])
            passed = conv and win_ok
            ok = ok and passed
            print(f"  {race:10}{st:4}{year:<6}{('YES' if conv else 'NO'):>11}"
                  f"{win:>8}{wins[st]:>8}{('PASS' if passed else 'FAIL'):>8}")
    print("=" * 76)
    print(f"OVERALL: {'PASS - pipeline reproduces reality end-to-end' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
