"""mi_live_feed.py — Michigan live ingestion into results_live (county level).

MI's own system (mvic.sos.state.mi.us) sits behind Cloudflare, and — unlike
GA/PA/AZ — a HEADLESS browser gets a 403 "Just a moment..." challenge page on
every request, including the bulk-download endpoint (confirmed 2026-07-06,
re-confirmed here). A HEADED (non-headless) Chromium with navigator.webdriver
masked passes the challenge cleanly. So this ingestor drives a real Playwright
browser instead of plain httpx.

THE DATA: the votehistory app (an ASP.NET MVC app, NOT a JSON API) exposes one
enormous win: a single bulk ZIP per election with EVERY precinct x EVERY
office in the state —
    /VoteHistory/GetPrecinctResultsFile?electionId={N}
— e.g. "2024GEN.zip" containing tab-delimited, no-header files:
    {yr}vote.txt   ElectionYear,ElectionType,OfficeCode,DistrictCode,
                   StatusCode,CandidateId,CountyCode,CityTownCode,Ward,
                   Precinct,PrecinctLabel,Votes   (one row per precinct;
                   OfficeCode 1=President, 5=U.S. Senator — see readme.txt
                   inside the zip for the full code list)
    {yr}name.txt   ...,CandidateId,Last,First,Middle,Party
    county.txt     CountyCode,CountyCode,CountyName   (no year prefix)
This is the SAME bulk-file shape as NC's approach — one download, then we
aggregate precinct rows to county totals ourselves (matching our
county-pseudo-precinct pattern). No per-county/per-township loop needed.

electionId is NOT known ahead of time the way AZ's is — MI adds each new
election to the #ElectionDateId dropdown on /votehistory/Index only once it's
configured in their system (may not appear until close to/on the day). So
this script re-discovers the id each run by scanning that dropdown's option
text for the target date, rather than hardcoding it.

CLI (test against the 2024 general — President + Senate both on this ballot):
  python ingestor/mi_live_feed.py "11/5/2024" president
  python ingestor/mi_live_feed.py "11/5/2024" senate

On primary night (once the state adds the election, expected on/near Aug 4):
  python ingestor/mi_live_feed.py "8/4/2026" senate
"""
from __future__ import annotations

import base64
import io
import os
import re
import sqlite3
import zipfile

from playwright.sync_api import sync_playwright

DB = os.path.join("data", "db", "baseline.db")
BASE = "https://mvic.sos.state.mi.us"
INDEX_URL = f"{BASE}/votehistory/Index?type=C&electionDate=11-5-2024"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
OFFICE_CODE = {"president": "1", "senate": "5"}
PARTY = {"DEM": "DEM", "REP": "REP", "LIB": "LIB", "GRN": "GRE", "GRE": "GRE",
         "NLP": "OTH", "NPA": "OTH", "RFP": "OTH", "TIS": "OTH", "UST": "OTH",
         "WCP": "OTH", "WORW": "OTH"}
# MI's bulk-file county names vs our DB's county names (see etl_mi_county_baseline.py)
COUNTY_ALIASES = {"GD. TRAVERSE": "GRAND TRAVERSE", "GD TRAVERSE": "GRAND TRAVERSE"}


def _norm_county(name):
    name = name.strip().upper()
    name = COUNTY_ALIASES.get(name, name)
    return name.replace(".", "")


FETCH_ZIP_JS = """
async (electionId) => {
    const r = await fetch('/VoteHistory/GetPrecinctResultsFile?electionId=' + electionId);
    if (!r.ok) return {ok: false, status: r.status};
    const buf = await r.arrayBuffer();
    const bytes = new Uint8Array(buf);
    let binary = '';
    const chunkSize = 8192;
    for (let i = 0; i < bytes.length; i += chunkSize) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    return {ok: true, b64: btoa(binary)};
}
"""


