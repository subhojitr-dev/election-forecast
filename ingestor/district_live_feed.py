"""Election-night feed for the Districts tab (GA & NC State House / State Senate).

Pulls precinct-level legislative results from the same official sources as
district_results.py and stores ONE JSON snapshot per state in the
`district_live` table. The API serves it at /api/districts/live/{ST}; the browser
does the projection (ui/src/districts/model.js) against the static 2026 baseline.

Payload:
  {state, election, as_of, chambers: {house|senate: {"<dist>": {
      cands: [{name, party, votes}],
      units: [[county, precinct, method, d, r, o, done], ...]}}}}
  method = "all" (GA: precinct totals) or Election Day / Early / Mail / Provisional (NC)
  done   = 1 when that unit is fully counted:
           GA → the county reports this contest fully in (reportingUnits == totalUnits),
                or the precinct's reportingStatus == 3. Status codes are NOT consistent
                across counties (certified 2026: Fulton/Cobb precincts = 3, Fayette = 4),
                so a county like Fayette counts as "partly in" until it finishes —
                cautious, never early. Watch this at the next live GA special election.
           NC → the unit has votes (NC posts a precinct's / bucket's count in one go)

Configure an election (Render → Environment), then the production poller picks it up:
  DISTRICT_LIVE_GA_EID = e.g. 11072028GeneralElection   (from results.sos.ga.gov/results/public/Georgia)
  DISTRICT_LIVE_NC_DATE = e.g. 2028-11-07                (NCSBE ENRS folder date)
  DISTRICT_LIVE_SC_EID = e.g. 127300                     (enr-scvotes.org election id)
  DISTRICT_LIVE_OH = 1                                   (Ohio SoS XML feed; one fixed URL, current election)
                     OH reports by COUNTY only: a unit = county x district, done when the county
                     reports all its precincts (CountStatus Completed).

CLI:
  py ingestor/district_live_feed.py GA <eid>          one poll → DB
  py ingestor/district_live_feed.py NC <yyyy-mm-dd>   one poll → DB
  py ingestor/district_live_feed.py OH                one poll → DB
  py ingestor/district_live_feed.py clear [GA|NC]     remove stored snapshots
"""
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import sys
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import re  # noqa: E402

from district_results import (GA_API, GA_CONTEST, NC_S3, OH_XML, SC_CONTEST, _ga_cand, _get,  # noqa: E402
                              _nc_kind, _party, _sc_party, _txt, parse_oh_xml)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "db", "baseline.db")
GA_DONE_STATUS = 3

SCHEMA = """CREATE TABLE IF NOT EXISTS district_live (
  state TEXT PRIMARY KEY, election TEXT, as_of TEXT, payload TEXT)"""


def _empty():
    return {"house": defaultdict(lambda: {"cands": defaultdict(int), "units": {}}),
            "senate": defaultdict(lambda: {"cands": defaultdict(int), "units": {}})}


def _add(ch, county, precinct, method, cand, votes, done):
    """cand = (name, party, inc)"""
    party = cand[1]
    ch["cands"][(cand[0], party)] += votes
    u = ch["units"].setdefault((county, precinct, method), [0, 0, 0, done])
    u["DRO".index(party)] += votes
    u[3] = u[3] and done


