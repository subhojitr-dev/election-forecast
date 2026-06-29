"""
etl_baseline.py  —  Phase 1 ETL
Election Forecast Dashboard

Loads the MIT Election Data Science Lab 2020 precinct-level CSVs
(President + Senate) into the SQLite baseline database for our 8 target
swing states, then verifies the load against the certified Georgia QA totals.

Run:  python ingestor/etl_baseline.py

Findings baked into this script (see HANDOVER_BRIEF.md + codebook):
  * State filtering MUST use the exact `state_po` column. A naive substring
    match on a state name is wrong: Vermont has precincts literally named
    "GEORGIA_FRA-1" (town of Georgia, VT).
  * Votes are disaggregated by `mode` (ABSENTEE / ADVANCED VOTING /
    ELECTION DAY / PROVISIONAL ...). We SUM across modes per precinct+candidate.
  * FIPS codes are read as strings (codebook: leading zeros get dropped if int).
  * Statistical rows (OVERVOTES, UNDERVOTES, REGISTERED VOTERS, ...) are
    excluded from candidate totals.
  * Senate race selection: prefer the regular general (special=FALSE); fall
    back to the special election only if that's all a state has (AZ).
"""

import os
import sqlite3
import sys
import time

import pandas as pd

# Windows consoles default to cp1252; force UTF-8 so progress/emoji print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data", "raw")
DB_DIR = os.path.join(ROOT, "data", "db")
DB_PATH = os.path.join(DB_DIR, "baseline.db")

PRESIDENT_CSV = os.path.join(RAW, "PRESIDENT_precinct_general.csv")
SENATE_CSV = os.path.join(RAW, "2020-SENATE-precinct-general.csv")
PRES_2024_CSV = os.path.join(RAW, "2024-PRESIDENT-precinct-general.csv")
SEN_2024_CSV = os.path.join(RAW, "2024-SENATE-precinct-general.csv")
SEN_2018_CSV = os.path.join(RAW, "2018-SENATE-precinct-general.csv")

# (path, race_type, election_year, is_senate) — loaded additively into one DB.
# is_senate triggers single-contest selection (handles AZ special / GA two-races).
SOURCES = [
    (PRESIDENT_CSV, "president", 2020, False),
    (SENATE_CSV, "senate", 2020, True),
    (PRES_2024_CSV, "president", 2024, False),
    (SEN_2024_CSV, "senate", 2024, True),
    (SEN_2018_CSV, "senate", 2018, True),
]

TARGET_STATES = {"GA", "PA", "AZ", "NV", "WI", "MI", "NC", "TX"}
CHUNKSIZE = 200_000

# Columns we actually need (lean read for memory)
USECOLS = [
    "precinct", "votes", "county_name", "county_fips", "candidate",
    "party_simplified", "state_po", "special", "stage",
]
DTYPES = {
    "precinct": str, "county_name": str, "county_fips": str,
    "candidate": str, "party_simplified": str, "state_po": str,
    "special": str, "stage": str,
}

# Party mapping: party_simplified -> our scheme
PARTY_MAP = {
    "DEMOCRAT": "DEM", "REPUBLICAN": "REP",
    "LIBERTARIAN": "LIB", "GREEN": "GRE",
}

# Candidate labels that are statistics, not real votes -> excluded from totals
STAT_CANDIDATES = {
    "OVERVOTES", "UNDERVOTES", "OVER VOTES", "UNDER VOTES",
    "REGISTERED VOTERS", "BLANK", "BLANK VOTES", "TOTAL", "TOTAL VOTES",
    "BALLOTS CAST", "EXHAUSTED", "EXHAUSTED BALLOTS", "VOID", "VOID VOTES",
    "TIMES COUNTED", "TIMES BLANK VOTED", "TIMES OVER VOTED",
}

QA_TOLERANCE = 0.001  # 0.1% per candidate vs certified


def log(msg):
    print(msg, flush=True)


def map_party(ps):
    if not isinstance(ps, str):
        return "OTH"
    return PARTY_MAP.get(ps.strip().upper(), "OTH")


def is_stat(candidate):
    if not isinstance(candidate, str):
        return False
    return candidate.strip().upper() in STAT_CANDIDATES


