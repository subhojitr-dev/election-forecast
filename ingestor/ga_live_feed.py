"""ga_live_feed.py — Georgia live ingestion into results_live (county level).

GA moved off Clarity to Enhanced Voting. Its API is OPEN (plain httpx works):
  state:  results.sos.ga.gov/results/public/api/elections/Georgia/{EID}/data
  county: results.sos.ga.gov/results/public/api/elections/{county-shortName}/{EID}/data
The state call lists the 159 counties (childLocalities); each county call returns
that county's contests -> summaryResults.ballotOptions (candidate + voteCount).
Party is in the candidate name suffix, e.g. "Kamala D. Harris (Dem)".

We fetch all 159 counties (in parallel), map each to GA-{fips}-CTY (the county-
pseudo baseline already loaded), and write to results_live — so the existing
analytics compute GA's shift / win-prob / county table unchanged.

CLI (test against a past GA election):
  python ingestor/ga_live_feed.py 2024NovGen "President of the US" president
"""
from __future__ import annotations

import os
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import httpx

DB = os.path.join("data", "db", "baseline.db")
API = "https://results.sos.ga.gov/results/public/api/elections"
PARTY = {"REP": "REP", "DEM": "DEM", "LIB": "LIB", "GRN": "GRE", "GREEN": "GRE",
         "IND": "OTH", "CST": "OTH"}


def _text(name):
    return name[0]["text"] if isinstance(name, list) and name else (name or "")


def _party(cand_name):
    m = re.search(r"\(([^)]+)\)\s*$", cand_name)
    return PARTY.get(m.group(1).strip().upper(), "OTH") if m else "OTH"


def _get(url, timeout=30):
    r = httpx.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def counties(eid):
    """[(shortName, COUNTY_NAME_UPPER)] from the state feed's childLocalities."""
    d = _get(f"{API}/Georgia/{eid}/data")
    return [(loc["shortName"], (loc.get("mapFeatureId") or _text(loc["name"])).upper())
            for loc in d["jurisdiction"]["childLocalities"]]


def county_contest(short_name, eid, contest_filter):
    """Candidates for the matching contest in one county: [(cand, party, votes)]."""
    d = _get(f"{API}/{short_name}/{eid}/data")
    cf = contest_filter.upper()
    for b in d["ballotItems"]:
        if cf in _text(b.get("name", "")).upper():
            out = []
            for o in (b.get("summaryResults") or {}).get("ballotOptions", []):
                nm = _text(o["name"])
                out.append((nm, _party(nm), o.get("voteCount") or 0))
            return out
    return []


def ingest(eid, contest_filter, race_type="senate", db_path=DB, workers=16):
    conn = sqlite3.connect(db_path)
    fips = {r[0]: r[1] for r in conn.execute(
        "SELECT county, county_fips FROM precincts WHERE id LIKE 'GA-%-CTY'")}
    cs = [(sn, nm) for sn, nm in counties(eid) if nm in fips]

    def work(item):
        sn, nm = item
        try:
            return nm, county_contest(sn, eid, contest_filter)
        except Exception:
            return nm, []
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for nm, cands in ex.map(work, cs):
            results[nm] = cands

    reporting = sum(1 for nm in results if results[nm])
    # clear ALL GA live rows for this race (incl. leftover precinct-level rows
    # from prior sim/test runs) so only this feed's county totals remain
    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE 'GA-%'",
                 (race_type,))
    payload = []
    d_tot = r_tot = 0
    for nm, cands in results.items():
        pid = f"GA-{fips[nm]}-CTY"
        ctot = sum(v for _, _, v in cands) or 1
        for cand, party, votes in cands:
            if votes or party in ("DEM", "REP"):
                payload.append((pid, race_type, cand, party, votes, votes / ctot,
                                reporting, len(fips), "all"))
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
    return {"counties_in": reporting, "counties_total": len(fips),
            "rows": len(payload), "dem": d_tot, "rep": r_tot}


if __name__ == "__main__":
    import sys
    eid = sys.argv[1] if len(sys.argv) > 1 else "2024NovGen"
    contest = sys.argv[2] if len(sys.argv) > 2 else "President of the US"
    race = sys.argv[3] if len(sys.argv) > 3 else "president"
    print(f"GA live ingest — {eid} · {contest!r} -> results_live (race={race})")
    s = ingest(eid, contest, race)
    tot = s["dem"] + s["rep"] or 1
    print(f"  counties: {s['counties_in']}/{s['counties_total']}   rows: {s['rows']}")
    print(f"  live two-party: D {s['dem']:,} ({100*s['dem']/tot:.1f}%)   "
          f"R {s['rep']:,} ({100*s['rep']/tot:.1f}%)   "
          f"winner: {'D' if s['dem'] > s['rep'] else 'R'}")
