"""
rollup.py  —  Phase 3 live county rollup
Election Forecast Dashboard

Reads results_live + the 2020 baseline and produces per-county figures used by
the County Breakdown table (Panel 7), the Shift bar chart (Panel 8), and the
Watch List (Panel 9):

  - live Dem/Rep/total votes
  - how many of the county's precincts have reported (vs its 2020 precinct count)
  - the county's two-party shift vs 2020
  - an estimate of votes still outstanding (for the watch list)
"""

from __future__ import annotations

import sqlite3

from shift_calculator import two_party_share


def baseline_county(conn, state_abbr, race_type, baseline_year):
    """Per-county 2020 baseline: dem2, rep2, precinct count."""
    rows = conn.execute(
        """SELECT p.county,
                  SUM(CASE WHEN rh.party='DEM' THEN rh.votes ELSE 0 END),
                  SUM(CASE WHEN rh.party='REP' THEN rh.votes ELSE 0 END),
                  COUNT(DISTINCT p.id)
           FROM results_historical rh JOIN precincts p ON rh.precinct_id=p.id
           WHERE p.state_abbr=? AND rh.race_type=? AND rh.election_year=?
           GROUP BY p.county""",
        (state_abbr, race_type, baseline_year)).fetchall()
    return {c: {"dem": d or 0, "rep": r or 0, "precincts": n or 0} for c, d, r, n in rows}


def live_county(conn, state_abbr, race_type):
    """Per-county live: dem, rep, total votes, # precincts reported so far."""
    rows = conn.execute(
        """SELECT p.county,
                  SUM(CASE WHEN rl.party='DEM' THEN rl.votes ELSE 0 END),
                  SUM(CASE WHEN rl.party='REP' THEN rl.votes ELSE 0 END),
                  SUM(rl.votes),
                  COUNT(DISTINCT rl.precinct_id)
           FROM results_live rl JOIN precincts p ON rl.precinct_id=p.id
           WHERE p.state_abbr=? AND rl.race_type=?
           GROUP BY p.county""",
        (state_abbr, race_type)).fetchall()
    return {c: {"dem": d or 0, "rep": r or 0, "total": t or 0, "reported": n or 0}
            for c, d, r, t, n in rows}


def county_rollups(conn, state_abbr, race_type, baseline_year=2020):
    """
    Combine baseline + live into one list of per-county dicts. Counties with no
    live votes yet still appear (so the table is complete and the watch list can
    flag fully-outstanding counties).
    """
    base = baseline_county(conn, state_abbr, race_type, baseline_year)
    live = live_county(conn, state_abbr, race_type)

    out = []
    for county, b in base.items():
        lv = live.get(county, {"dem": 0, "rep": 0, "total": 0, "reported": 0})
        base_share = two_party_share(b["dem"], b["rep"])
        live_share = two_party_share(lv["dem"], lv["rep"])
        shift = (live_share - base_share) if (live_share is not None and base_share is not None) else None
        pct_reporting = (100.0 * lv["reported"] / b["precincts"]) if b["precincts"] else 0.0
        base_total2 = b["dem"] + b["rep"]
        est_remaining = max(0.0, base_total2 * (1.0 - pct_reporting / 100.0))
        # "scale the current count up to 100%" estimate of THIS election's turnout
        # (the TV-network method), cross-checkable against the 2020 baseline total.
        live2 = lv["dem"] + lv["rep"]
        est_total2 = (live2 / (pct_reporting / 100.0)) if pct_reporting > 0 else 0.0
        out.append({
            "county": county,
            "precincts_total": b["precincts"],
            "precincts_reported": lv["reported"],
            "pct_reporting": pct_reporting,
            "live_dem": lv["dem"], "live_rep": lv["rep"], "live_total": lv["total"],
            "dem_share_2020": base_share,        # the 2020 benchmark share
            "dem_share_live": live_share,
            "shift": shift,                       # live share vs benchmark (+ = above)
            "est_votes_remaining": est_remaining,             # baseline-based
            "est_total_2pty": est_total2,                     # extrapolated turnout
            "turnout_vs_2020": (est_total2 / base_total2) if base_total2 else None,
            "pending_extrapolated": max(0.0, est_total2 - live2),
            "margin_2020": (b["dem"] - b["rep"]),
        })
    return out


def watch_list(rollups, top_n=8):
    """
    Counties with the most estimated votes outstanding AND a close 2020 margin —
    highest-impact counties still to come (Panel 9). 'Closeness' boosts ranking.
    """
    def impact(c):
        base_total2 = abs(c["margin_2020"]) + 1
        closeness = 1.0 / (1.0 + abs(c["margin_2020"]) / 50000.0)  # closer -> ~1
        return c["est_votes_remaining"] * (0.5 + closeness)
    ranked = sorted(rollups, key=impact, reverse=True)
    return ranked[:top_n]


def mode_breakdown(conn, state_abbr, race_type, county=None):
    """Per ballot-mode (election_day / early / mail / military / all) live tally:
    dem, rep, total, and two-party Dem share. Powers the 'select mail / military
    to see its status' view (statewide if county is None, else for one county)."""
    q = """SELECT rl.mode,
                  SUM(CASE WHEN rl.party='DEM' THEN rl.votes ELSE 0 END),
                  SUM(CASE WHEN rl.party='REP' THEN rl.votes ELSE 0 END),
                  SUM(rl.votes)
           FROM results_live rl JOIN precincts p ON rl.precinct_id = p.id
           WHERE p.state_abbr=? AND rl.race_type=?"""
    args = [state_abbr, race_type]
    if county:
        q += " AND p.county=?"
        args.append(county)
    q += " GROUP BY rl.mode"
    out = []
    for mode, d, r, t in conn.execute(q, args):
        out.append({"mode": mode, "dem": d or 0, "rep": r or 0, "total": t or 0,
                    "dem_share_2pty": two_party_share(d or 0, r or 0)})
    # stable, human order
    order = {"election_day": 0, "early": 1, "mail": 2, "military": 3, "all": 4}
    out.sort(key=lambda m: order.get(m["mode"], 9))
    return out