# ----------------------------------------------------------------------------
# Load + filter a CSV down to target-state general-election candidate rows
# ----------------------------------------------------------------------------
def load_filtered(csv_path, label):
    log(f"\n[{label}] reading {os.path.basename(csv_path)} in chunks of {CHUNKSIZE:,} ...")
    parts = []
    rows_seen = 0
    rows_kept = 0
    t0 = time.time()
    reader = pd.read_csv(
        csv_path, usecols=USECOLS, dtype=DTYPES,
        chunksize=CHUNKSIZE, low_memory=False,
    )
    for i, chunk in enumerate(reader, 1):
        rows_seen += len(chunk)
        # exact state filter + general stage only
        chunk = chunk[chunk["state_po"].isin(TARGET_STATES)]
        chunk = chunk[chunk["stage"].astype(str).str.upper() == "GEN"]
        # numeric votes only (Texas turnout-pct hack lives in its own file;
        # not an issue here, but guard anyway)
        chunk["votes"] = pd.to_numeric(chunk["votes"], errors="coerce")
        chunk = chunk[chunk["votes"].notna()]
        # drop statistical rows
        chunk = chunk[~chunk["candidate"].map(is_stat)]
        if len(chunk):
            rows_kept += len(chunk)
            parts.append(chunk)
        if i % 10 == 0:
            log(f"    chunk {i:>4}: {rows_seen:>12,} rows scanned, "
                f"{rows_kept:>10,} kept ({time.time()-t0:5.1f}s)")
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=USECOLS)
    log(f"[{label}] done: {rows_seen:,} scanned -> {len(df):,} kept "
        f"in {time.time()-t0:.1f}s")
    log(f"[{label}] states present: {sorted(df['state_po'].unique())}")
    return df


# ----------------------------------------------------------------------------
# Senate race selection (handle AZ special + GA two-races)
# ----------------------------------------------------------------------------
def select_senate_contests(df):
    log("\n[SENATE] contest inventory (state | special | rows | votes | top D / top R):")
    keep_idx = []
    for state in sorted(df["state_po"].unique()):
        sdf = df[df["state_po"] == state]
        contests = {}
        for special_val, cdf in sdf.groupby(sdf["special"].astype(str).str.upper()):
            contests[special_val] = cdf
            party = cdf["candidate"].map(lambda c: None)  # placeholder
            mapped = cdf.assign(P=cdf["party_simplified"].map(map_party))
            top_d = (mapped[mapped["P"] == "DEM"].groupby("candidate")["votes"].sum()
                     .sort_values(ascending=False))
            top_r = (mapped[mapped["P"] == "REP"].groupby("candidate")["votes"].sum()
                     .sort_values(ascending=False))
            d_name = f"{top_d.index[0]} ({int(top_d.iloc[0]):,})" if len(top_d) else "-"
            r_name = f"{top_r.index[0]} ({int(top_r.iloc[0]):,})" if len(top_r) else "-"
            log(f"    {state} | special={special_val:<5} | {len(cdf):>7,} rows | "
                f"{int(cdf['votes'].sum()):>10,} votes | D: {d_name} | R: {r_name}")
        # prefer regular general (special=FALSE); else special=TRUE
        chosen = "FALSE" if "FALSE" in contests else next(iter(contests))
        log(f"    -> {state}: using special={chosen}")
        keep_idx.append(contests[chosen].index)
    result = df.loc[pd.Index([i for idx in keep_idx for i in idx])]
    return result


