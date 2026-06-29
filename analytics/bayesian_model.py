"""
bayesian_model.py  —  Phase 3 win-probability model
Election Forecast Dashboard

Turns a projected final Democratic vote share into a probability that the
Democrat wins, plus the human-readable confidence tier and lean label.

The model is deliberately simple and explainable (no heavy stats deps — just
the normal distribution via math.erf):

  - We have a POINT ESTIMATE of the final two-party Dem share (from the
    projection in shift_calculator/engine), e.g. 0.503.
  - Our UNCERTAINTY about that estimate is large when few precincts have
    reported and shrinks as more report in.
  - Win probability = P(final Dem share > 0.50) under a Normal(mean, sigma).

How "stay close to the prior early" (the brief) is implemented: the projection
applies the *observed* swing to the not-yet-counted precincts only partially,
scaled by `reporting_weight(pct)` — near 0 when little is in (so the projection
~= the 2020 baseline), near 1 when most is in (full observed swing). That weight
lives here so the whole prior-vs-live blend is in one place.
"""

from __future__ import annotations

import math


def reporting_weight(pct_reporting: float) -> float:
    """
    How much to trust the live/observed swing vs. the 2020 baseline.
    0 at 0% reporting -> ~1 by ~85% reporting. Keeps early calls anchored to
    the prior (brief: '<15% reporting -> stay close to prior').
    """
    return max(0.0, min(1.0, pct_reporting / 85.0))


def win_probability(projected_dem_share: float, pct_reporting: float):
    """
    Return (prob_dem_wins, sigma) for a projected final two-party Dem share.

    sigma (our uncertainty, in vote-share points) starts wide (~0.085 at 0%)
    and narrows toward ~0.005 near 100%. Probability is the Normal CDF of how
    far the projection sits above the 0.50 win line, scaled by sigma.
    """
    if projected_dem_share is None:
        return 0.5, 0.085
    sigma = 0.08 * (1.0 - pct_reporting / 100.0) + 0.005
    z = (projected_dem_share - 0.5) / sigma
    prob = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return prob, sigma


def confidence_tier(pct_reporting: float) -> str:
    """Maps % reporting to the brief's confidence tiers."""
    if pct_reporting < 15:
        return "Very Early — Directional Only"
    if pct_reporting < 40:
        return "Early — Lean Forming"
    if pct_reporting < 70:
        return "Developing — Probable"
    if pct_reporting < 90:
        return "Strong Signal"
    return "Near Final"


def lean_label(prob_dem: float) -> str:
    """
    Symmetric race-rating label from the Dem win probability.
    (Panel 6: 'Lean D' / 'Toss-Up' / 'Likely R' etc.)
    """
    p = prob_dem
    if p >= 0.97:
        return "Safe D"
    if p >= 0.85:
        return "Likely D"
    if p >= 0.65:
        return "Lean D"
    if p > 0.55:
        return "Tilt D"
    if p >= 0.45:
        return "Toss-Up"
    if p > 0.35:
        return "Tilt R"
    if p > 0.15:
        return "Lean R"
    if p > 0.03:
        return "Likely R"
    return "Safe R"
