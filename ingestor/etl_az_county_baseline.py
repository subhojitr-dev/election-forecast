"""etl_az_county_baseline.py — Arizona baselines at COUNTY level.

WHY
  The live AZ feed (az_live_feed.py) reads results.arizona.vote at COUNTY
  granularity (county name is a clean, exact-match join to our 15 AZ counties
  — no name-matching). For the analytics to compare live-vs-baseline, the
  baseline must be at the SAME granularity. So we aggregate AZ's existing
  precinct-level baselines into county-pseudo-precincts ("AZ-{fips}-CTY") —
  the same pattern used for NC/GA/PA — and remove the now-superseded
  precinct-level rows for that race/year (county-level v1 decision, 2026-06-30).

  Converts BOTH President 2024 and Senate 2024 (the 2024 general, electionId
  47 on results.arizona.vote, is AZ's own archived live-test target — it
  carries both races).

  Idempotent per (race_type, year). baseline.db is gitignored (prod uses the
  released copy), so this is local-only until you re-publish the DB.
"""
import os
import sqlite3

DB = os.path.join("data", "db", "baseline.db")


def convert(c, race_type, year):
    state_full = c.execute("SELECT state FROM precincts WHERE state_abbr='AZ' LIMIT 1").fetchone()[0]
    fips = {r[0]: r[1] for r in c.execute(
        "SELECT DISTINCT county, county_fips FROM county_rollup WHERE state='AZ'")}

    rows = c.execute(
        """SELECT p.county, rh.candidate, rh.party, SUM(rh.votes) v
           FROM results_historical rh JOIN precincts p ON rh.precinct_id = p.id
           WHERE p.state_abbr='AZ' AND rh.race_type=? AND rh.election_year=?
             AND p.id NOT LIKE 'AZ-%-CTY'
           GROUP BY p.county, rh.candidate, rh.party""", (race_type, year)).fetchall()
    if not rows:
        n = c.execute("SELECT COUNT(*) FROM precincts WHERE id LIKE 'AZ-%-CTY'").fetchone()[0]
        print(f"  {race_type} {year}: no precinct-level rows found — already county-level "
              f"or not loaded ({n} AZ-CTY pseudo-precincts total). Nothing to do.")
        return

    ctot = {}
    for county, _, _, v in rows:
        ctot[county] = ctot.get(county, 0) + v

    c.execute("DELETE FROM results_historical WHERE race_type=? AND election_year=? "
              "AND precinct_id LIKE 'AZ-%-CTY'", (race_type, year))
    ins_prec = ins_rh = 0
    for county, candidate, party, v in rows:
        cf = fips.get(county)
        if not cf:
            continue
        pid = f"AZ-{cf}-CTY"
        if not c.execute("SELECT 1 FROM precincts WHERE id=?", (pid,)).fetchone():
            c.execute("""INSERT INTO precincts (id, state, state_abbr, county, county_fips, precinct_name)
                         VALUES (?,?,?,?,?,?)""",
                      (pid, state_full, "AZ", county, cf, "COUNTY TOTAL"))
            ins_prec += 1
        share = v / ctot[county] if ctot[county] else 0.0
        c.execute("""INSERT INTO results_historical
                     (precinct_id, election_year, race_type, candidate, party, votes, vote_share)
                     VALUES (?,?,?,?,?,?,?)""",
                  (pid, year, race_type, candidate, party, v, share))
        ins_rh += 1

    # remove the now-superseded precinct-level rows (no double-count)
    c.execute("""DELETE FROM results_historical WHERE race_type=? AND election_year=?
                 AND precinct_id IN (SELECT id FROM precincts
                     WHERE state_abbr='AZ' AND id NOT LIKE 'AZ-%-CTY')""", (race_type, year))

    d = c.execute("""SELECT SUM(rh.votes) FROM results_historical rh JOIN precincts p ON rh.precinct_id=p.id
                     WHERE p.state_abbr='AZ' AND rh.race_type=? AND rh.election_year=? AND rh.party='DEM'""",
                  (race_type, year)).fetchone()[0]
    rr = c.execute("""SELECT SUM(rh.votes) FROM results_historical rh JOIN precincts p ON rh.precinct_id=p.id
                      WHERE p.state_abbr='AZ' AND rh.race_type=? AND rh.election_year=? AND rh.party='REP'""",
                   (race_type, year)).fetchone()[0]
    nctot = c.execute("SELECT COUNT(*) FROM precincts WHERE id LIKE 'AZ-%-CTY'").fetchone()[0]
    print(f"  {race_type} {year}: converted -> county level: +{ins_prec} pseudo-precincts, "
          f"{ins_rh} rows ({nctot} AZ-CTY total)")
    print(f"  {race_type} {year} (county-level baseline): DEM {d:,} / REP {rr:,}  "
          f"-> winner {'D' if d > rr else 'R'}")


def main():
    c = sqlite3.connect(DB)
    convert(c, "president", 2024)
    convert(c, "senate", 2024)
    c.commit()
    c.close()


if __name__ == "__main__":
    main()
