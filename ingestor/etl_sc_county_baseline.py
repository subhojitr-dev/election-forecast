"""etl_sc_county_baseline.py — South Carolina baseline at COUNTY level.

WHY
  The live SC feed (sc_live_feed.py) reads enr-scvotes.org (SC's Clarity ENR
  instance) at COUNTY granularity (county name is a clean, exact-match join to
  our 46 SC counties — no name-matching). For the analytics to compare
  live-vs-baseline, the baseline must be at the SAME granularity. So we
  aggregate SC's precinct-level Senate 2020 baseline (Graham vs Harrison — the
  Class-2 seat up again in 2026) into county-pseudo-precincts ("SC-{fips}-CTY")
  — the same pattern used for NC/GA/PA/AZ/MI/TX — and remove the precinct-level
  rows for that race/year (county-level v1 decision, 2026-06-30).

  Idempotent. baseline.db is gitignored (prod uses the released copy), so this
  is local-only until you re-publish the DB.
"""
import os
import sqlite3

DB = os.path.join("data", "db", "baseline.db")


def convert(c, race_type, year):
    state_full = c.execute("SELECT state FROM precincts WHERE state_abbr='SC' LIMIT 1").fetchone()[0]
    fips = {r[0]: r[1] for r in c.execute(
        "SELECT DISTINCT county, county_fips FROM county_rollup WHERE state='SC'")}

    rows = c.execute(
        """SELECT p.county, rh.candidate, rh.party, SUM(rh.votes) v
           FROM results_historical rh JOIN precincts p ON rh.precinct_id = p.id
           WHERE p.state_abbr='SC' AND rh.race_type=? AND rh.election_year=?
             AND p.id NOT LIKE 'SC-%-CTY'
           GROUP BY p.county, rh.candidate, rh.party""", (race_type, year)).fetchall()
    if not rows:
        n = c.execute("SELECT COUNT(*) FROM precincts WHERE id LIKE 'SC-%-CTY'").fetchone()[0]
        print(f"  {race_type} {year}: no precinct-level rows found — already county-level "
              f"or not loaded ({n} SC-CTY pseudo-precincts total). Nothing to do.")
        return

    ctot = {}
    for county, _, _, v in rows:
        ctot[county] = ctot.get(county, 0) + v

    c.execute("DELETE FROM results_historical WHERE race_type=? AND election_year=? "
              "AND precinct_id LIKE 'SC-%-CTY'", (race_type, year))
    ins_prec = ins_rh = 0
    for county, candidate, party, v in rows:
        cf = fips.get(county)
        if not cf:
            continue
        pid = f"SC-{cf}-CTY"
        if not c.execute("SELECT 1 FROM precincts WHERE id=?", (pid,)).fetchone():
            c.execute("""INSERT INTO precincts (id, state, state_abbr, county, county_fips, precinct_name)
                         VALUES (?,?,?,?,?,?)""",
                      (pid, state_full, "SC", county, cf, "COUNTY TOTAL"))
            ins_prec += 1
        share = v / ctot[county] if ctot[county] else 0.0
        c.execute("""INSERT INTO results_historical
                     (precinct_id, election_year, race_type, candidate, party, votes, vote_share)
                     VALUES (?,?,?,?,?,?,?)""",
                  (pid, year, race_type, candidate, party, v, share))
        ins_rh += 1

    c.execute("""DELETE FROM results_historical WHERE race_type=? AND election_year=?
                 AND precinct_id IN (SELECT id FROM precincts
                     WHERE state_abbr='SC' AND id NOT LIKE 'SC-%-CTY')""", (race_type, year))

    d = c.execute("""SELECT SUM(rh.votes) FROM results_historical rh JOIN precincts p ON rh.precinct_id=p.id
                     WHERE p.state_abbr='SC' AND rh.race_type=? AND rh.election_year=? AND rh.party='DEM'""",
                  (race_type, year)).fetchone()[0]
    rr = c.execute("""SELECT SUM(rh.votes) FROM results_historical rh JOIN precincts p ON rh.precinct_id=p.id
                      WHERE p.state_abbr='SC' AND rh.race_type=? AND rh.election_year=? AND rh.party='REP'""",
                   (race_type, year)).fetchone()[0]
    nctot = c.execute("SELECT COUNT(*) FROM precincts WHERE id LIKE 'SC-%-CTY'").fetchone()[0]
    print(f"  {race_type} {year}: converted -> county level: +{ins_prec} pseudo-precincts, "
          f"{ins_rh} rows ({nctot} SC-CTY total)")
    print(f"  {race_type} {year} (county-level baseline): DEM {d:,} / REP {rr:,}  "
          f"-> winner {'D' if d > rr else 'R'}")


def main():
    c = sqlite3.connect(DB)
    convert(c, "senate", 2020)
    c.commit()
    c.close()


if __name__ == "__main__":
    main()
