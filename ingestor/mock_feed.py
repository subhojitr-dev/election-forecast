"""
mock_feed.py  —  Phase 2 synthetic feed for edge-case testing
Election Forecast Dashboard

ReplayFeed (replay_harness.py) replays REAL past elections. MockFeed instead
generates SYNTHETIC results we fully control, so we can deliberately test
scenarios that a single archived election may not show us — most importantly the
"red mirage / blue shift" the brief warns about:

    Election-day precincts (more Republican) often report first; mail/early
    precincts (more Democratic) report later. So the early picture can show an
    R lead that erodes as more reports in — a mirage.

MockFeed can order its synthetic precincts reddest-first to reproduce exactly
that, letting us confirm the dashboard's analytics behave sensibly when an early
lead is misleading. It uses an isolated 'ZZ' pseudo-state so it never touches
real baseline rows.

Run:
    python ingestor/mock_feed.py            # red-mirage demo (D wins after looking R)
"""

from __future__ import annotations

import math
import random
import sqlite3
from typing import Optional

from clarity_poller import DB_PATH, FeedSource, LiveRow, Snapshot, log, run_poller

MOCK_STATE = "ZZ"


class MockFeed(FeedSource):
    """
    Generate `n_precincts` synthetic precincts whose final two-party split lands
    near `target_dem_share`, then reveal them in `steps` batches.

    red_mirage=True reveals the most-Republican precincts first, so the early
    snapshots lean R and the result "shifts blue" as it completes.
    """
    race_type = "president"
    state_abbr = MOCK_STATE

    def __init__(self, n_precincts: int = 200, target_dem_share: float = 0.52,
                 spread: float = 0.18, steps: int = 12, red_mirage: bool = True,
                 seed: int = 7):
        rnd = random.Random(seed)
        self.steps = steps
        self.precincts = []
        for i in range(n_precincts):
            size = rnd.randint(300, 3000)                 # ballots in precinct
            share = min(0.97, max(0.03, rnd.gauss(target_dem_share, spread)))
            dem = round(size * share)
            rep = size - dem
            pid = f"{MOCK_STATE}-99999-MOCK{i:04d}"
            self.precincts.append((pid, dem, rep, share))

        # reporting order: reddest precincts first => red mirage
        self.precincts.sort(key=lambda p: p[3], reverse=not red_mirage)
        self.total = len(self.precincts)
        self._step = 0

        # store the ground truth for later verification
        self.truth_dem = sum(p[1] for p in self.precincts)
        self.truth_rep = sum(p[2] for p in self.precincts)

    def next_snapshot(self) -> Optional[Snapshot]:
        if self._step >= self.steps:
            return None
        self._step += 1
        k = self.total if self._step == self.steps else \
            math.ceil(self.total * self._step / self.steps)
        rows: list[LiveRow] = []
        for pid, dem, rep, _ in self.precincts[:k]:
            rows.append(LiveRow(pid, "MOCK DEMOCRAT", "DEM", dem))
            rows.append(LiveRow(pid, "MOCK REPUBLICAN", "REP", rep))
        return Snapshot(version=f"mock-{self._step}", rows=rows,
                        precincts_reporting=k, total_precincts=self.total,
                        label=f"mock {self._step}/{self.steps}")


def main():
    log("MOCK red-mirage demo: a race that LOOKS Republican early, finishes Dem.\n")
    feed = MockFeed(n_precincts=200, target_dem_share=0.52, red_mirage=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM results_live WHERE precinct_id LIKE ?", (f"{MOCK_STATE}-%",))
    conn.commit(); conn.close()

    run_poller(feed, interval=0, db_path=DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    live = dict(conn.execute(
        """SELECT party, SUM(votes) FROM results_live
           WHERE precinct_id LIKE ? GROUP BY party""", (f"{MOCK_STATE}-%",)).fetchall())
    conn.execute("DELETE FROM results_live WHERE precinct_id LIKE ?", (f"{MOCK_STATE}-%",))
    conn.commit(); conn.close()

    log("\n" + "=" * 60)
    log("FINAL vs GROUND TRUTH")
    log("=" * 60)
    log(f"  DEM  live {live.get('DEM',0):>9,}  truth {feed.truth_dem:>9,}  "
        f"{'✓' if live.get('DEM',0)==feed.truth_dem else '✗'}")
    log(f"  REP  live {live.get('REP',0):>9,}  truth {feed.truth_rep:>9,}  "
        f"{'✓' if live.get('REP',0)==feed.truth_rep else '✗'}")
    winner = "DEM" if feed.truth_dem > feed.truth_rep else "REP"
    log(f"  Final winner: {winner}  (note the R leads in the early polls above)")
    log("=" * 60)
    log("(cleaned up mock rows from results_live)")


if __name__ == "__main__":
    main()
