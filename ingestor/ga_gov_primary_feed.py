"""ga_gov_primary_feed.py — GA's real May 19, 2026 Governor primary, pulled from
the same Enhanced Voting API ga_live_feed.py already uses, as a "showcase" that
GA's live feed genuinely works (proven once already for the Nov-2026 Senate
general's plumbing; this exercises it against a real, already-decided primary
night instead of live data, the same role mi_primary_2026 played for MI).

Election id discovered via the /api/jurisdictions/Georgia listing endpoint
(the same discovery shortcut documented in mi_enhancedvoting_feed.py):
publicElectionId "GeneralPrimary51926".

**Governor is TWO separate contests per county**, not one combined race with
a party suffix on each name (unlike ga_live_feed.py's Nov-general pattern,
where "Kamala D. Harris (Dem)" carries its party in the name) — confirmed via
Fulton County's raw response:
    "Governor - Rep"  -> Chris Carr, Rick Jackson, Burt Jones, ...
    "Governor - Dem"  -> Keisha Lance Bottoms, Jason Esteves, ...
Party comes from which CONTEST a candidate is under, not their name. This is
why ga_live_feed.py's ingest() (built for one combined general-election
contest) isn't reused as-is — county_contest() there returns only the FIRST
ballotItem matching a loose filter, which would silently drop one party's
whole field. This module fetches BOTH contests explicitly per county instead.

Only the May 19 first round is pulled (not the June 16 GOP runoff between
Jackson and Jones, since neither hit 50% that night) — matches the "one
primary night" scope the MI showcase covered.

Usage:
    python ingestor/ga_gov_primary_feed.py
"""
from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import httpx

DB = os.path.join("data", "db", "baseline.db")
API = "https://results.sos.ga.gov/results/public/api/elections"
EID = "GeneralPrimary51926"
CONTESTS = {"governor - dem": "DEM", "governor - rep": "REP"}


def _text(name):
    return name[0]["text"] if isinstance(name, list) and name else (name or "")


def _get(url, timeout=30):
    r = httpx.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.json()


def counties():
    d = _get(f"{API}/Georgia/{EID}/data")
    return [(loc["shortName"], (loc.get("mapFeatureId") or _text(loc["name"])).upper())
            for loc in d["jurisdiction"]["childLocalities"]]


def county_governor_primary(short_name):
    """[(candidate, party, votes), ...] for BOTH "Governor - Dem" and
    "Governor - Rep" in one county (not just whichever matches first)."""
    d = _get(f"{API}/{short_name}/{EID}/data")
    out = []
    for b in d["ballotItems"]:
        party = CONTESTS.get(_text(b.get("name", "")).strip().lower())
        if party is None:
            continue
        for o in (b.get("summaryResults") or {}).get("ballotOptions", []):
            nm = _text(o["name"])
            if nm.strip().lower() == "write-in":
                continue
            out.append((nm, party, o.get("voteCount") or 0))
    return out


def ingest(db_path=DB, race_type="ga_gov_primary_2026", workers=16):
    conn = sqlite3.connect(db_path)
    fips = {r[0]: r[1] for r in conn.execute(
        "SELECT county, county_fips FROM precincts WHERE id LIKE 'GA-%-CTY'")}
    cs = [(sn, nm) for sn, nm in counties() if nm in fips]

    def work(item):
        sn, nm = item
        try:
            return nm, county_governor_primary(sn)
        except Exception:
            return nm, []
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for nm, cands in ex.map(work, cs):
            results[nm] = cands

    reporting = sum(1 for nm in results if results[nm])
    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE 'GA-%'",
                 (race_type,))
    payload = []
    for nm, cands in results.items():
        pid = f"GA-{fips[nm]}-CTY"
        for cand, party, votes in cands:
            payload.append((pid, race_type, cand, party, votes, None,
                            reporting, len(fips), "all"))
    conn.executemany(
        """INSERT INTO results_live
           (precinct_id, race_type, candidate, party, votes, vote_share,
            precincts_reporting, total_precincts, mode)
           VALUES (?,?,?,?,?,?,?,?,?)""", payload)
    conn.commit()
    conn.close()
    return {"counties_in": reporting, "counties_total": len(fips), "rows": len(payload)}


if __name__ == "__main__":
    s = ingest()
    print(f"GA Governor primary (5/19/2026): {s['counties_in']}/{s['counties_total']} "
          f"counties, {s['rows']} rows written")
