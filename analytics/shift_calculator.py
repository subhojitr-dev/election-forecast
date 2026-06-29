"""
shift_calculator.py  —  Phase 3 shift + projection math
Election Forecast Dashboard

Pure functions for the brief's intelligence steps 1-3:

  Step 1 (shift)      : how much better/worse the Democrat is doing vs the 2020
                        baseline, per precinct  (in two-party share points).
  Step 2 (rollup)     : combine precinct shifts into a county/state shift,
                        weighted by votes cast (bigger precincts count more).
  Step 3 (projection) : extrapolate to a final share using the NOT-yet-reported
                        precincts' 2020 baseline, nudged by the observed swing.

All shares are TWO-PARTY (dem / (dem + rep)) so third-party noise doesn't move
the signal. Step 4 (win probability) lives in bayesian_model.py.
"""

from __future__ import annotations

from typing import Optional


def two_party_share(dem: float, rep: float) -> Optional[float]:
    """Dem share of the two-party vote, or None if no two-party votes."""
    tot = (dem or 0) + (rep or 0)
    return (dem / tot) if tot > 0 else None


def weighted_shift(items) -> Optional[float]:
    """
    items: iterable of (shift, weight). Returns the vote-weighted average shift,
    or None if there is no weight yet (nothing reporting).
    """
    num = den = 0.0
    for shift, w in items:
        if shift is None or not w:
            continue
        num += shift * w
        den += w
    return (num / den) if den else None


def project_final_share(counted_dem: float, counted_rep: float,
                        remaining_base_total2: float,
                        remaining_base_dem_share: Optional[float],
                        observed_shift: Optional[float],
                        weight: float) -> Optional[float]:
    """
    Project the final two-party Dem share (brief Step 3, 'uniform swing'):

      - counted_dem/rep         : two-party votes already counted (live)
      - remaining_base_total2   : 2020 two-party votes of precincts NOT yet in
                                  (our estimate of how much vote is still out)
      - remaining_base_dem_share: those precincts' 2020 two-party Dem share
      - observed_shift          : statewide swing seen so far (share points)
      - weight                  : how much of that swing to apply to the
                                  remainder (0 early -> 1 late; from
                                  bayesian_model.reporting_weight)

    The remainder is expected to vote like 2020 *plus* the damped observed swing.
    """
    counted_total2 = (counted_dem or 0) + (counted_rep or 0)

    if remaining_base_total2 <= 0 or remaining_base_dem_share is None:
        # everything is in (or we have no baseline for the remainder)
        return two_party_share(counted_dem, counted_rep)

    expected_remaining_dem_share = remaining_base_dem_share + (observed_shift or 0.0) * weight
    expected_remaining_dem_share = max(0.0, min(1.0, expected_remaining_dem_share))

    proj_dem2 = counted_dem + remaining_base_total2 * expected_remaining_dem_share
    proj_total2 = counted_total2 + remaining_base_total2
    return (proj_dem2 / proj_total2) if proj_total2 > 0 else None
