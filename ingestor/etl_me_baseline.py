"""etl_me_baseline.py — Maine as a new state: 2020 Senate baseline (Collins'
last election, Class 2 — same class as GA/MI/NC/TX/SC, all last contested
2020, all up again in 2026 — same logic already used for those). Real 2026
race: Susan Collins (R, incumbent) vs Troy Jackson (D nominee, replacing
Graham Platner after he withdrew) — see elections.py's general2026 entry.

Source: `me_2020_senate_county_results.json`, a small (68-row, ~9KB) fixture
committed alongside this script — county-level DEM/REP/OTH/LIB vote totals
for ME's 2020 Senate race, extracted from the MEDSL national 2020 Senate
precinct file (doi:10.7910/DVN/ER9XTV, file id 6100391) and verified against
certified results (Collins 51.00% vs certified 50.98%, Gideon 42.40% vs
42.39% — see PROGRESS.md).

NOT downloaded at runtime, unlike etl_governor_2022.py's per-state files —
that file requires a Dataverse "Guestbook" response (a one-time human form,
confirmed 2026-08-08: "You may not download this file without the required
Guestbook response for guestbookID 458") before ANY download succeeds, so a
User-Agent fix (which solved the *different*, actually-bot-blocking 403 on
the Governor files) can't help here — this isn't bot detection, it's a real
access gate. Since Maine's own needed data is tiny and this is a fixed
historical fact that will never change, baking it into a small static file
sidesteps the whole problem: no download, no external dependency at all.

Maine uses ranked-choice voting for federal races, but the source file only
reported FIRST-CHOICE totals per precinct (no RCV elimination rounds) —
Collins won outright in the first round in 2020 (>50%, avoided an RCV
runoff), so first-choice = final result for that year anyway.

One Maine-specific wrinkle: county_name includes a "STATEWIDE UOCAVA" row
(military/overseas absentee ballots, not tied to a real county) alongside
the 16 real counties — treated as its own county-pseudo-precinct
(ME-23000-CTY) like any other, same as everywhere else in this project.

IMPORTANT: additive, like etl_governor_2022.py / etl_tx_county_baseline.py —
does NOT touch etl_baseline.py's destructive wipe-and-rebuild. Creates
ME-{fips}-CTY precinct rows and inserts results_historical scoped to
(race_type='senate', election_year=2020, precinct_id LIKE 'ME-%'). Idempotent
(deletes only its own prior rows first).

Run:  python ingestor/etl_me_baseline.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURE = os.path.join(HERE, "me_2020_senate_county_results.json")
DB = os.path.join(ROOT, "data", "db", "baseline.db")


def load():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def ingest(conn, rows, race_type="senate", year=2020):
    conn.execute("""DELETE FROM results_historical WHERE race_type=? AND election_year=?
                    AND precinct_id LIKE 'ME-%'""", (race_type, year))
    ctot: dict[str, int] = {}
    for r in rows:
        ctot[r["county_fips"]] = ctot.get(r["county_fips"], 0) + r["votes"]
    known = {r[0] for r in conn.execute("SELECT id FROM precincts WHERE id LIKE 'ME-%-CTY'")}
    new_precincts = inserted = 0
    for r in rows:
        pid = f"ME-{r['county_fips']}-CTY"
        if pid not in known:
            conn.execute("""INSERT INTO precincts
                            (id, state, state_abbr, county, county_fips, precinct_name)
                            VALUES (?,?,?,?,?,?)""",
                         (pid, "MAINE", "ME", r["county"], r["county_fips"], "COUNTY TOTAL"))
            known.add(pid)
            new_precincts += 1
        tot = ctot[r["county_fips"]]
        share = r["votes"] / tot if tot else 0.0
        conn.execute(
            """INSERT INTO results_historical
               (precinct_id, election_year, race_type, candidate, party, votes, vote_share)
               VALUES (?,?,?,?,?,?,?)""",
            (pid, year, race_type, r["candidate"], r["party"], r["votes"], share))
        inserted += 1
    d = conn.execute("""SELECT SUM(votes) FROM results_historical
                        WHERE race_type=? AND election_year=? AND party='DEM'
                          AND precinct_id LIKE 'ME-%'""", (race_type, year)).fetchone()[0]
    rep = conn.execute("""SELECT SUM(votes) FROM results_historical
                        WHERE race_type=? AND election_year=? AND party='REP'
                          AND precinct_id LIKE 'ME-%'""", (race_type, year)).fetchone()[0]
    print(f"  ME senate {year}: +{new_precincts} precincts, {inserted} rows — "
          f"DEM {d:,} / REP {rep:,} -> winner {'D' if d > rep else 'R'}")


def already_seeded(conn) -> bool:
    n = conn.execute(
        "SELECT COUNT(*) FROM results_historical WHERE race_type='senate' AND election_year=2020 "
        "AND precinct_id LIKE 'ME-%'"
    ).fetchone()[0]
    return n > 0


def main(force=False):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    conn = sqlite3.connect(DB)
    if not force and already_seeded(conn):
        print("  ME senate 2020: already loaded — nothing to do (pass force=True to reload)")
        conn.close()
        return
    ingest(conn, load())
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
