"""District results — GA & NC State House / State Senate, 2024 + 2026.

Builds the static data behind the app's "Districts" tab:
    ui/public/districts/{ST}.json                    one row per district (both years)
    ui/public/districts/{ST}/{house|senate}-{N}.json  detail: counties, vote method, precincts

Sources (all official, public, no login):
  GA  Enhanced Voting API (same system ga_live_feed.py uses)
        county list   results.sos.ga.gov/results/public/api/elections/Georgia/{EID}/data
        county data   .../api/elections/{county-slug}/{EID}/data        (contest x vote method)
        precincts     .../api/elections/{county-slug}/{EID}/data/ballot-item/{itemId}
      Precinct rows carry totals only; the vote-method split is county x contest.
  NC  NCSBE bulk files on S3
        2026  ENRS/2026_11_03/results_pct_20261103.zip   (early/mail/provisional are
              county-wide pseudo-precincts in many counties -> see _allocate)
        2024  ENRS/2024_11_05/results_precinct_sort/STATEWIDE_PRECINCT_SORT.txt
              (every vote sorted to the voter's home precinct -> exact)
      When NCSBE posts the 2026 precinct-sorted file (after the state canvass) this
      script uses it automatically and the "estimated" flag goes away.

"Top of ticket" = US Senate (2026) / President (2024) votes cast in the same precincts.
Edge = legislative two-party margin minus top-of-ticket margin in the same district:
positive = the Democratic legislative candidate ran AHEAD of the top of the ticket.

Usage:  py ingestor/district_results.py [GA|NC|ALL]
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import re
import sys
import time
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "districts"
OUT = ROOT / "ui" / "public" / "districts"
UA = {"User-Agent": "Mozilla/5.0 (election-forecast district builder)"}

GA_API = "https://results.sos.ga.gov/results/public/api/elections"
GA_EIDS = {2026: "11032026GeneralAndSpecialElection", 2024: "2024NovGen"}
NC_S3 = "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS"
NC_FILES = {
    2026: ("2026_11_03", "20261103"),
    2024: ("2024_11_05", "20241105"),
}
TOP_LABEL = {2026: "US Senate", 2024: "President"}
METHODS = ["Election Day", "Early", "Mail", "Provisional"]


# --------------------------------------------------------------------------- helpers
def _get(url: str, tries: int = 4):
    for i in range(tries):
        try:
            r = httpx.get(url, headers=UA, timeout=60)
            if r.status_code == 200:
                return r
            if r.status_code in (204, 404):
                return None
        except httpx.HTTPError:
            pass
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"failed: {url}")


def _txt(v):
    if isinstance(v, list):
        return (v[0] or {}).get("text", "") if v else ""
    return v or ""


def _party(p: str) -> str:
    p = (p or "").upper()
    if p.startswith("DEM"):
        return "D"
    if p.startswith("REP"):
        return "R"
    return "O"


def _margin(d, r):
    return round((d - r) / (d + r), 4) if (d + r) else None


# Record = one candidate's votes in one precinct-unit for one contest.
#   unit  = (county, precinct, real)  real=False for county-wide buckets
#   kind  = "top" | "house" | "senate"
#   cand  = (name, party, incumbent)
#   by    = {"all": n} or {"Election Day": n, "Early": n, ...}


# --------------------------------------------------------------------------- GA
GA_CONTEST = [
    # Gwinnett appends a Spanish translation: "State Senate - District 7/ Senador …"
    (re.compile(r"^US Senate\b(?!.*Special)"), "top"),
    (re.compile(r"^President of the US"), "top"),
    (re.compile(r"^State House of Representatives - District (\d+)\b"), "house"),
    (re.compile(r"^State Senate - District (\d+)\b"), "senate"),
]
GA_METHOD = {"Election Day": "Election Day", "Advance Voting": "Early",
             "Absentee by Mail": "Mail", "Provisional": "Provisional"}


def _ga_cand(opt):
    raw = _txt(opt.get("name"))
    inc = "(I)" in raw
    name = re.sub(r"\s*\((?:I|Rep|Dem|Lib|Grn|Ind|NP)\)", "", raw).strip()
    party = _party(_txt((opt.get("party") or {}).get("abbreviation")) or
                   (re.search(r"\((Rep|Dem)\)", raw) or [None, ""])[1])
    if opt.get("isWriteIn"):
        party = "O"
        name = name or "Write-in"
    return name, party, inc


def _ga_county(slug: str, eid: str):
    """All needed contests for one county -> (precinct rows, county-method rows)."""
    r = _get(f"{GA_API}/{slug}/{eid}/data")
    if r is None:
        return [], []
    d = r.json()
    county = re.sub(r"-county-ga$", "", slug).replace("-", " ").upper()
    prec_rows, meth_rows = [], []
    for item in d.get("ballotItems") or []:
        title = _txt(item.get("name")).strip()
        kind = dist = None
        for rx, k in GA_CONTEST:
            m = rx.match(title)
            if m:
                kind, dist = k, (int(m.group(1)) if m.groups() else 0)
                break
        if not kind:
            continue
        for opt in item["summaryResults"]["ballotOptions"]:
            cand = _ga_cand(opt)
            for g in opt.get("groupResults") or []:
                meth = GA_METHOD.get(_txt(g.get("groupName")))
                if meth and g.get("voteCount"):
                    meth_rows.append((county, kind, dist, cand, meth, int(g["voteCount"])))
        br = _get(f"{GA_API}/{slug}/{eid}/data/ballot-item/{item['id']}")
        if br is None:
            continue
        for p in br.json()["ballotItemWithBreakdown"].get("breakdownResults") or []:
            pname = _txt(p["precinct"].get("name")).strip()
            for opt in p.get("ballotOptions") or []:
                v = int(opt.get("voteCount") or 0)
                if v:
                    prec_rows.append((county, pname, True, kind, dist, _ga_cand(opt), {"all": v}))
    return prec_rows, meth_rows


def load_ga(year: int):
    cache = RAW / f"ga_{year}.json.gz"
    if cache.exists():
        c = json.loads(gzip.decompress(cache.read_bytes()))
        return ([(a, b, c_, k, d_, tuple(cd), by) for a, b, c_, k, d_, cd, by in c["prec"]],
                [(a, k, d_, tuple(cd), m, v) for a, k, d_, cd, m, v in c["meth"]])
    eid = GA_EIDS[year]
    st = _get(f"{GA_API}/Georgia/{eid}/data").json()
    slugs = [c["shortName"] for c in st["jurisdiction"]["childLocalities"]]
    print(f"GA {year}: fetching {len(slugs)} counties …", flush=True)
    prec, meth = [], []
    with ThreadPoolExecutor(8) as ex:
        for i, (p, m) in enumerate(ex.map(lambda s: _ga_county(s, eid), slugs), 1):
            prec += p
            meth += m
            if i % 20 == 0:
                print(f"  {i}/{len(slugs)} counties", flush=True)
    RAW.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(gzip.compress(json.dumps({"prec": prec, "meth": meth}).encode()))
    return prec, meth


# --------------------------------------------------------------------------- NC
NC_CONTEST = [
    (re.compile(r"^US SENATE$"), "top"),
    (re.compile(r"^US PRESIDENT$"), "top"),
    (re.compile(r"^NC HOUSE OF REPRESENTATIVES DISTRICT (\d+)$"), "house"),
    (re.compile(r"^NC STATE SENATE DISTRICT (\d+)$"), "senate"),
]


def _nc_kind(title):
    for rx, k in NC_CONTEST:
        m = rx.match(title.strip())
        if m:
            return k, (int(m.group(1)) if m.groups() else 0)
    return None, None


def _nc_method(desc: str):
    d = desc.lower()
    if "election day" in d:
        return "Election Day"
    if "early" in d or "one stop" in d:
        return "Early"
    if "mail" in d or "absentee" in d:
        return "Mail"
    if "provisional" in d:
        return "Provisional"
    return None  # transfer etc. — ignored (tiny)


def _nc_sorted(year: int):
    folder, ymd = NC_FILES[year]
    path = RAW / f"nc_{year}_sort.txt"
    if not path.exists():
        r = _get(f"{NC_S3}/{folder}/results_precinct_sort/STATEWIDE_PRECINCT_SORT.txt")
        if r is None:
            return None
        path.write_bytes(r.content)
        print(f"NC {year}: downloaded precinct-sorted file")
    agg = defaultdict(int)
    with path.open(encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            kind, dist = _nc_kind(r["contest_title"])
            if not kind:
                continue
            if r["candidate_name"].strip().upper() in ("UNDER VOTE", "OVER VOTE", "UNDERVOTES", "OVERVOTES"):
                continue
            meth = _nc_method(r["voting_method_rslt_desc"])
            v = int(r["vote_ct"] or 0)
            if meth and v:
                cand = (r["candidate_name"].strip(), _party(r["candidate_party_lbl"]), False)
                agg[(r["county"].strip(), r["precinct_code"].strip(), kind, dist, cand, meth)] += v
    rows = defaultdict(dict)
    for (cty, pct, kind, dist, cand, meth), v in agg.items():
        rows[(cty, pct, True, kind, dist, cand)][meth] = v
    return [(*k[:5], k[5], by) for k, by in rows.items()]


def _nc_pct(year: int):
    folder, ymd = NC_FILES[year]
    path = RAW / f"nc_{year}_pct.txt"
    if not path.exists():
        r = _get(f"{NC_S3}/{folder}/results_pct_{ymd}.zip")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        path.write_bytes(z.read(z.namelist()[0]))
    out = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            kind, dist = _nc_kind(r["Contest Name"])
            if not kind:
                continue
            by = {"Election Day": int(r["Election Day"] or 0), "Early": int(r["Early Voting"] or 0),
                  "Mail": int(r["Absentee by Mail"] or 0), "Provisional": int(r["Provisional"] or 0)}
            if not sum(by.values()):
                continue
            cand = (r["Choice"].strip(), _party(r["Choice Party"]), False)
            out.append((r["County"].strip(), r["Precinct"].strip(), r["Real Precinct"] == "Y",
                        kind, dist, cand, by))
    return out


def load_nc(year: int):
    rows = _nc_sorted(year)
    if rows is not None:
        return rows, True
    return _nc_pct(year), False


# --------------------------------------------------------------------------- build
def _total(by):
    return sum(by.values())


def build(state: str, year: int, prec, exact_sorted=True):
    """-> {(chamber, dist): district-dict} for one year."""
    # unit -> chamber -> dist -> leg votes total ; unit -> top D/R ; precinct meta
    leg = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    top = defaultdict(lambda: {"D": 0, "R": 0, "by": defaultdict(lambda: [0, 0])})
    cands = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # (ch,d)->cand->method->v
    unit_leg = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))       # (ch,d)->unit->[D,R,O]
    unit_leg_by = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0])))
    for county, pct, real, kind, dist, cand, by in prec:
        unit = (county, pct, real)
        n = _total(by)
        if kind == "top":
            if cand[1] in "DR":
                top[unit][cand[1]] += n
                for m, v in by.items():
                    top[unit]["by"][m][0 if cand[1] == "D" else 1] += v
            continue
        key = (kind, dist)
        leg[unit][kind][dist] += n
        for m, v in by.items():
            cands[key][cand][m] += v
            if cand[1] in "DR":
                unit_leg_by[key][unit][m][0 if cand[1] == "D" else 1] += v
        unit_leg[key][unit]["DRO".index(cand[1])] += n

    # Allocate top-of-ticket votes in each unit to the district(s) voting there.
    # One district -> all of it. Several (split precincts, NC county-wide early/mail
    # buckets) -> raked so each district's slice follows its own real-precinct
    # Senate lean in that county, and the slices add back to the unit exactly.
    real_lean = defaultdict(lambda: [0, 0])  # (county, chamber, dist) -> top D,R in real single-district precincts
    for unit, chambers in leg.items():
        if unit[2] and unit in top:
            for ch, ds in chambers.items():
                if len(ds) == 1:
                    (d,) = ds
                    real_lean[(unit[0], ch, d)][0] += top[unit]["D"]
                    real_lean[(unit[0], ch, d)][1] += top[unit]["R"]
    top_alloc = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))  # (ch,d)->unit->[D,R]
    top_alloc_by = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))  # (ch,d)->method->[D,R]
    estimated = defaultdict(float)  # (ch,d) -> votes that were allocated by estimate
    for unit, t in top.items():
        for ch, ds in leg.get(unit, {}).items():
            tot = sum(ds.values())
            if not tot:
                continue
            if len(ds) == 1:
                (d,) = ds
                shares = {d: (1.0, 1.0)}
            else:
                p = {}
                for d in ds:
                    ld, lr = real_lean.get((unit[0], ch, d), (0, 0))
                    p[d] = ld / (ld + lr) if (ld + lr) else 0.5
                wd = {d: ds[d] * p[d] for d in ds}
                wr = {d: ds[d] * (1 - p[d]) for d in ds}
                sd, sr = sum(wd.values()) or 1, sum(wr.values()) or 1
                shares = {d: (wd[d] / sd, wr[d] / sr) for d in ds}
                if not unit[2]:
                    for d in ds:
                        estimated[(ch, d)] += (t["D"] + t["R"]) * ds[d] / tot
            for d, (fd, fr) in shares.items():
                top_alloc[(ch, d)][unit][0] += t["D"] * fd
                top_alloc[(ch, d)][unit][1] += t["R"] * fr
                for m, (vd, vr) in t["by"].items():
                    top_alloc_by[(ch, d)][m][0] += vd * fd
                    top_alloc_by[(ch, d)][m][1] += vr * fr

    out = {}
    for key, cs in cands.items():
        ch, dist = key
        clist = []
        for (name, party, inc), by in cs.items():
            clist.append({"name": name, "party": party, "inc": inc, "votes": sum(by.values())})
        clist.sort(key=lambda c: -c["votes"])
        if clist:
            clist[0]["win"] = True
        D = sum(c["votes"] for c in clist if c["party"] == "D")
        R = sum(c["votes"] for c in clist if c["party"] == "R")
        O = sum(c["votes"] for c in clist if c["party"] == "O")
        tD = sum(v[0] for v in top_alloc[key].values())
        tR = sum(v[1] for v in top_alloc[key].values())
        contested = D > 0 and R > 0
        m, tm = _margin(D, R) if contested else None, _margin(tD, tR)
        # counties
        cty = defaultdict(lambda: [0, 0, 0, 0.0, 0.0])
        for unit, (d_, r_, o_) in unit_leg[key].items():
            cty[unit[0]][0] += d_; cty[unit[0]][1] += r_; cty[unit[0]][2] += o_
        for unit, (d_, r_) in top_alloc[key].items():
            cty[unit[0]][3] += d_; cty[unit[0]][4] += r_
        counties = [{"county": c.title(), "d": v[0], "r": v[1], "o": v[2],
                     "td": round(v[3]), "tr": round(v[4])} for c, v in cty.items()]
        counties.sort(key=lambda c: -(c["d"] + c["r"] + c["o"]))
        # vote method (legislative race)
        meth = defaultdict(lambda: [0, 0])
        for unit, mm in unit_leg_by[key].items():
            for mname, (d_, r_) in mm.items():
                meth[mname][0] += d_; meth[mname][1] += r_
        methods = [{"method": mname, "d": meth[mname][0], "r": meth[mname][1],
                    "td": round(top_alloc_by[key][mname][0]) if mname in top_alloc_by[key] else None,
                    "tr": round(top_alloc_by[key][mname][1]) if mname in top_alloc_by[key] else None}
                   for mname in METHODS if mname in meth]
        # precincts (real only)
        precincts = []
        for unit, (d_, r_, o_) in unit_leg[key].items():
            if not unit[2]:
                continue
            ta = top_alloc[key].get(unit, (0, 0))
            precincts.append({"county": unit[0].title(), "precinct": unit[1], "d": d_, "r": r_, "o": o_,
                              "td": round(ta[0]), "tr": round(ta[1])})
        precincts.sort(key=lambda p: (p["county"], p["precinct"]))
        est = estimated.get(key, 0)
        out[key] = {
            "cands": clist, "d": D, "r": R, "o": O, "total": D + R + O,
            "contested": contested, "margin": m,
            "top": {"label": TOP_LABEL[year], "d": round(tD), "r": round(tR), "margin": tm},
            "edge": round(m - tm, 4) if (m is not None and tm is not None) else None,
            "est_share": round(est / (tD + tR), 3) if (tD + tR) and not exact_sorted else 0,
            "counties": counties, "methods": methods, "precincts": precincts,
        }
    return out


def ga_method_override(dist_data, meth_rows):
    """GA precinct rows have totals only; the method split comes from county x contest."""
    agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for county, kind, dist, cand, meth, v in meth_rows:
        if kind != "top" and cand[1] in "DR":
            agg[(kind, dist)][meth][0 if cand[1] == "D" else 1] += v
    for key, dd in dist_data.items():
        if key in agg:
            dd["methods"] = [{"method": m, "d": agg[key][m][0], "r": agg[key][m][1], "td": None, "tr": None}
                             for m in METHODS if m in agg[key]]


def write_state(state: str):
    years = {}
    notes = []
    for year in (2024, 2026):
        if state == "GA":
            prec, meth = load_ga(year)
            dd = build(state, year, prec)
            ga_method_override(dd, meth)
        else:
            prec, exact = load_nc(year)
            dd = build(state, year, prec, exact_sorted=exact)
            if not exact:
                notes.append(f"NC {year}: early/mail votes in multi-district counties are reported "
                             "county-wide; the top-of-ticket split inside those districts is estimated "
                             "until NCSBE posts its precinct-sorted file.")
        years[year] = dd
        print(f"{state} {year}: {len(dd)} districts")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / state).mkdir(exist_ok=True)
    rows = []
    for key in sorted(set(years[2026]) | set(years[2024])):
        ch, dist = key
        row = {"chamber": ch, "district": dist}
        for y in (2024, 2026):
            dd = years[y].get(key)
            if dd:
                row[str(y)] = {k: dd[k] for k in ("cands", "d", "r", "o", "total", "contested",
                                                  "margin", "top", "edge", "est_share")}
                row[str(y)]["counties"] = [c["county"] for c in dd["counties"]]
        a, b = row.get("2026"), row.get("2024")
        if a and b:
            row["swing"] = round(a["margin"] - b["margin"], 4) if (a["margin"] is not None and b["margin"] is not None) else None
            row["top_swing"] = round(a["top"]["margin"] - b["top"]["margin"], 4) if (a["top"]["margin"] is not None and b["top"]["margin"] is not None) else None
        rows.append(row)
        detail = {"state": state, "chamber": ch, "district": dist,
                  **{str(y): years[y][key] for y in (2024, 2026) if key in years[y]}}
        (OUT / state / f"{ch}-{dist}.json").write_text(json.dumps(detail, separators=(",", ":")))
    meta = {"state": state, "built": date.today().isoformat(), "notes": notes,
            "sources": ("Georgia Secretary of State results (results.sos.ga.gov), certified"
                        if state == "GA" else "NC State Board of Elections results files (dl.ncsbe.gov)"),
            "districts": rows}
    (OUT / f"{state}.json").write_text(json.dumps(meta, separators=(",", ":")))
    print(f"wrote ui/public/districts/{state}.json + {len(rows)} detail files")


if __name__ == "__main__":
    which = (sys.argv[1] if len(sys.argv) > 1 else "ALL").upper()
    for st in (["GA", "NC"] if which == "ALL" else [which]):
        write_state(st)