def _finish(state, election, chambers):
    out = {}
    for name, dists in chambers.items():
        out[name] = {}
        for dist, x in dists.items():
            out[name][str(dist)] = {
                "cands": sorted(({"name": n, "party": p, "votes": v} for (n, p), v in x["cands"].items()),
                                key=lambda c: -c["votes"]),
                "units": [[c, p, m, d, r, o, 1 if done else 0] for (c, p, m), (d, r, o, done) in sorted(x["units"].items())],
            }
    return {"state": state, "election": election,
            "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "chambers": out}


# --------------------------------------------------------------------------- GA
def _ga_county(slug, eid):
    r = _get(f"{GA_API}/{slug}/{eid}/data")
    if r is None:
        return []
    county = slug.removesuffix("-county-ga").replace("-", " ").upper()
    rows = []
    for item in r.json().get("ballotItems") or []:
        title = _txt(item.get("name")).strip()
        kind = dist = None
        for rx, k in GA_CONTEST:
            m = rx.match(title)
            if m and k != "top":
                kind, dist = k, int(m.group(1))
        if not kind:
            continue
        rs = item.get("reportingStatus") or {}
        county_done = bool(rs.get("totalUnits")) and rs.get("reportingUnits") == rs.get("totalUnits")
        br = _get(f"{GA_API}/{slug}/{eid}/data/ballot-item/{item['id']}")
        if br is None:
            continue
        for p in br.json()["ballotItemWithBreakdown"].get("breakdownResults") or []:
            done = county_done or p["precinct"].get("reportingStatus") == GA_DONE_STATUS
            pname = _txt(p["precinct"].get("name")).strip()
            for opt in p.get("ballotOptions") or []:
                rows.append((kind, dist, county, pname, _ga_cand(opt), int(opt.get("voteCount") or 0), done))
    return rows


def fetch_ga(eid: str, workers: int = 16):
    st = _get(f"{GA_API}/Georgia/{eid}/data")
    if st is None:
        raise RuntimeError(f"GA election {eid} not found")
    j = st.json()
    slugs = [c["shortName"] for c in j["jurisdiction"]["childLocalities"]]
    chambers = _empty()
    with ThreadPoolExecutor(workers) as ex:
        for rows in ex.map(lambda s: _ga_county(s, eid), slugs):
            for kind, dist, county, pname, cand, v, done in rows:
                _add(chambers[kind][dist], county, pname, "all", cand, v, done)
    return _finish("GA", _txt(j["election"].get("name")) or eid, chambers)


# --------------------------------------------------------------------------- NC
def fetch_nc(day: str):
    y, m, d = day.split("-")
    r = _get(f"{NC_S3}/{y}_{m}_{d}/results_pct_{y}{m}{d}.zip")
    if r is None:
        raise RuntimeError(f"NC results file for {day} not posted yet")
    z = zipfile.ZipFile(io.BytesIO(r.content))
    text = z.read(z.namelist()[0]).decode("utf-8", errors="replace")
    chambers = _empty()
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        kind, dist = _nc_kind(row["Contest Name"])
        if kind not in ("house", "senate"):
            continue
        cand = (row["Choice"].strip(), _party(row["Choice Party"]), False)
        ch = chambers[kind][dist]
        ch["cands"][(cand[0], cand[1])] += 0       # list every candidate even at 0 votes
        for col, meth in (("Election Day", "Election Day"), ("Early Voting", "Early"),
                          ("Absentee by Mail", "Mail"), ("Provisional", "Provisional")):
            v = int(row[col] or 0)
            if v:
                _add(ch, row["County"].strip(), row["Precinct"].strip(), meth, cand, v, True)
    return _finish("NC", f"North Carolina {day}", chambers)


# --------------------------------------------------------------------------- SC
SC_BASE = "https://www.enr-scvotes.org/SC"


def _sc_county(name, eid, ver):
    base = f"{SC_BASE}/{name.replace(' ', '_')}/{eid}/{ver}"
    s, d = _get(f"{base}/json/en/summary.json"), _get(f"{base}/json/details.json")
    if s is None or d is None:
        return []
    by_k = {c["K"]: c for c in d.json()["Contests"]}
    rows = []
    for c in s.json():
        title = " ".join(c["C"].split())
        kind = dist = None
        for rx, k in SC_CONTEST:
            m = rx.match(title)
            if m and k != "top":
                kind, dist = k, int(m.group(1))
        det = by_k.get(c["K"])
        if not kind or not det:
            continue
        cands = [(re.sub(r"^\S+\s+", "", n).strip() if not n.lower().startswith("write") else "Write-in",
                  "O" if n.lower().startswith("write") else _sc_party(p), False)
                 for n, p in zip(c["CH"], c["P"])]
        # Clarity marks nothing per precinct; a precinct with any votes in the contest counts as in.
        for pname, votes in zip(det["P"], det["V"]):
            done = sum(votes) > 0
            for cand, v in zip(cands, votes):
                rows.append((kind, dist, name.upper(), pname.strip(), cand, int(v), done))
    return rows


def fetch_sc(eid: str, workers: int = 4):
    """SC Election Commission (Clarity ENR). ⚠️ As of Nov 2026 its CDN refuses scripted
    requests (403/405) — it was open in July 2026. Re-test before relying on this for a
    live night; if still blocked, SC stays practice-only rather than working around it."""
    v = _get(f"{SC_BASE}/{eid}/current_ver.txt")
    if v is None:
        raise RuntimeError(f"SC election {eid} not reachable")
    ver = v.text.strip()
    es = _get(f"{SC_BASE}/{eid}/{ver}/json/en/electionsettings.json").json()
    ed = es["settings"]["electiondetails"]
    ed = json.loads(ed) if isinstance(ed, str) else ed
    pc = ed["participatingcounties"]
    pc = json.loads(pc) if isinstance(pc, str) else pc
    counties = [x.split("|")[:3] for x in pc]
    chambers = _empty()
    with ThreadPoolExecutor(workers) as ex:
        for rows in ex.map(lambda c: _sc_county(*c), counties):
            for kind, dist, county, pname, cand, v, done in rows:
                _add(chambers[kind][dist], county, pname, "all", cand, v, done)
    return _finish("SC", f"South Carolina {eid}", chambers)


# --------------------------------------------------------------------------- OH
def fetch_oh():
    r = _get(OH_XML)
    if r is None:
        raise RuntimeError("OH results feed not available")
    chambers = _empty()
    for county, kind, dist, cand, v, done in parse_oh_xml(r.text):
        if kind not in ("house", "senate"):
            continue
        ch = chambers[kind][dist]
        ch["cands"][(cand[0], cand[1])] += 0       # list every candidate even at 0 votes
        _add(ch, county, "ALL", "all", cand, v, done)
    m = re.search(r'GeneratedDate="([^"]+)"', r.text[:2000])
    return _finish("OH", f"Ohio results feed {m.group(1) if m else ''}".strip(), chambers)


# --------------------------------------------------------------------------- store
def store(payload, db_path=DB):
    con = sqlite3.connect(db_path)
    try:
        con.execute(SCHEMA)
        con.execute("INSERT OR REPLACE INTO district_live VALUES (?,?,?,?)",
                    (payload["state"], payload["election"], payload["as_of"], json.dumps(payload, separators=(",", ":"))))
        con.commit()
    finally:
        con.close()
    n = sum(len(v) for v in payload["chambers"].values())
    units = sum(len(x["units"]) for v in payload["chambers"].values() for x in v.values())
    return {"state": payload["state"], "districts": n, "units": units, "as_of": payload["as_of"]}


def clear(state=None, db_path=DB):
    con = sqlite3.connect(db_path)
    try:
        con.execute(SCHEMA)
        if state:
            con.execute("DELETE FROM district_live WHERE state=?", (state,))
        else:
            con.execute("DELETE FROM district_live")
        con.commit()
    finally:
        con.close()


def poll_ga():
    return store(fetch_ga(os.environ["DISTRICT_LIVE_GA_EID"]))


def poll_sc():
    return store(fetch_sc(os.environ["DISTRICT_LIVE_SC_EID"]))


def poll_oh():
    return store(fetch_oh())


def poll_nc():
    return store(fetch_nc(os.environ["DISTRICT_LIVE_NC_DATE"]))


if __name__ == "__main__":
    cmd = sys.argv[1].upper() if len(sys.argv) > 1 else ""
    if cmd == "GA":
        print(store(fetch_ga(sys.argv[2])))
    elif cmd == "SC":
        print(store(fetch_sc(sys.argv[2])))
    elif cmd == "NC":
        print(store(fetch_nc(sys.argv[2])))
    elif cmd == "OH":
        print(store(fetch_oh()))
    elif cmd == "CLEAR":
        clear(sys.argv[2].upper() if len(sys.argv) > 2 else None)
        print("cleared")
    else:
        print(__doc__)
