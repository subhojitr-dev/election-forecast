"""pa_live_feed.py — Pennsylvania live ingestion into results_live (county level).

PA runs its OWN election-night reporting system at electionreturns.pa.gov (NOT
Clarity, NOT Enhanced Voting — an AngularJS SPA over an open ASP.NET API). The
API is OPEN (plain httpx works, no Incapsula block observed on the API paths):
  elections list:  /api/ElectionReturn/GetAllElections?methodName=GetAllElections
  office list:      /api/ElectionReturn/GetOfficeNames?countyName=&methodName=GetOfficeNames
                     &electionid={EID}&electiontype={G|P}&isactive={0|1}
  county breakdown: /api/ElectionReturn/GetCountyBreak?officeId={OID}&districtId=1
                     &methodName=GetCountyBreak&electionid={EID}&electiontype={G|P}
                     &isactive={0|1}
GetCountyBreak returns {"Election":{"Statewide":[{ "ADAMS":[{...}], "ALLEGHENY":[...], ...}]}}
— one key per county (67, matching our county names exactly, no name-matching
needed), each a list of candidate rows with Votes AND a live ballot-mode split
(ElectionDayVotes / MailInVotes / ProvisionalVotes) — PA has NO early in-person
voting, so only those 3 modes exist (unlike NC's 4).

We map each county to PA-{fips}-CTY (the county-pseudo baseline, see
etl_pa_county_baseline.py) and write to results_live per mode — so the existing
analytics compute PA's shift / win-prob / county table unchanged.

CLI (test against the 2024 general — offers both President officeId=1 and
Senate officeId=2 on the same electionid):
  python ingestor/pa_live_feed.py 105 G 2 1 senate
  python ingestor/pa_live_feed.py 105 G 1 1 president
"""
from __future__ import annotations

import json
import os
import sqlite3

import httpx

DB = os.path.join("data", "db", "baseline.db")
API = "https://www.electionreturns.pa.gov/api/ElectionReturn"
PARTY = {"DEM": "DEM", "REP": "REP", "LIB": "LIB", "GRN": "GRE", "GREEN": "GRE"}
MODE_COLS = {"ElectionDayVotes": "election_day", "MailInVotes": "mail",
             "ProvisionalVotes": "provisional"}


def _get(url, timeout=30):
    r = httpx.get(url, timeout=timeout)
    r.raise_for_status()
    # response body is itself a JSON string containing JSON — unwrap once or twice
    d = r.json()
    if isinstance(d, str):
        d = json.loads(d)
    return d


def county_breakdown(eid, etype, office_id, district_id=1, isactive=0):
    """{COUNTY_NAME_UPPER: [(candidate, party, votes, {mode: votes}), ...]}"""
    url = (f"{API}/GetCountyBreak?officeId={office_id}&districtId={district_id}"
           f"&methodName=GetCountyBreak&electionid={eid}&electiontype={etype}"
           f"&isactive={isactive}")
    d = _get(url)
    counties = d["Election"]["Statewide"][0]
    out = {}
    for county, rows in counties.items():
        cands = []
        for row in rows:
            party = PARTY.get(row["PartyName"].strip().upper(), "OTH")
            votes = int(row["Votes"] or 0)
            modes = {MODE_COLS[c]: int(row.get(c) or 0) for c in MODE_COLS}
            cands.append((row["CandidateName"], party, votes, modes))
        out[county.strip().upper()] = cands
    return out


def ingest(eid, etype, office_id, race_type, db_path=DB, district_id=1, isactive=0):
    conn = sqlite3.connect(db_path)
    fips = {r[0]: r[1] for r in conn.execute(
        "SELECT county, county_fips FROM precincts WHERE id LIKE 'PA-%-CTY'")}
    counties = county_breakdown(eid, etype, office_id, district_id, isactive)
    counties = {nm: cands for nm, cands in counties.items() if nm in fips}

    # clear ALL PA live rows for this race (incl. leftover precinct-level rows
    # from prior sim/test runs) so only this feed's county totals remain
    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE 'PA-%'",
                 (race_type,))
    payload = []
    d_tot = r_tot = 0
    for nm, cands in counties.items():
        pid = f"PA-{fips[nm]}-CTY"
        ctot = sum(v for _, _, v, _ in cands) or 1
        for cand, party, votes, modes in cands:
            for mode, mv in modes.items():
                if mv:
                    payload.append((pid, race_type, cand, party, mv, mv / ctot,
                                    len(counties), len(fips), mode))
            if party == "DEM":
                d_tot += votes
            elif party == "REP":
                r_tot += votes
    conn.executemany(
        """INSERT INTO results_live
           (precinct_id, race_type, candidate, party, votes, vote_share,
            precincts_reporting, total_precincts, mode)
           VALUES (?,?,?,?,?,?,?,?,?)""", payload)
    conn.commit()
    conn.close()
    return {"counties_in": len(counties), "counties_total": len(fips),
            "rows": len(payload), "dem": d_tot, "rep": r_tot}


if __name__ == "__main__":
    import sys
    eid = sys.argv[1] if len(sys.argv) > 1 else "105"
    etype = sys.argv[2] if len(sys.argv) > 2 else "G"
    office_id = sys.argv[3] if len(sys.argv) > 3 else "2"
    district_id = sys.argv[4] if len(sys.argv) > 4 else "1"
    race = sys.argv[5] if len(sys.argv) > 5 else "senate"
    print(f"PA live ingest — election {eid}/{etype} office {office_id} -> results_live (race={race})")
    s = ingest(eid, etype, office_id, race, district_id=district_id)
    tot = s["dem"] + s["rep"] or 1
    print(f"  counties: {s['counties_in']}/{s['counties_total']}   rows: {s['rows']}")
    print(f"  live two-party: D {s['dem']:,} ({100*s['dem']/tot:.1f}%)   "
          f"R {s['rep']:,} ({100*s['rep']/tot:.1f}%)   "
          f"winner: {'D' if s['dem'] > s['rep'] else 'R'}")
