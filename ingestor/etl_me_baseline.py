"""etl_me_baseline.py — Maine as a new state: 2020 Senate baseline (Collins'
last election, Class 2 — same class as GA/MI/NC/TX/SC, all last contested
2020, all up again in 2026 — same logic already used for those). Real 2026
race: Susan Collins (R, incumbent) vs Troy Jackson (D nominee, replacing
Graham Platner after he withdrew) — see elections.py's general2026 entry.

Source: the SAME MEDSL 2020 Senate precinct file every other state's Senate
baseline already uses (doi:10.7910/DVN/ER9XTV, file id 6100391 — see
DATA_SETUP.md) — Maine was in it all along, just filtered out by
etl_baseline.py's TARGET_STATES restriction. Auto-downloaded if missing
locally (mirrors etl_governor_2022.py's self-seeding — production has no way
to pre-stage this file, and re-running the full etl_baseline.py pipeline
there isn't an option, see that script's IMPORTANT note above).

Maine uses ranked-choice voting for federal races, but this file only
reports FIRST-CHOICE totals per precinct (single mode='TOTAL' row per
candidate, no RCV elimination rounds) — confirmed by inspection, so no
special RCV handling is needed; treated exactly like every other state's
plurality data. Collins won outright in the first round in 2020 (>50%,
avoided an RCV runoff), so first-choice = final result for that year anyway.

One Maine-specific wrinkle: county_name includes a "STATEWIDE UOCAVA" row
(military/overseas absentee ballots, not tied to a real county) alongside
the 16 real counties — treated as its own county-pseudo-precinct
(ME-23000-CTY) like any other, same as everywhere else in this project;
no special-case handling needed since the analytics engine is generic over
precinct_id.

IMPORTANT: additive, like etl_governor_2022.py / etl_tx_county_baseline.py —
does NOT touch etl_baseline.py's destructive wipe-and-rebuild. Creates
ME-{fips}-CTY precinct rows (don't exist yet — confirmed via a DB check
before writing this) and inserts results_historical scoped to
(race_type='senate', election_year=2020, precinct_id LIKE 'ME-%'). Idempotent
(deletes only its own prior rows first).

Run:  python ingestor/etl_me_baseline.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CSV = os.path.join(ROOT, "data", "raw", "2020-SENATE-precinct-general.csv")
DB = os.path.join(ROOT, "data", "db", "baseline.db")
DATAVERSE_FILE_URL = "https://dataverse.harvard.edu/api/access/datafile/6100391"

PARTY_MAP = {"DEMOCRAT": "DEM", "REPUBLICAN": "REP", "LIBERTARIAN": "LIB", "GREEN": "GRE"}
STAT_CANDIDATES = {"UNDERVOTES", "OVERVOTES", "WRITEIN", "WRITE-IN", "BLANK", "TOTAL VOTES"}


def _ensure_downloaded():
    if os.path.exists(CSV) and os.path.getsize(CSV) > 0:
        return CSV
    os.makedirs(os.path.dirname(CSV), exist_ok=True)
    print(f"  downloading 2020-SENATE-precinct-general.csv from {DATAVERSE_FILE_URL} ...")
    urllib.request.urlretrieve(DATAVERSE_FILE_URL, CSV)
    print(f"  ready ({os.path.getsize(CSV):,} bytes)")
    return CSV


def map_party(ps):
    return PARTY_MAP.get(ps.strip().upper(), "OTH") if isinstance(ps, str) else "OTH"


def is_stat(candidate):
    return isinstance(candidate, str) and candidate.strip().upper() in STAT_CANDIDATES


CHUNKSIZE = 200_000  # bounds memory regardless of the source file's size — this is a
# 164MB NATIONAL file (34 states) and we only want Maine's slice of it. Read in
# chunks, filter each one down to ME rows only, and only ever hold that (tiny) result
# in memory. Same pattern etl_baseline.py / etl_governor_2022.py use.


def load():
    parts = []
    reader = pd.read_csv(
        CSV, dtype={"county_fips": str, "candidate": str, "county_name": str,
                     "state_po": str, "party_simplified": str},
        usecols=["state_po", "county_fips", "county_name", "candidate",
                 "party_simplified", "votes", "stage"],
        chunksize=CHUNKSIZE, low_memory=False)
    for chunk in reader:
        chunk = chunk[(chunk["state_po"] == "ME") & (chunk["stage"].astype(str).str.upper() == "GEN")]
        if len(chunk):
            parts.append(chunk)
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if df.empty:
        return df

    df = df[~df["candidate"].map(is_stat)]
    df["votes"] = pd.to_numeric(df["votes"], errors="coerce")
    df = df[df["votes"].notna() & (df["votes"] >= 0)]
    df["party"] = df["party_simplified"].map(map_party)
    g = (df.groupby(["county_fips", "county_name", "candidate", "party"], as_index=False)["votes"]
         .sum())
    return g


def ingest(conn, df, race_type="senate", year=2020):
    conn.execute("""DELETE FROM results_historical WHERE race_type=? AND election_year=?
                    AND precinct_id LIKE 'ME-%'""", (race_type, year))
    ctot = df.groupby("county_fips")["votes"].sum().to_dict()
    known = {r[0] for r in conn.execute("SELECT id FROM precincts WHERE id LIKE 'ME-%-CTY'")}
    new_precincts = inserted = 0
    for _, row in df.iterrows():
        pid = f"ME-{row['county_fips']}-CTY"
        if pid not in known:
            conn.execute("""INSERT INTO precincts
                            (id, state, state_abbr, county, county_fips, precinct_name)
                            VALUES (?,?,?,?,?,?)""",
                         (pid, "MAINE", "ME", row["county_name"], row["county_fips"], "COUNTY TOTAL"))
            known.add(pid)
            new_precincts += 1
        share = row["votes"] / ctot[row["county_fips"]] if ctot[row["county_fips"]] else 0.0
        conn.execute(
            """INSERT INTO results_historical
               (precinct_id, election_year, race_type, candidate, party, votes, vote_share)
               VALUES (?,?,?,?,?,?,?)""",
            (pid, year, race_type, row["candidate"], row["party"], int(row["votes"]), share))
        inserted += 1
    d = conn.execute("""SELECT SUM(votes) FROM results_historical
                        WHERE race_type=? AND election_year=? AND party='DEM'
                          AND precinct_id LIKE 'ME-%'""", (race_type, year)).fetchone()[0]
    r = conn.execute("""SELECT SUM(votes) FROM results_historical
                        WHERE race_type=? AND election_year=? AND party='REP'
                          AND precinct_id LIKE 'ME-%'""", (race_type, year)).fetchone()[0]
    print(f"  ME senate {year}: +{new_precincts} precincts, {inserted} rows — "
          f"DEM {d:,} / REP {r:,} -> winner {'D' if d > r else 'R'}")


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
    _ensure_downloaded()
    ingest(conn, load())
    conn.commit()
    conn.close()
    # NOT deleted after use (unlike etl_governor_2022.py's per-state files) —
    # this is the SAME shared file etl_baseline.py's SOURCES list expects for a
    # local full-rebuild dev workflow, not a file dedicated to this script alone.


if __name__ == "__main__":
    main()
