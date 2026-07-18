"""etl_sc_baseline.py — Phase 1 ETL, SC add-on (2026-07-17)

SC was NOT one of the original 8 target states, so baseline.db has ZERO SC
data (no precincts, no results_historical). This script loads it, ADDITIVELY,
from the SAME Harvard Dataverse CSVs already on disk (data/raw/) — those files
are nationwide, SC rows were just filtered out by etl_baseline.py's
TARGET_STATES set. Confirmed present: President 2020, President 2024, Senate
2020 (Graham vs Harrison — SC's Class-2 seat, the one up again in 2026).

⚠️ Deliberately NOT reusing etl_baseline.py directly: that script's write_db()
DROPS AND REBUILDS THE ENTIRE baseline.db from just its 5 hardcoded sources —
running it now would destroy every live-feed result (results_live, the
county-pseudo baselines for NC/GA/PA/AZ/MI/TX) built up since. This script
only ever INSERTs into the existing DB, never drops anything.

Run:  python ingestor/etl_sc_baseline.py
"""
import os
import sqlite3
import sys
import time

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data", "raw")
DB_PATH = os.path.join(ROOT, "data", "db", "baseline.db")

SOURCES = [
    (os.path.join(RAW, "PRESIDENT_precinct_general.csv"), "president", 2020, False),
    (os.path.join(RAW, "2024-PRESIDENT-precinct-general.csv"), "president", 2024, False),
    (os.path.join(RAW, "2020-SENATE-precinct-general.csv"), "senate", 2020, True),
]
CHUNKSIZE = 200_000
USECOLS = ["precinct", "votes", "county_name", "county_fips", "candidate",
           "party_simplified", "state_po", "special", "stage"]
DTYPES = {"precinct": str, "county_name": str, "county_fips": str,
          "candidate": str, "party_simplified": str, "state_po": str,
          "special": str, "stage": str}
PARTY_MAP = {"DEMOCRAT": "DEM", "REPUBLICAN": "REP", "LIBERTARIAN": "LIB", "GREEN": "GRE"}
STAT_CANDIDATES = {
    "OVERVOTES", "UNDERVOTES", "OVER VOTES", "UNDER VOTES",
    "REGISTERED VOTERS", "BLANK", "BLANK VOTES", "TOTAL", "TOTAL VOTES",
    "BALLOTS CAST", "EXHAUSTED", "EXHAUSTED BALLOTS", "VOID", "VOID VOTES",
    "TIMES COUNTED", "TIMES BLANK VOTED", "TIMES OVER VOTED",
}


def log(msg):
    print(msg, flush=True)


def map_party(ps):
    if not isinstance(ps, str):
        return "OTH"
    return PARTY_MAP.get(ps.strip().upper(), "OTH")


def is_stat(candidate):
    return isinstance(candidate, str) and candidate.strip().upper() in STAT_CANDIDATES


def load_filtered(csv_path, label):
    log(f"[{label}] reading {os.path.basename(csv_path)} for SC only ...")
    parts = []
    t0 = time.time()
    for chunk in pd.read_csv(csv_path, usecols=USECOLS, dtype=DTYPES,
                              chunksize=CHUNKSIZE, low_memory=False):
        chunk = chunk[chunk["state_po"] == "SC"]
        chunk = chunk[chunk["stage"].astype(str).str.upper() == "GEN"]
        chunk["votes"] = pd.to_numeric(chunk["votes"], errors="coerce")
        chunk = chunk[chunk["votes"].notna()]
        chunk = chunk[~chunk["candidate"].map(is_stat)]
        if len(chunk):
            parts.append(chunk)
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=USECOLS)
    log(f"[{label}] {len(df):,} SC rows ({time.time()-t0:.1f}s)")
    return df


def select_senate_contest(df):
    """Prefer the regular general (special=FALSE); else whatever's there."""
    contests = {k.upper(): v for k, v in df.groupby(df["special"].astype(str).str.upper())}
    chosen = "FALSE" if "FALSE" in contests else next(iter(contests))
    log(f"[SENATE] SC contest special={chosen} chosen "
        f"({len(contests[chosen]):,} rows)")
    return contests[chosen]


