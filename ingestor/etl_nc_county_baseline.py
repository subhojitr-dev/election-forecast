"""etl_nc_county_baseline.py — NC U.S. Senate 2020 baseline at COUNTY level.

WHY
  The live NC feed (nc_live_feed.py) reads NCSBE at COUNTY granularity (county
  FIPS = a clean join, no precinct name-matching). For the analytics to compare
  live-vs-baseline, the baseline must be at the SAME granularity. So we aggregate
  NC's existing precinct-level 2020 Senate baseline into county-pseudo-precincts
  ("NC-{fips}-CTY") — exactly the pattern GA's 2021 runoff uses — and remove the
  precinct-level 2020 Senate rows (county-level v1 decision, 2026-06-30).

  Needs NO change to the analytics: live + baseline are both keyed NC-{fips}-CTY,
  so the existing per-precinct(=per-county) shift/rollup work unchanged.

  Idempotent. baseline.db is gitignored (prod uses the released copy), so this is
  local-only until you re-publish the DB.
"""
import os
import sqlite3

DB = os.path.join("data", "db", "baseline.db")


def main():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    state_full = c.execute("SELECT state FROM precincts WHERE state_abbr='NC' LIMIT 1").fetchone()[0]
    fips = {r["county"]: r["county_fips"] for r in c.execute(
        "SELECT DISTINCT county, county_fips FROM county_rollup WHERE state='NC'")}

    rows = c.execute(
        """SELECT p.county, rh.candidate, rh.party, SUM(rh.votes) v
           FROM results_historical rh JOIN precincts p ON rh.precinct_id = p.id
           WHERE p.state_abbr='NC' AND rh.race_type='senate' AND rh.election_year=2020
             AND p.id NOT LIKE 'NC-%-CTY'
           GROUP BY p.county, rh.candidate, rh.party""").fetchall()
    if not rows:
        # already converted (idempotent re-run) — report + exit cleanly
        n = c.execute("SELECT COUNT(*) FROM precincts WHERE id LIKE 'NC-%-CTY'").fetchone()[0]
        print(f"No precinct-level NC 2020 Senate rows found — already county-level "
              f"({n} NC-CTY pseudo-precincts). Nothing to do.")
        return

    ctot = {}
    for r in rows:
        ctot[r["county"]] = ctot.get(r["county"], 0) + r["v"]

    c.execute("DELETE FROM results_historical WHERE race_type='senate' "
              "AND election_year=2020 AND precinct_id LIKE 'NC-%-CTY'")
    ins_prec = ins_rh = 0
    for r in rows:
        county, cf = r["county"], fips.get(r["county"])
        if not cf:
            continue
        pid = f"NC-{cf}-CTY"
        if not c.execute("SELECT 1 FROM precincts WHERE id=?", (pid,)).fetchone():
            c.execute("""INSERT INTO precincts (id, state, state_abbr, county, county_fips, precinct_name)
                         VALUES (?,?,?,?,?,?)""",
                      (pid, state_full, "NC", county, cf, "COUNTY TOTAL"))
            ins_prec += 1
        share = r["v"] / ctot[county] if ctot[county] else 0.0
        c.execute("""INSERT INTO results_historical
                     (precinct_id, election_year, race_type, candidate, party, votes, vote_share)
                     VALUES (?,?,?,?,?,?,?)""",
                  (pid, 2020, "senate", r["candidate"], r["party"], r["v"], share))
        ins_rh += 1

    # remove the now-superseded precinct-level NC 2020 Senate rows (no double-count)
    c.execute("""DELETE FROM results_historical WHERE race_type='senate' AND election_year=2020
                 AND precinct_id IN (SELECT id FROM precincts
                     WHERE state_abbr='NC' AND id NOT LIKE 'NC-%-CTY')""")
    c.commit()

    d = c.execute("""SELECT SUM(rh.votes) FROM results_historical rh JOIN precincts p ON rh.precinct_id=p.id
                     WHERE p.state_abbr='NC' AND rh.race_type='senate' AND rh.election_year=2020 AND rh.party='DEM'""").fetchone()[0]
    rr = c.execute("""SELECT SUM(rh.votes) FROM results_historical rh JOIN precincts p ON rh.precinct_id=p.id
                      WHERE p.state_abbr='NC' AND rh.race_type='senate' AND rh.election_year=2020 AND rh.party='REP'""").fetchone()[0]
    nctot = c.execute("SELECT COUNT(*) FROM precincts WHERE id LIKE 'NC-%-CTY'").fetchone()[0]
    print(f"Converted NC 2020 Senate -> county level: +{ins_prec} pseudo-precincts, {ins_rh} rows "
          f"({nctot} NC-CTY total)")
    print(f"NC 2020 Senate (county-level baseline): DEM {d:,} / REP {rr:,}  "
          f"-> winner {'D' if d > rr else 'R'}  (real: Tillis R beat Cunningham D)")
    c.close()


if __name__ == "__main__":
    main()
