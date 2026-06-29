"""ETL — Georgia Jan 5, 2021 U.S. Senate RUNOFF baseline (both seats, COUNTY level).

WHY THIS EXISTS
  Georgia requires a majority to win. In the Nov 2020 general, Perdue (R) LED
  Ossoff (D) but finished under 50%, so the seat was decided by the Jan 5, 2021
  RUNOFF — which Ossoff WON (and Warnock won the concurrent special runoff).
  Ossoff's seat (Class II) is up again in 2026, so the runoff — not the Nov
  general — is the correct baseline for the dashboard's GA Senate race.

WHAT IT DOES
  Loads the runoff results ADDITIVELY as election_year=2021, aggregated to COUNTY
  level (decision 2026-06-28): each GA county becomes ONE pseudo-precinct
  ("GA-{fips}-CTY") so the precinct-keyed analytics/replay work unchanged at
  county granularity.
    - regular seat (Ossoff vs Perdue)   -> race_type 'senate'
    - special seat (Warnock vs Loeffler) -> race_type 'senate_special'
  The 2020 Nov-general GA rows are left intact (just unused once the API repoints
  SENATE_BASELINE["GA"] = 2021). Idempotent: clears GA 2021 rows before inserting.

SOURCE
  OpenElections precinct file (aggregated here to county):
  data/raw/ga_runoff_2021/20210105__ga__runoff.csv
"""
import csv
import os
import sqlite3

DB_PATH = os.path.join("data", "db", "baseline.db")
CSV_PATH = os.path.join("data", "raw", "ga_runoff_2021", "20210105__ga__runoff.csv")

# office label in the CSV -> (race_type we store it under)
OFFICE_RACE = {
    "U.S. Senate": "senate",
    "U.S. Senate (Special)": "senate_special",
}
PARTY_MAP = {"Democrat": "DEM", "Republican": "REP"}
MODE_COLS = ("election_day_votes", "advanced_votes",
             "absentee_by_mail_votes", "provisional_votes")


def norm_county(name):
    return " ".join(name.strip().upper().split())


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # GA full state name + canonical county -> fips map, taken from existing rows
    state_full = conn.execute(
        "SELECT state FROM precincts WHERE state_abbr='GA' LIMIT 1").fetchone()[0]
    fips = {norm_county(r["county"]): r["county_fips"] for r in conn.execute(
        "SELECT DISTINCT county, county_fips FROM county_rollup WHERE state='GA'")}
    print(f"State: {state_full} | known GA counties: {len(fips)}")

    # --- aggregate the CSV to county level ---
    # agg[(race_type, county)] = {(party, candidate): votes}
    agg = {}
    unmatched = set()
    with open(CSV_PATH, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            race = OFFICE_RACE.get(row["office"])
            party = PARTY_MAP.get(row["party"])
            if race is None or party is None:
                continue                      # skip PSC + any non D/R
            county = norm_county(row["county"])
            if county not in fips:
                unmatched.add(county)
                continue
            v = sum(int(row[c] or 0) for c in MODE_COLS)
            agg.setdefault((race, county), {}).setdefault((party, row["candidate"]), 0)
            agg[(race, county)][(party, row["candidate"])] += v

    if unmatched:
        raise SystemExit(f"ABORT — county names not in baseline: {sorted(unmatched)}")

    # --- write pseudo-precincts + results_historical (idempotent) ---
    inserted_prec = 0
    counties_seen = set()
    rh_rows = 0
    # clear any prior 2021 GA load for these races
    conn.execute(
        """DELETE FROM results_historical WHERE election_year=2021
           AND race_type IN ('senate','senate_special')
           AND precinct_id IN (SELECT id FROM precincts WHERE state_abbr='GA')""")

    for (race, county), cands in sorted(agg.items()):
        cf = fips[county]
        pid = f"GA-{cf}-CTY"
        if county not in counties_seen:
            counties_seen.add(county)
        # ensure the county pseudo-precinct exists
        exists = conn.execute("SELECT 1 FROM precincts WHERE id=?", (pid,)).fetchone()
        if not exists:
            conn.execute(
                """INSERT INTO precincts (id, state, state_abbr, county, county_fips, precinct_name)
                   VALUES (?,?,?,?,?,?)""",
                (pid, state_full, "GA", county, cf, "COUNTY TOTAL (runoff)"))
            inserted_prec += 1
        total2 = sum(cands.values())   # both candidates (2-way runoff)
        for (party, cand), votes in cands.items():
            share = (votes / total2) if total2 else 0.0
            conn.execute(
                """INSERT INTO results_historical
                   (precinct_id, election_year, race_type, candidate, party, votes, vote_share)
                   VALUES (?,?,?,?,?,?,?)""",
                (pid, 2021, race, cand.upper(), party, votes, share))
            rh_rows += 1

    conn.commit()
    print(f"Inserted pseudo-precincts: {inserted_prec} | results_historical rows: {rh_rows}")

    # --- verification ---
    for race in ("senate", "senate_special"):
        print(f"\n=== GA {race} 2021 statewide ===")
        rows = conn.execute(
            """SELECT rh.party, rh.candidate, SUM(rh.votes) v
               FROM results_historical rh JOIN precincts p ON rh.precinct_id=p.id
               WHERE p.state_abbr='GA' AND rh.race_type=? AND rh.election_year=2021
               GROUP BY rh.party, rh.candidate ORDER BY v DESC""", (race,)).fetchall()
        d = sum(r["v"] for r in rows if r["party"] == "DEM")
        r_ = sum(r["v"] for r in rows if r["party"] == "REP")
        for row in rows:
            print(f"  {row['party']:<4} {row['candidate']:<22} {row['v']:>12,}")
        share = 100 * d / (d + r_) if (d + r_) else 0
        winner = "DEM" if d > r_ else "REP"
        n_cty = conn.execute(
            """SELECT COUNT(DISTINCT p.county_fips)
               FROM results_historical rh JOIN precincts p ON rh.precinct_id=p.id
               WHERE p.state_abbr='GA' AND rh.race_type=? AND rh.election_year=2021""",
            (race,)).fetchone()[0]
        print(f"  -> winner {winner}, Dem two-party {share:.2f}%, counties {n_cty}")

    conn.close()


if __name__ == "__main__":
    main()
