"""tx_live_feed.py — Texas live ingestion into results_live (county level).

TX runs its own election-night system at results.texas-election.com (an
Angular SPA, NOT Clarity/Enhanced Voting). A Cloudflare WAF rule blocks plain
httpx outright ("Attention Required!", not just a JS challenge) — but a
Playwright-driven Chromium passes cleanly, and HEADLESS is enough here (unlike
MI, which strictly needs a headed browser). Confirmed both headless and headed
return the identical 1.8MB payload.

THE DATA: one call gives EVERY county x EVERY race in the whole state, keyed
directly by 5-digit county FIPS (e.g. "48001") — an exact match to our
county_fips column, no name-matching at all (simpler than every other state
wired so far, which all needed at least an uppercase county-NAME match):
    /static/data/election/{electionId}/{version}/County.json
    -> {"48001": {"N": "ANDERSON", "TV": <total votes>,
                  "Races": {"1001": {"ON": "PRESIDENT/VICE-PRESIDENT",
                                     "C": {candId: {N, P: party, V: votes}}}}}}
`version` is NOT the election id — it's a data-version number that bumps as
new results are published (matches AZ's uploadId pattern), fetched fresh via:
    /static/data/election/{electionId}/Version.json -> {"___versionNo": N}
electionId itself is discoverable (not hardcoded) via:
    /static/data/ElectionConstants_404.json -> electionInfo[year][type]
      (type: "G"=general, "P"=primary, "RU"=primary runoff, "SE"=special, ...)

President OID = 1001, U.S. Senator OID = 7958 (confirmed from the 2024 data;
these office ids look stable across cycles but re-verify from Race.json if
a lookup ever comes back empty).

CLI (test against the 2024 general — President + Senate both on this ballot):
  python ingestor/tx_live_feed.py 2024 G 1001 president
  python ingestor/tx_live_feed.py 2024 G 7958 senate
"""
from __future__ import annotations

import os
import sqlite3

from playwright.sync_api import sync_playwright

DB = os.path.join("data", "db", "baseline.db")
BASE_URL = "https://results.texas-election.com/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
PARTY = {"REP": "REP", "DEM": "DEM", "LIB": "LIB", "GRE": "GRE", "GRN": "GRE"}

FETCH_JSON_JS = """
async (path) => {
    const r = await fetch(path);
    if (!r.ok) return {ok: false, status: r.status};
    return {ok: true, body: await r.text()};
}
"""


def _with_page(fn):
    """Run fn(page) inside a Chromium context that's loaded the TX results
    page first (needed to pass the Cloudflare WAF rule on the JSON paths;
    headless is sufficient for TX, unlike MI)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA)
        page = ctx.new_page()
        page.goto(BASE_URL, timeout=30000)
        page.wait_for_timeout(3000)
        try:
            return fn(page)
        finally:
            browser.close()


def _fetch_json(page, path):
    import json
    result = page.evaluate(FETCH_JSON_JS, path)
    if not result.get("ok"):
        raise RuntimeError(f"{path} failed: HTTP {result.get('status')}")
    return json.loads(result["body"])


def discover_election_id(year, etype="G"):
    """Look up electionInfo[str(year)][etype] in ElectionConstants_404.json.
    Returns the numeric election id, or None if not configured yet."""
    def _run(page):
        d = _fetch_json(page, "/static/data/ElectionConstants_404.json")
        bucket = d.get("electionInfo", {}).get(str(year), {}).get(etype, {})
        if not bucket:
            return None
        return next(iter(bucket))   # single G/P election per year in practice
    return _with_page(_run)


def current_version(election_id):
    def _run(page):
        d = _fetch_json(page, f"/static/data/election/{election_id}/Version.json")
        return d["___versionNo"]
    return _with_page(_run)


def county_totals(election_id, office_id, version=None):
    """{county_fips: [(candidate, party, votes), ...]}"""
    def _run(page):
        v = version or _fetch_json(page, f"/static/data/election/{election_id}/Version.json")["___versionNo"]
        d = _fetch_json(page, f"/static/data/election/{election_id}/{v}/County.json")
        out = {}
        for fips, county in d.items():
            race = county.get("Races", {}).get(str(office_id))
            if not race:
                continue
            cands = []
            for cand in race["C"].values():
                party = PARTY.get(cand["P"].strip().upper(), "OTH")
                cands.append((cand["N"], party, int(cand.get("V") or 0)))
            out[fips] = cands
        return out, v
    return _with_page(_run)


def ingest(election_id, office_id, race_type, db_path=DB):
    totals, version = county_totals(election_id, office_id)
    conn = sqlite3.connect(db_path)
    fips = {r[0] for r in conn.execute(
        "SELECT county_fips FROM precincts WHERE id LIKE 'TX-%-CTY'")}
    totals = {f: cands for f, cands in totals.items() if f in fips}

    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE 'TX-%'",
                 (race_type,))
    payload = []
    d_tot = r_tot = 0
    for f, cands in totals.items():
        pid = f"TX-{f}-CTY"
        ctot = sum(v for _, _, v in cands) or 1
        for cand, party, votes in cands:
            payload.append((pid, race_type, cand, party, votes, votes / ctot,
                            len(totals), len(fips), "all"))
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
    return {"counties_in": len(totals), "counties_total": len(fips),
            "rows": len(payload), "dem": d_tot, "rep": r_tot, "version": version}


if __name__ == "__main__":
    import sys
    year = sys.argv[1] if len(sys.argv) > 1 else "2024"
    etype = sys.argv[2] if len(sys.argv) > 2 else "G"
    office_id = sys.argv[3] if len(sys.argv) > 3 else "1001"
    race = sys.argv[4] if len(sys.argv) > 4 else "president"
    print(f"TX live ingest — discovering electionId for {year} {etype!r} ...")
    eid = discover_election_id(year, etype)
    if eid is None:
        print(f"  NOT FOUND: {year} {etype!r} isn't configured on results.texas-election.com yet.")
        sys.exit(1)
    print(f"  electionId = {eid}")
    print(f"Fetching + parsing County.json -> results_live (race={race}, office={office_id}) ...")
    s = ingest(eid, office_id, race)
    tot = s["dem"] + s["rep"] or 1
    print(f"  version: {s['version']}   counties: {s['counties_in']}/{s['counties_total']}   rows: {s['rows']}")
    print(f"  live two-party: D {s['dem']:,} ({100*s['dem']/tot:.1f}%)   "
          f"R {s['rep']:,} ({100*s['rep']/tot:.1f}%)   "
          f"winner: {'D' if s['dem'] > s['rep'] else 'R'}")
