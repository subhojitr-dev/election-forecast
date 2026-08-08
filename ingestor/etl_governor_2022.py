"""etl_governor_2022.py — GA/AZ/TX Governor baselines, at COUNTY level, for the
2026 general (Kemp/Hobbs/Abbott all term-limited or up for re-election in 2026;
2022 is each state's last Governor election, same logic used for Senate's
"last time this class was contested" baseline year in elections.py).

Source: MEDSL "Precinct-Level Returns 2022 by Individual State"
(doi:10.7910/DVN/UYQIEP) — per-state .tab files covering ALL state offices,
not just Governor; filtered down to office=='GOVERNOR' here.
    AZ-cleaned.tab   (file id 10855167)
    ga22_cleaned.tab (file id 10855164)
    TX-cleaned.tab   (file id 10855154)
Auto-downloaded into data/raw/gov2022/ on first run if not already present
(gitignored, same as every other raw election file — see DATA_SETUP.md; ~100MB
per state, ~340MB total, one-time). This mirrors download_db.py's pattern
specifically so production can self-seed: there's no way to pre-stage these
files on Render, and re-running the whole ETL pipeline there isn't an option
(etl_baseline.py wipes+rebuilds the DB — see the IMPORTANT note below), so the
poller task that calls ingest() (see production_poller.py) needs this to be
fully self-contained, not dependent on a manual local download step.

IMPORTANT: unlike etl_baseline.py, this does NOT wipe/rebuild baseline.db — it
opens the EXISTING db and additively inserts scoped to
(race_type='governor', election_year=2022), the same non-destructive pattern
etl_tx_county_baseline.py/etl_mi_county_baseline.py use. Re-running it is
idempotent (deletes only its own prior rows first).

Aggregated straight to county-pseudo-precincts ({ST}-{fips}-CTY) — no
precinct-level intermediate, matching the project's "county-level v1"
decision (2026-06-30) already used for every other race. The {ST}-{fips}-CTY
rows already exist in `precincts` (created by the Senate/President baselines)
for all of GA/AZ/TX's counties, confirmed by fips-code cross-check before
writing this script — no new precinct rows are needed.

Run:  python ingestor/etl_governor_2022.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data", "raw", "gov2022")
DB = os.path.join(ROOT, "data", "db", "baseline.db")
DATAVERSE_FILE_URL = "https://dataverse.harvard.edu/api/access/datafile/{id}"

# (local filename, Dataverse file id)
FILES = {
    "AZ": ("AZ-cleaned.tab", 10855167),
    "GA": ("ga22_cleaned.tab", 10855164),
    "TX": ("TX-cleaned.tab", 10855154),
}


def _ensure_downloaded(filename, file_id):
    path = os.path.join(RAW, filename)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(RAW, exist_ok=True)
    url = DATAVERSE_FILE_URL.format(id=file_id)
    print(f"  downloading {filename} from {url} ...")
    urllib.request.urlretrieve(url, path)
    print(f"  {filename} ready ({os.path.getsize(path):,} bytes)")
    return path

PARTY_MAP = {"DEMOCRAT": "DEM", "REPUBLICAN": "REP", "LIBERTARIAN": "LIB", "GREEN": "GRE"}
STAT_CANDIDATES = {
    "OVERVOTES", "UNDERVOTES", "OVER VOTES", "UNDER VOTES", "NOT QUALIFIED",
    "REGISTERED VOTERS", "BLANK", "BLANK VOTES", "TOTAL", "TOTAL VOTES",
    "BALLOTS CAST", "EXHAUSTED", "EXHAUSTED BALLOTS", "VOID", "VOID VOTES",
    "WRITE-IN", "NONE",
}


def map_party(ps):
    return PARTY_MAP.get(ps.strip().upper(), "OTH") if isinstance(ps, str) else "OTH"


def is_stat(candidate):
    return isinstance(candidate, str) and candidate.strip().upper() in STAT_CANDIDATES


def load_state(state, path):
    df = pd.read_csv(
        path, sep="\t", usecols=["office", "stage", "state_po", "county_fips",
                                  "county_name", "candidate", "party_simplified", "votes",
                                  "mode", "precinct"],
        dtype={"county_fips": str, "candidate": str, "county_name": str, "precinct": str},
        low_memory=False)
    df = df[(df["office"] == "GOVERNOR") & (df["stage"].astype(str).str.upper() == "GEN")]
    df = df[~df["candidate"].map(is_stat)]
    df["votes"] = pd.to_numeric(df["votes"], errors="coerce")
    df = df[df["votes"].notna() & (df["votes"] >= 0)]
    df["party"] = df["party_simplified"].map(map_party)

    # Some counties report a redundant mode='TOTAL' row IN ADDITION TO granular
    # per-mode rows (EARLY VOTING/ELECTION DAY/ABSENTEE/PROVISIONAL/...) for the
    # SAME precinct (confirmed: GA does this for essentially every precinct; AZ
    # for a small subset of counties; TX only ever reports TOTAL, no risk there).
    # Naively summing all rows double-counts wherever both exist. Fix: per
    # precinct, prefer TOTAL exclusively when present; only sum granular modes
    # for precincts that don't have a TOTAL row.
    df["pkey"] = df["county_fips"] + "|" + df["precinct"].fillna("")
    has_total = set(df.loc[df["mode"] == "TOTAL", "pkey"])
    df = df[(df["pkey"].isin(has_total) & (df["mode"] == "TOTAL")) | (~df["pkey"].isin(has_total))]

    # county totals: sum every precinct's votes for this candidate+party
    g = (df.groupby(["county_fips", "county_name", "candidate", "party"], as_index=False)["votes"]
         .sum())
    return g


def ingest(conn, state, df):
    race_type, year = "governor", 2022
    pid_prefix = f"{state}-"
    conn.execute("""DELETE FROM results_historical WHERE race_type=? AND election_year=?
                    AND precinct_id LIKE ? AND precinct_id LIKE '%-CTY'""",
                 (race_type, year, f"{pid_prefix}%"))
    known = {r[0] for r in conn.execute(
        "SELECT id FROM precincts WHERE id LIKE ?", (f"{pid_prefix}%-CTY",))}
    ctot = df.groupby("county_fips")["votes"].sum().to_dict()
    inserted = skipped = 0
    for _, row in df.iterrows():
        pid = f"{state}-{row['county_fips']}-CTY"
        if pid not in known:
            skipped += 1
            continue
        share = row["votes"] / ctot[row["county_fips"]] if ctot[row["county_fips"]] else 0.0
        conn.execute(
            """INSERT INTO results_historical
               (precinct_id, election_year, race_type, candidate, party, votes, vote_share)
               VALUES (?,?,?,?,?,?,?)""",
            (pid, year, race_type, row["candidate"], row["party"], int(row["votes"]), share))
        inserted += 1
    d = conn.execute("""SELECT SUM(rh.votes) FROM results_historical rh
                        WHERE rh.race_type=? AND rh.election_year=? AND rh.party='DEM'
                          AND rh.precinct_id LIKE ?""", (race_type, year, f"{pid_prefix}%")).fetchone()[0]
    r = conn.execute("""SELECT SUM(rh.votes) FROM results_historical rh
                        WHERE rh.race_type=? AND rh.election_year=? AND rh.party='REP'
                          AND rh.precinct_id LIKE ?""", (race_type, year, f"{pid_prefix}%")).fetchone()[0]
    print(f"  {state} governor 2022: {inserted} rows inserted, {skipped} skipped "
          f"(no matching {pid_prefix}*-CTY precinct) — DEM {d:,} / REP {r:,} "
          f"-> winner {'D' if d > r else 'R'}")


def already_seeded(conn) -> bool:
    n = conn.execute(
        "SELECT COUNT(*) FROM results_historical WHERE race_type='governor' AND election_year=2022"
    ).fetchone()[0]
    return n > 0


def main(force=False):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    conn = sqlite3.connect(DB)
    if not force and already_seeded(conn):
        print("  governor 2022: already loaded — nothing to do (pass force=True to reload)")
        conn.close()
        return
    for state, (filename, file_id) in FILES.items():
        path = _ensure_downloaded(filename, file_id)
        df = load_state(state, path)
        ingest(conn, state, df)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
