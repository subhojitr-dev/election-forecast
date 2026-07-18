"""sc_live_feed.py — South Carolina live ingestion into results_live (county level).

SC runs a Clarity/SOE Software ENR instance at enr-scvotes.org — and unlike
every other state we checked, its OLD Clarity mechanism is still ALIVE and
fully OPEN (plain httpx, no Cloudflare, no WAF, no Playwright needed at all —
the simplest state wired so far):
  discovery:  /SC/{electionId}/current_ver.txt  -> plain-text version number
              (the exact classic Clarity mechanism described in Issues.md —
              it's just decommissioned for GA/others, not for SC)
  candidates: /SC/{electionId}/{version}/json/en/summary.json
              -> [{"C": "U.S.  Senate  - REP", "K": "26001",
                   "CH": [candidate names...], "P": [party per candidate]}, ...]
              (note the literal DOUBLE SPACES in contest names — a Clarity
              quirk; do substring matches, not exact string equality)
  county data: /SC/{electionId}/{version}/json/ALL.json
              -> {"Contests": [{"A": "Abbeville", "C": [contest codes...],
                                "V": [[votes per candidate]...]}, ...]}
              ONE call = every county x every contest. The array at index i of
              "V" lines up positionally with contest code at index i of "C"
              (NOT with the "K" ordering in summary.json — join by code, then
              use summary.json's CH/P for that same code to label the votes).
              ⚠️ ONE county entry has A == "-1" — a statewide/pseudo-county
              rollup row, NOT one of SC's 46 real counties. MUST be excluded
              or every county gets double-counted (confirmed: including it
              exactly doubles every statewide total).

electionId is NOT listed anywhere public between elections (SC's
/SC/elections.json returns `[]` right now) — unlike AZ's stable pre-published
ids. Must be (re)discovered via browser network inspection close to the
night, the same as MI. Once you have an electionId, current_ver.txt handles
the rest with zero browser dependency.

CLI (test against the 2026 June primary — the only SC election currently
reachable on their live system; used here as a MECHANICS validation, since
SC's actual baseline race, the 2020 Senate general, isn't archived on their
live ENR anymore):
  python ingestor/sc_live_feed.py 126294 26001 sc_primary_test_rep
  python ingestor/sc_live_feed.py 126294 26000 sc_primary_test_dem
"""
from __future__ import annotations

import os
import sqlite3

import httpx

DB = os.path.join("data", "db", "baseline.db")
BASE = "https://www.enr-scvotes.org/SC"
PARTY = {"DEM": "DEM", "REP": "REP", "LIB": "LIB", "GRE": "GRE", "GRN": "GRE"}


def _get(url, timeout=30):
    r = httpx.get(url, timeout=timeout)
    r.raise_for_status()
    return r


def current_version(election_id):
    return _get(f"{BASE}/{election_id}/current_ver.txt").text.strip()


def contest_candidates(election_id, version, contest_code):
    """(candidate_names, parties) in the SAME order as ALL.json's V arrays for this code."""
    summary = _get(f"{BASE}/{election_id}/{version}/json/en/summary.json").json()
    for c in summary:
        if c["K"] == str(contest_code):
            return c["CH"], [PARTY.get(p.strip().upper(), "OTH") for p in c["P"]]
    raise KeyError(f"contest code {contest_code} not found in summary.json")


def county_votes(election_id, version, contest_code):
    """{COUNTY_NAME_UPPER: [votes_per_candidate]} (excludes the '-1' pseudo-county)."""
    data = _get(f"{BASE}/{election_id}/{version}/json/ALL.json").json()["Contests"]
    out = {}
    for county in data:
        if county["A"] == "-1":
            continue
        codes = county["C"]
        if str(contest_code) not in codes:
            continue
        idx = codes.index(str(contest_code))
        out[county["A"].strip().upper()] = county["V"][idx]
    return out


def ingest(election_id, contest_code, race_type, db_path=DB):
    version = current_version(election_id)
    candidates, parties = contest_candidates(election_id, version, contest_code)
    counties = county_votes(election_id, version, contest_code)

    conn = sqlite3.connect(db_path)
    fips = {r[0]: r[1] for r in conn.execute(
        "SELECT county, county_fips FROM precincts WHERE id LIKE 'SC-%-CTY'")}
    counties = {nm: v for nm, v in counties.items() if nm in fips}

    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE 'SC-%'",
                 (race_type,))
    payload = []
    d_tot = r_tot = 0
    for nm, votes in counties.items():
        pid = f"SC-{fips[nm]}-CTY"
        ctot = sum(votes) or 1
        for cand, party, v in zip(candidates, parties, votes):
            payload.append((pid, race_type, cand, party, v, v / ctot,
                            len(counties), len(fips), "all"))
            if party == "DEM":
                d_tot += v
            elif party == "REP":
                r_tot += v
    conn.executemany(
        """INSERT INTO results_live
           (precinct_id, race_type, candidate, party, votes, vote_share,
            precincts_reporting, total_precincts, mode)
           VALUES (?,?,?,?,?,?,?,?,?)""", payload)
    conn.commit()
    conn.close()
    return {"counties_in": len(counties), "counties_total": len(fips),
            "rows": len(payload), "dem": d_tot, "rep": r_tot, "version": version}


if __name__ == "__main__":
    import sys
    eid = sys.argv[1] if len(sys.argv) > 1 else "126294"
    contest_code = sys.argv[2] if len(sys.argv) > 2 else "26001"
    race = sys.argv[3] if len(sys.argv) > 3 else "senate"
    print(f"SC live ingest — election {eid} · contest {contest_code} -> results_live (race={race})")
    s = ingest(eid, contest_code, race)
    tot = s["dem"] + s["rep"] or 1
    print(f"  version: {s['version']}   counties: {s['counties_in']}/{s['counties_total']}   rows: {s['rows']}")
    print(f"  live two-party: D {s['dem']:,} ({100*s['dem']/tot:.1f}%)   "
          f"R {s['rep']:,} ({100*s['rep']/tot:.1f}%)   "
          f"winner: {'D' if s['dem'] > s['rep'] else 'R'}")