# ----------------------------------------------------------------------------
# Build the normalized tables
# ----------------------------------------------------------------------------
def build_tables(df, race_type, election_year):
    df = df.copy()
    df["party"] = df["party_simplified"].map(map_party)
    df["precinct_id"] = (
        df["state_po"] + "-" + df["county_fips"].fillna("") + "-" + df["precinct"].fillna("")
    )

    # precincts (unique)
    precincts = (
        df[["precinct_id", "state_po", "county_name", "county_fips", "precinct"]]
        .drop_duplicates("precinct_id")
        .rename(columns={
            "precinct_id": "id", "state_po": "state_abbr",
            "county_name": "county", "precinct": "precinct_name",
        })
    )
    precincts["state"] = precincts["state_abbr"]

    # results_historical: sum across modes per precinct+candidate
    rh = (
        df.groupby(["precinct_id", "candidate", "party"], as_index=False)["votes"]
        .sum()
    )
    # precinct total valid votes (for vote_share)
    ptot = rh.groupby("precinct_id")["votes"].sum().rename("ptot")
    rh = rh.join(ptot, on="precinct_id")
    rh["vote_share"] = (rh["votes"] / rh["ptot"]).where(rh["ptot"] > 0, 0.0)
    rh["election_year"] = election_year
    rh["race_type"] = race_type

    # county_rollup
    g = df.groupby(["state_po", "county_name", "county_fips"])
    rollup = pd.DataFrame({
        "dem_votes": g.apply(lambda x: x.loc[x["party"] == "DEM", "votes"].sum(), include_groups=False),
        "rep_votes": g.apply(lambda x: x.loc[x["party"] == "REP", "votes"].sum(), include_groups=False),
        "total_votes": g["votes"].sum(),
    }).reset_index().rename(columns={"state_po": "state", "county_name": "county"})
    rollup["dem_share"] = (rollup["dem_votes"] / rollup["total_votes"]).where(rollup["total_votes"] > 0, 0.0)
    rollup["rep_share"] = (rollup["rep_votes"] / rollup["total_votes"]).where(rollup["total_votes"] > 0, 0.0)
    rollup["election_year"] = election_year
    rollup["race_type"] = race_type

    return precincts, rh, rollup


