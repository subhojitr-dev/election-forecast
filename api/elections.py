"""
elections.py — the election "ballot manifest".

Single source of truth for WHICH contests are on the ballot for each election, in
which states, and which historical baseline each compares against. The UI race
toggle + swing-state strip read from here, so on a real election night only the
races actually happening show up:
  - Nov 2026 = Senate Class-2 seats only (NO President)
  - Nov 2028 = President + Senate Class-3 seats

Senate seats rotate on a fixed 6-year "class" schedule, so the line-ups are known
years ahead:
  - 2026 -> Class 2 (last contested 2020): of our 8 -> GA / MI / NC / TX
  - 2028 -> Class 3 (last contested 2022): GA / AZ / NV / PA / WI / NC  + President
Off-cycle SPECIAL elections can add a seat with little notice — add them here when
announced (that's the only part not knowable far ahead).
"""
from __future__ import annotations

ALL8 = ["GA", "PA", "AZ", "NV", "WI", "MI", "NC", "TX"]
RACE_LABEL = {"president": "President", "senate": "Senate", "senate_special": "GA Special"}
RACE_ORDER = ["president", "senate", "senate_special"]

ELECTIONS = {
    "demo": {
        "label": "Demo · historical sandbox (all races)",
        "date": "2020-11-03",
        "races": {"president": ALL8, "senate": ALL8, "senate_special": ["GA"]},
        "president_baseline": 2020,
        "senate_baseline": {"GA": 2021, "NC": 2020, "AZ": 2024, "MI": 2024,
                            "PA": 2024, "NV": 2024, "WI": 2024, "TX": 2024},
        "senate_special_baseline": {"GA": 2021},
    },
    # --- past elections, for replay/testing against real results ---
    "pres2024": {
        "label": "Test · 2024 President (historical)",
        "date": "2024-11-05",
        "races": {"president": ALL8},
        "president_baseline": 2024,
    },
    "sen2020": {
        "label": "Test · 2020 Senate (historical)",
        "date": "2020-11-03",
        "races": {"senate": ["GA", "AZ", "MI", "NC", "TX"]},
        "senate_baseline": {s: 2020 for s in ["GA", "AZ", "MI", "NC", "TX"]},
    },
    "sen2024": {
        "label": "Test · 2024 Senate (historical)",
        "date": "2024-11-05",
        "races": {"senate": ["AZ", "MI", "PA", "NV", "WI", "TX"]},
        "senate_baseline": {s: 2024 for s in ["AZ", "MI", "PA", "NV", "WI", "TX"]},
    },
    "sen2018": {
        "label": "Test · 2018 Senate (historical)",
        "date": "2018-11-06",
        "races": {"senate": ["AZ", "MI", "TX", "NV", "PA", "WI"]},
        "senate_baseline": {s: 2018 for s in ["AZ", "MI", "TX", "NV", "PA", "WI"]},
    },
    # --- real upcoming elections (the dress rehearsals) ---
    "general2026": {
        "label": "General · Nov 3, 2026 (midterm)",
        "date": "2026-11-03",
        # No presidential race in 2026. Senate = Class-2 seats only.
        "races": {"senate": ["GA", "MI", "NC", "TX", "SC"]},
        # Each seat's baseline = the last time IT was contested (2020; GA = 2021 runoff).
        "senate_baseline": {"GA": 2021, "MI": 2020, "NC": 2020, "TX": 2020, "SC": 2020},
        # Real 2026 nominees (primaries decided Mar–Jun 2026; MI primary is Aug 4).
        "candidates": {"senate": {
            "GA": {"dem": "JON OSSOFF", "rep": "MIKE COLLINS"},
            "NC": {"dem": "ROY COOPER", "rep": "MICHAEL WHATLEY"},
            "TX": {"dem": "JAMES TALARICO", "rep": "KEN PAXTON"},
            "MI": {"dem": "DEM NOMINEE — TBD AUG 4", "rep": "GOP NOMINEE — TBD AUG 4"},
            # SC primary was 2026-06-12 (enr-scvotes.org, electionId 126294):
            # Graham (R, incumbent) 56.78%/264,091 beat Mark Lynch; Andrews (D) 61.53%/226,075.
            "SC": {"dem": "ANNIE ANDREWS", "rep": "LINDSEY GRAHAM"},
        }},
    },
    "general2028": {
        "label": "General · Nov 7, 2028 (needs 2022 Senate data)",
        "date": "2028-11-07",
        "races": {"president": ALL8, "senate": ["GA", "AZ", "NV", "PA", "WI", "NC"]},
        "president_baseline": 2024,
        # Class-3 seats last contested 2022 -> need the 2022 Senate file loaded (TODO).
        "senate_baseline": {s: 2022 for s in ["GA", "AZ", "NV", "PA", "WI", "NC"]},
    },
}
DEFAULT_ELECTION = "demo"


def get(eid):
    return ELECTIONS.get(eid, ELECTIONS[DEFAULT_ELECTION])


def races_for(eid):
    """Race ids actually on the ballot for this election (non-empty state lists)."""
    e = get(eid)
    return [r for r in RACE_ORDER if e["races"].get(r)]


def states_for(eid, race):
    return get(eid)["races"].get(race, [])


def baseline_year(eid, state, race):
    e = get(eid)
    if race == "president":
        return e.get("president_baseline", 2020)
    if race == "senate":
        return e.get("senate_baseline", {}).get(state, 2020)
    if race == "senate_special":
        return e.get("senate_special_baseline", {}).get(state, 2021)
    return 2020


def candidates(eid, race, state):
    """Real nominee labels for this seat, if the manifest sets them (else {}).
    Used to relabel the replayed baseline's candidates (e.g. 2026 GA Senate shows
    Ossoff vs Collins over the 2020/2021 vote geography)."""
    return get(eid).get("candidates", {}).get(race, {}).get(state, {})


def listing():
    return [{"id": k, "label": v["label"], "date": v["date"],
             "races": [{"id": r, "label": RACE_LABEL[r]} for r in races_for(k)]}
            for k, v in ELECTIONS.items()]