def build_tables(df, race_type, year):
    df = df.copy()
    df["party"] = df["party_simplified"].map(map_party)
    df["precinct_id"] = ("SC-" + df["county_fips"].fillna("") + "-" + df["precinct"].fillna(""))

    precincts = (df[["precinct_id", "county_name", "county_fips", "precinct"]]
                 .drop_duplicates("precinct_id")
                 .rename(columns={"precinct_id": "id", "county_name": "county",
                                   "precinct": "precinct_name"}))
    precincts["state"] = "South Carolina"
    precincts["state_abbr"] = "SC"

    rh = df.groupby(["precinct_id", "candidate", "party"], as_index=False)["votes"].sum()
    ptot = rh.groupby("precinct_id")["votes"].sum().rename("ptot")
    rh = rh.join(ptot, on="precinct_id")
    rh["vote_share"] = (rh["votes"] / rh["ptot"]).where(rh["ptot"] > 0, 0.0)
    rh["election_year"] = year
    rh["race_type"] = race_type

    g = df.groupby(["county_name", "county_fips"])
    rollup = pd.DataFrame({
        "dem_votes": g.apply(lambda x: x.loc[x["party"] == "DEM", "votes"].sum(), include_groups=False),
        "rep_votes": g.apply(lambda x: x.loc[x["party"] == "REP", "votes"].sum(), include_groups=False),
        "total_votes": g["votes"].sum(),
    }).reset_index().rename(columns={"county_name": "county"})
    rollup["state"] = "SC"
    rollup["dem_share"] = (rollup["dem_votes"] / rollup["total_votes"]).where(rollup["total_votes"] > 0, 0.0)
    rollup["rep_share"] = (rollup["rep_votes"] / rollup["total_votes"]).where(rollup["total_votes"] > 0, 0.0)
    rollup["election_year"] = year
    rollup["race_type"] = race_type
    return precincts, rh, rollup


def main():
    conn = sqlite3.connect(DB_PATH)
    already = conn.execute("SELECT COUNT(*) FROM precincts WHERE state_abbr='SC'").fetchone()[0]
    if already:
        log(f"SC already has {already:,} precincts loaded — nothing to do (idempotent guard).")
        conn.close()
        return

    datasets = []
    for path, race_type, year, is_senate in SOURCES:
        if not os.path.exists(path):
            log(f"[SKIP] missing file: {path}")
            continue
        df = load_filtered(path, f"{year} {race_type.upper()}")
        if df.empty:
            log(f"[SKIP] no SC rows in {os.path.basename(path)}")
            continue
        if is_senate:
            df = select_senate_contest(df)
        precincts, rh, rollup = build_tables(df, race_type, year)
        datasets.append({"race_type": race_type, "year": year,
                         "precincts": precincts, "rh": rh, "rollup": rollup})

    # union + dedupe precincts across ALL datasets before inserting (a precinct_id
    # like "SC-45001-..." repeats across 2020 president / 2024 president / senate —
    # inserting per-dataset would violate the precincts.id PRIMARY KEY)
    all_precincts = pd.concat([d["precincts"] for d in datasets], ignore_index=True) \
        .drop_duplicates("id")
    all_precincts[["id", "state", "state_abbr", "county", "county_fips", "precinct_name"]] \
        .to_sql("precincts", conn, if_exists="append", index=False)
    log(f"[DB] precincts (union of all SC datasets): {len(all_precincts):,}")

    for d in datasets:
        d["rh"][["precinct_id", "election_year", "race_type", "candidate", "party",
                 "votes", "vote_share"]].to_sql("results_historical", conn,
                                                if_exists="append", index=False)
        d["rollup"][["state", "county", "county_fips", "election_year", "race_type",
                     "dem_votes", "rep_votes", "total_votes", "dem_share", "rep_share"]] \
            .to_sql("county_rollup", conn, if_exists="append", index=False)
        log(f"[DB] {d['year']} {d['race_type']:9}: {len(d['rh']):>7,} historical rows, "
            f"{len(d['rollup']):>3} county rollups")
    conn.commit()

    # sanity check: SC 2020 Senate should show Graham > Harrison
    d = conn.execute("""SELECT SUM(rh.votes) FROM results_historical rh
                        JOIN precincts p ON rh.precinct_id=p.id
                        WHERE p.state_abbr='SC' AND rh.race_type='senate'
                          AND rh.election_year=2020 AND rh.party='DEM'""").fetchone()[0]
    r = conn.execute("""SELECT SUM(rh.votes) FROM results_historical rh
                        JOIN precincts p ON rh.precinct_id=p.id
                        WHERE p.state_abbr='SC' AND rh.race_type='senate'
                          AND rh.election_year=2020 AND rh.party='REP'""").fetchone()[0]
    n_counties = conn.execute("SELECT COUNT(*) FROM county_rollup WHERE state='SC' AND race_type='senate' AND election_year=2020").fetchone()[0]
    conn.close()
    log(f"\nSC 2020 Senate (Graham vs Harrison): DEM {d:,} / REP {r:,} "
        f"-> winner {'D' if d > r else 'R'}  ({n_counties} counties)")


if __name__ == "__main__":
    main()