# ----------------------------------------------------------------------------
# Schema
# ----------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS precincts (
  id TEXT PRIMARY KEY, state TEXT, state_abbr TEXT,
  county TEXT, county_fips TEXT, precinct_name TEXT
);
CREATE TABLE IF NOT EXISTS results_historical (
  id INTEGER PRIMARY KEY AUTOINCREMENT, precinct_id TEXT,
  election_year INTEGER, race_type TEXT, candidate TEXT, party TEXT,
  votes INTEGER, vote_share REAL,
  FOREIGN KEY (precinct_id) REFERENCES precincts(id)
);
CREATE TABLE IF NOT EXISTS results_live (
  id INTEGER PRIMARY KEY AUTOINCREMENT, precinct_id TEXT, race_type TEXT,
  candidate TEXT, party TEXT, votes INTEGER, vote_share REAL,
  precincts_reporting INTEGER, total_precincts INTEGER,
  last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS county_rollup (
  id INTEGER PRIMARY KEY AUTOINCREMENT, state TEXT, county TEXT,
  county_fips TEXT, election_year INTEGER, race_type TEXT,
  dem_votes INTEGER, rep_votes INTEGER, total_votes INTEGER,
  dem_share REAL, rep_share REAL
);
CREATE INDEX IF NOT EXISTS idx_rh_precinct ON results_historical(precinct_id);
CREATE INDEX IF NOT EXISTS idx_rh_race ON results_historical(race_type, election_year);
CREATE INDEX IF NOT EXISTS idx_rollup_state ON county_rollup(state, race_type, election_year);
"""


def write_db(datasets):
    os.makedirs(DB_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        log(f"\n[DB] removed existing {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    log(f"[DB] schema created at {DB_PATH}")

    # union precincts across every dataset
    all_precincts = pd.concat([d["precincts"] for d in datasets], ignore_index=True) \
        .drop_duplicates("id")
    all_precincts[["id", "state", "state_abbr", "county", "county_fips", "precinct_name"]] \
        .to_sql("precincts", conn, if_exists="append", index=False)
    log(f"[DB] precincts (union of all datasets): {len(all_precincts):,}")

    for d in datasets:
        d["rh"][["precinct_id", "election_year", "race_type", "candidate", "party",
                 "votes", "vote_share"]].to_sql("results_historical", conn,
                                                if_exists="append", index=False)
        d["rollup"][["state", "county", "county_fips", "election_year", "race_type",
                     "dem_votes", "rep_votes", "total_votes", "dem_share", "rep_share"]] \
            .to_sql("county_rollup", conn, if_exists="append", index=False)
        log(f"[DB] {d['year']} {d['race_type']:9}: "
            f"{len(d['rh']):>8,} historical rows, {len(d['rollup']):>4} county rollups")

    conn.commit()
    conn.close()


# ----------------------------------------------------------------------------
# QA verification
# ----------------------------------------------------------------------------
def verify(datasets):
    log("\n" + "=" * 64)
    log("QA ANCHOR  (Georgia 2020 President — certified)")
    log("=" * 64)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT rh.candidate, SUM(rh.votes)
        FROM results_historical rh JOIN precincts p ON rh.precinct_id = p.id
        WHERE p.state_abbr='GA' AND rh.race_type='president' AND rh.election_year=2020
          AND rh.candidate IN ('JOSEPH R BIDEN','DONALD J TRUMP')
        GROUP BY rh.candidate
    """)
    tallies = dict(cur.fetchall())
    biden = tallies.get("JOSEPH R BIDEN", 0)
    trump = tallies.get("DONALD J TRUMP", 0)

    cur.execute("SELECT COUNT(*) FROM county_rollup WHERE state='GA' AND race_type='president' AND election_year=2020")
    counties = cur.fetchone()[0]
    cur.execute("""SELECT COUNT(DISTINCT p.id) FROM precincts p
                   JOIN results_historical rh ON rh.precinct_id=p.id
                   WHERE p.state_abbr='GA' AND rh.race_type='president'
                     AND rh.election_year=2020""")
    precincts = cur.fetchone()[0]
    conn.close()

    certified = {"Biden": 2_473_633, "Trump": 2_461_854}
    got = {"Biden": biden, "Trump": trump}
    ok = True
    for name in ("Biden", "Trump"):
        delta = got[name] - certified[name]
        pct = delta / certified[name]
        status = "PASS" if abs(pct) <= QA_TOLERANCE else "FAIL"
        if status == "FAIL":
            ok = False
        log(f"  {name:6} {got[name]:>10,}  certified {certified[name]:>10,}  "
            f"delta {delta:+6,} ({pct:+.3%})  [{status}]")
    log(f"  Margin {biden-trump:+,} (certified +11,779)")
    log(f"  Counties {counties} (certified 159)  "
        f"[{'PASS' if counties == 159 else 'FAIL'}]")
    log(f"  Precincts {precincts:,} (certified ~2,659)")
    if counties != 159:
        ok = False
    log("=" * 64)
    log(f"QA ANCHOR: {'PASS ✅' if ok else 'FAIL ❌'} "
        f"(tolerance ±{QA_TOLERANCE:.1%} per candidate, exact county count)")

    # ---- eyeball summary of every loaded baseline ----
    log("\n" + "=" * 64)
    log("LOADED BASELINES  (per state — sanity check winners + coverage)")
    log("=" * 64)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT election_year, race_type, state,
               SUM(dem_votes), SUM(rep_votes), SUM(total_votes), COUNT(*)
        FROM county_rollup
        GROUP BY election_year, race_type, state
        ORDER BY race_type, election_year, state
    """).fetchall()
    conn.close()
    log(f"  {'year':<5}{'race':<10}{'st':<4}{'DEM':>11}{'REP':>11}  win  {'cnty':>4}")
    for y, r, st, dv, rv, tv, cnt in rows:
        win = "D" if dv > rv else "R"
        log(f"  {y:<5}{r:<10}{st:<4}{dv:>11,}{rv:>11,}   {win}   {cnt:>4}")
    log("=" * 64)
    return ok


# ----------------------------------------------------------------------------
def main():
    log("Phase 1 ETL — building baseline.db (multi-year, additive)")
    log(f"Target states: {sorted(TARGET_STATES)}")

    datasets = []
    for path, race_type, year, is_senate in SOURCES:
        if not os.path.exists(path):
            log(f"\n[SKIP] missing file (not loaded): {path}")
            continue
        df = load_filtered(path, f"{year} {race_type.upper()}")
        if df.empty:
            log(f"[SKIP] no target-state rows in {os.path.basename(path)}")
            continue
        if is_senate:
            df = select_senate_contests(df)
        precincts, rh, rollup = build_tables(df, race_type, year)
        datasets.append({"race_type": race_type, "year": year,
                         "precincts": precincts, "rh": rh, "rollup": rollup})

    if not datasets:
        log("\n[FATAL] no source files found — nothing loaded.")
        sys.exit(1)

    write_db(datasets)
    ok = verify(datasets)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