def _with_page(fn):
    """Run fn(page) inside a headed, webdriver-masked Chromium (the config
    that passes MI's Cloudflare challenge — headless gets 403)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(user_agent=UA)
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = ctx.new_page()
        page.goto(INDEX_URL, timeout=30000)
        page.wait_for_timeout(6000)
        try:
            return fn(page)
        finally:
            browser.close()


def discover_election_id(date_str):
    """Scan #ElectionDateId's options for one whose text starts with date_str
    (e.g. '8/4/2026'). Returns the numeric value, or None if not listed yet."""
    def _run(page):
        options = page.eval_on_selector_all(
            "#ElectionDateId option", "els => els.map(e => [e.value, e.textContent.trim()])")
        for value, text in options:
            if text.startswith(date_str):
                return value
        return None
    return _with_page(_run)


def fetch_zip_bytes(election_id):
    def _run(page):
        result = page.evaluate(FETCH_ZIP_JS, str(election_id))
        if not result.get("ok"):
            raise RuntimeError(f"GetPrecinctResultsFile failed: HTTP {result.get('status')}")
        return base64.b64decode(result["b64"])
    return _with_page(_run)


def _member(zf, suffix):
    for n in zf.namelist():
        if n.endswith(suffix):
            return n
    raise KeyError(f"no member ending in {suffix!r} in {zf.namelist()}")


def parse_county_totals(zip_bytes, office_code):
    """{county_name_normalized: {(candidate, party): votes}}"""
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    county_txt = zf.read(_member(zf, "county.txt")).decode("utf-8-sig", errors="replace")
    counties = {}
    for line in county_txt.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].strip().isdigit():
            counties[parts[0].strip()] = _norm_county(parts[-1])

    name_txt = zf.read(_member(zf, "name.txt")).decode("utf-8-sig", errors="replace")
    candidates = {}   # candidate_id -> (name, party)
    for line in name_txt.splitlines():
        f = line.split("\t")
        if len(f) < 10 or f[2].strip() != office_code:
            continue
        cand_id = f[5].strip()
        last, first, middle, party = f[6].strip(), f[7].strip(), f[8].strip(), f[9].strip()
        full = f"{last}, {first} {middle}".strip()
        candidates[cand_id] = (full, PARTY.get(party.upper(), "OTH"))

    vote_txt = zf.read(_member(zf, "vote.txt")).decode("utf-8-sig", errors="replace")
    totals = {}   # county -> (candidate, party) -> votes
    for line in vote_txt.splitlines():
        f = line.split("\t")
        if len(f) < 12 or f[2].strip() != office_code:
            continue
        cand_id, county_code, votes = f[5].strip(), f[6].strip(), int(f[11].strip() or 0)
        if cand_id not in candidates or county_code not in counties:
            continue
        county = counties[county_code]
        key = candidates[cand_id]
        totals.setdefault(county, {})
        totals[county][key] = totals[county].get(key, 0) + votes
    return totals


def ingest(election_id, race_type, db_path=DB):
    office_code = OFFICE_CODE[race_type]
    zip_bytes = fetch_zip_bytes(election_id)
    totals = parse_county_totals(zip_bytes, office_code)

    conn = sqlite3.connect(db_path)
    fips = {_norm_county(r[0]): r[1] for r in conn.execute(
        "SELECT county, county_fips FROM precincts WHERE id LIKE 'MI-%-CTY'")}
    totals = {c: v for c, v in totals.items() if c in fips}

    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE 'MI-%'",
                 (race_type,))
    payload = []
    d_tot = r_tot = 0
    for county, cands in totals.items():
        pid = f"MI-{fips[county]}-CTY"
        ctot = sum(cands.values()) or 1
        for (cand, party), votes in cands.items():
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
            "rows": len(payload), "dem": d_tot, "rep": r_tot}


if __name__ == "__main__":
    import sys
    date_str = sys.argv[1] if len(sys.argv) > 1 else "11/5/2024"
    race = sys.argv[2] if len(sys.argv) > 2 else "president"
    print(f"MI live ingest — discovering electionId for {date_str!r} ...")
    eid = discover_election_id(date_str)
    if eid is None:
        print(f"  NOT FOUND: {date_str!r} isn't in #ElectionDateId yet "
              f"(MI hasn't configured this election in their system yet — retry closer to the night).")
        sys.exit(1)
    print(f"  electionId = {eid}")
    print(f"Fetching + parsing bulk ZIP -> results_live (race={race}) ...")
    s = ingest(eid, race)
    tot = s["dem"] + s["rep"] or 1
    print(f"  counties: {s['counties_in']}/{s['counties_total']}   rows: {s['rows']}")
    print(f"  live two-party: D {s['dem']:,} ({100*s['dem']/tot:.1f}%)   "
          f"R {s['rep']:,} ({100*s['rep']/tot:.1f}%)   "
          f"winner: {'D' if s['dem'] > s['rep'] else 'R'}")
