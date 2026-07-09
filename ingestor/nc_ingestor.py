"""
nc_ingestor.py — North Carolina live-results ingestor (live-readiness)
Election Forecast Dashboard

North Carolina publishes its Election Night Reporting results as an OPEN,
tab-delimited file on S3 (no CloudFront / no 403). The file is statewide,
precinct-level, and already split BY VOTING METHOD — exactly what we need.

  Source: https://dl.ncsbe.gov/ENRS/{YYYY_MM_DD}/results_pct_{YYYYMMDD}.zip
  Columns: County | Election Date | Precinct | Contest Group ID | Contest Type |
           Contest Name | Choice | Choice Party | Vote For |
           Election Day | Early Voting | Absentee by Mail | Provisional |
           Total Votes | Real Precinct

We aggregate to COUNTY level (the live v1 approach — county totals give the same
statewide winner / win-prob / convergence) and keep the mode breakdown.

CLI:
  python ingestor/nc_ingestor.py 2024-11-05 "US PRESIDENT"
  python ingestor/nc_ingestor.py 2026-03-03 "US SENATE"
"""

from __future__ import annotations

import io
import zipfile
from collections import defaultdict

import httpx

S3 = "https://s3.amazonaws.com/dl.ncsbe.gov"
# NCSBE voting-method columns -> our mode buckets (results_live.mode).
# NC renamed early voting: "One Stop" (2020 and earlier) -> "Early Voting" (2024+).
# Include both; only the one present in a given file contributes.
MODE_COLS = {"Election Day": "election_day",
             "One Stop": "early", "Early Voting": "early",
             "Absentee by Mail": "mail", "Provisional": "provisional"}
PARTY_MAP = {"DEM": "DEM", "REP": "REP", "LIB": "LIB", "GRE": "GRE",
             "CST": "OTH", "NLB": "OTH", "GRN": "GRE", "UNA": "OTH"}


def results_url(date_iso: str) -> str:
    """date_iso = 'YYYY-MM-DD' -> the NCSBE results_pct zip URL."""
    y, m, d = date_iso.split("-")
    return f"{S3}/ENRS/{y}_{m}_{d}/results_pct_{y}{m}{d}.zip"


def fetch_results_pct(date_iso: str, timeout: float = 120) -> str:
    """Download + unzip the results_pct file, return its raw tab-delimited text."""
    r = httpx.get(results_url(date_iso), timeout=timeout)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    return z.read(z.namelist()[0]).decode("latin-1")


def _party(p) -> str:
    return PARTY_MAP.get((p or "").strip().upper(), "OTH")


def parse_county(raw: str, contest_filter: str):
    """
    Aggregate the file to COUNTY level for contests whose name contains
    `contest_filter` (case-insensitive substring, e.g. 'US SENATE').
    Returns list of dicts: {county, candidate, party, votes, modes{mode:votes}}.
    """
    lines = raw.split("\n")
    idx = {h.strip(): i for i, h in enumerate(lines[0].split("\t"))}
    ci, coi, choi, pai, toti = (idx["Contest Name"], idx["County"], idx["Choice"],
                                idx["Choice Party"], idx["Total Votes"])
    cf = contest_filter.upper()
    agg: dict = defaultdict(lambda: {"party": "OTH", "votes": 0,
                                     "modes": defaultdict(int)})
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) <= toti or cf not in f[ci].strip().upper():
            continue
        key = (f[coi].strip(), f[choi].strip())
        rec = agg[key]
        rec["party"] = _party(f[pai])
        try:
            rec["votes"] += int(f[toti] or 0)
        except ValueError:
            pass
        for col, mode in MODE_COLS.items():
            try:
                rec["modes"][mode] += int(f[idx[col]] or 0)
            except (ValueError, KeyError):
                pass
    return [{"county": c, "candidate": cand, "party": r["party"],
             "votes": r["votes"], "modes": dict(r["modes"])}
            for (c, cand), r in agg.items()]


def two_party(rows):
    d = sum(r["votes"] for r in rows if r["party"] == "DEM")
    r = sum(r["votes"] for r in rows if r["party"] == "REP")
    return d, r


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else "2024-11-05"
    contest = sys.argv[2] if len(sys.argv) > 2 else "US PRESIDENT"
    print(f"NC ingestor — {date} · contest ~ {contest!r}")
    print(f"  URL: {results_url(date)}")
    raw = fetch_results_pct(date)
    rows = parse_county(raw, contest)
    if not rows:
        print("  no rows matched — check the contest name."); sys.exit(1)
    counties = sorted(set(r["county"] for r in rows))
    cands = sorted(set(r["candidate"] for r in rows))
    d, r = two_party(rows)
    tot = d + r
    print(f"  counties: {len(counties)}   candidates: {len(cands)}")
    print(f"  statewide two-party:  D {d:,} ({100*d/tot:.1f}%)   "
          f"R {r:,} ({100*r/tot:.1f}%)   winner: {'D' if d > r else 'R'}")
    # mode split (statewide)
    modes = defaultdict(int)
    for row in rows:
        for m, v in row["modes"].items():
            modes[m] += v
    print("  votes by mode:", {m: f"{v:,}" for m, v in sorted(modes.items())})
    # biggest counties
    ctot = defaultdict(int)
    for row in rows:
        ctot[row["county"]] += row["votes"]
    print("  biggest counties:",
          [f"{c} {ctot[c]:,}" for c in sorted(ctot, key=ctot.get, reverse=True)[:4]])
