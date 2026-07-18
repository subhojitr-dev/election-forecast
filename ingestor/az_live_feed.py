"""az_live_feed.py — Arizona live ingestion into results_live (county level).

AZ runs its own election-night system at results.arizona.vote (a Cloudflare-
protected AngularJS SPA — the PAGE needs a real browser, but its DATA lives on
a separate, OPEN CDN with no Cloudflare in front: cdn1.arizona.vote — plain
httpx works). Two-step fetch:
  1. GET  /data/{electionId}/{jurisdictionId}/election_{electionId}_{jurisdictionId}.json
     -> {"uploadId": N, ...}  — the CURRENT data version. This bumps every time
     the state publishes a new results batch, so it must be re-fetched each poll.
  2. GET  /data/{electionId}/{jurisdictionId}/all_county_races_{electionId}_{jurisdictionId}_en_{uploadId}.json
     -> ONE JSON array with EVERY county x EVERY contest x EVERY candidate in a
     single call (no per-county loop needed, no per-race loop needed — simpler
     than GA and PA). Row shape: {CountyName, ContestName, ChoiceName,
     ChoiceTotalVotes, PrecinctsReported, PrecinctsParticipating, ...}.

Party is in a "(CODE)" suffix — on ChoiceName for GENERAL elections (e.g.
"Gallego, Ruben (DEM)"), but on ContestName for PRIMARY elections instead,
since AZ splits each party into its own contest row (e.g. "Governor (DEM)"
with plain candidate names as ChoiceName). We check ChoiceName first, then
fall back to ContestName.

NO live ballot-mode split is exposed here (unlike NC/PA) — AZ's turnout file
(voter_turnout_*.json) has statewide EarlyBallotsRemaining/ProvisionalBallots
Remaining counts but no per-candidate mode breakdown, so mode='all' (like GA).

electionId is STABLE and known well ahead of the night (AZ publishes the
results-app election id as soon as the election is configured — no waiting for
an auto-discovery scheme): see az_election_ids() below.

CLI (test against the 2024 general — President + Senate both on this ballot):
  python ingestor/az_live_feed.py 47 0 "President of the United States" president
  python ingestor/az_live_feed.py 47 0 "U.S. Senator" senate

Election-night mechanics check (2026 primary, electionId=68 — AZ has NO
President/Senate race on this ballot per api/elections.py, so this is a
plumbing/mechanics test only; use a real statewide primary contest like
Governor, and a scratch race_type so it can never surface in the UI):
  python ingestor/az_live_feed.py 68 0 "Governor (DEM)" az_primary_test
"""
from __future__ import annotations

import re
import os
import sqlite3

import httpx

DB = os.path.join("data", "db", "baseline.db")
BASE = "https://cdn1.arizona.vote/data"
PARTY = {"DEM": "DEM", "REP": "REP", "LBT": "LIB", "LIB": "LIB",
         "GRN": "GRE", "GRE": "GRE", "NOL": "OTH", "IND": "OTH"}


def az_election_ids():
    """Known results.arizona.vote electionIds (from the site's own election
    list at results.arizona.vote/#/featured/{id}/0 — stable well ahead of
    the night, no live discovery needed)."""
    return {
        "2026 primary": 68, "2025 special general": 72, "2025 special primary": 71,
        "2024 general": 47, "2024 primary": 46, "2024 ppe": 59,
        "2022 general": 33, "2022 primary": 32, "2020 general": 18,
        "2020 primary": 17, "2020 ppe": 27, "2018 general": 4,
    }


def _get(url, timeout=30):
    r = httpx.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def current_upload_id(election_id, jurisdiction_id=0):
    d = _get(f"{BASE}/{election_id}/{jurisdiction_id}/election_{election_id}_{jurisdiction_id}.json")
    return d["uploadId"]


def _party(choice_name, contest_name):
    for text in (choice_name, contest_name):
        m = re.search(r"\(([^)]+)\)\s*$", text or "")
        if m:
            return PARTY.get(m.group(1).strip().upper(), "OTH")
    return "OTH"


def county_races(election_id, jurisdiction_id, contest_filter, upload_id=None):
    """[(county_upper, candidate, party, votes, reported, participating)]"""
    if upload_id is None:
        upload_id = current_upload_id(election_id, jurisdiction_id)
    url = (f"{BASE}/{election_id}/{jurisdiction_id}/all_county_races_"
           f"{election_id}_{jurisdiction_id}_en_{upload_id}.json")
    rows = _get(url)
    cf = contest_filter.upper()
    out = []
    for r in rows:
        if cf not in r["ContestName"].upper():
            continue
        party = _party(r.get("ChoiceName"), r["ContestName"])
        out.append((r["CountyName"].strip().upper(), r["ChoiceName"], party,
                     int(r.get("ChoiceTotalVotes") or 0),
                     int(r.get("PrecinctsReported") or 0),
                     int(r.get("PrecinctsParticipating") or 0)))
    return out, upload_id


def ingest(election_id, jurisdiction_id, contest_filter, race_type, db_path=DB):
    conn = sqlite3.connect(db_path)
    fips = {r[0]: r[1] for r in conn.execute(
        "SELECT county, county_fips FROM precincts WHERE id LIKE 'AZ-%-CTY'")}
    rows, upload_id = county_races(election_id, jurisdiction_id, contest_filter)
    rows = [r for r in rows if r[0] in fips]
    present = {r[0] for r in rows}
    reported = sum(r[4] for r in rows)
    participating = sum(r[5] for r in rows) or 1

    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE 'AZ-%'",
                 (race_type,))
    ctot = {}
    for county, _, _, votes, _, _ in rows:
        ctot[county] = ctot.get(county, 0) + votes
    payload = []
    d_tot = r_tot = 0
    for county, cand, party, votes, _, _ in rows:
        pid = f"AZ-{fips[county]}-CTY"
        ct = ctot.get(county) or 1
        payload.append((pid, race_type, cand, party, votes, votes / ct,
                        reported, participating, "all"))
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
    return {"counties_in": len(present), "counties_total": len(fips),
            "rows": len(payload), "dem": d_tot, "rep": r_tot,
            "upload_id": upload_id, "precincts_reporting": reported,
            "total_precincts": participating}


if __name__ == "__main__":
    import sys
    eid = int(sys.argv[1]) if len(sys.argv) > 1 else 47
    jid = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    contest = sys.argv[3] if len(sys.argv) > 3 else "President of the United States"
    race = sys.argv[4] if len(sys.argv) > 4 else "president"
    print(f"AZ live ingest — election {eid}/{jid} · {contest!r} -> results_live (race={race})")
    s = ingest(eid, jid, contest, race)
    tot = s["dem"] + s["rep"] or 1
    print(f"  uploadId: {s['upload_id']}   counties: {s['counties_in']}/{s['counties_total']}   "
          f"rows: {s['rows']}   precincts: {s['precincts_reporting']}/{s['total_precincts']}")
    print(f"  live two-party: D {s['dem']:,} ({100*s['dem']/tot:.1f}%)   "
          f"R {s['rep']:,} ({100*s['rep']/tot:.1f}%)   "
          f"winner: {'D' if s['dem'] > s['rep'] else 'R'}")
