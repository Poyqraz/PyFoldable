"""Fold geometry envelope of the continuous RBF-coupled lifting line (no solver).

Two effects limit how far the distal segment may fold while the lifting-line representation stays
credible:

* RBF junction blending. DUST 3b1d2e61 moves each lifting-line point as a weighted average of two
  rigidly moving coupling nodes. Where those nodes sit on different segments, the averaged chord
  vector shortens; with equal weights its length is cos(theta/2) of the true chord, so the worst
  junction chord distortion is 1 - cos(theta/2). (Measured on the main case's mesh: 1.3 % at -20 deg,
  2.9 % at -30 deg, 6.5 % at -45 deg, 25 % at -90 deg, at the one station just outboard of the hinge;
  reports/coupled_deployment_20261112.)
* Sweep. An in-plane fold swings the distal span away from the radial direction, so the section sees
  a swept onset flow. Simple sweep theory with 2-D polars, as DUST's lifting line applies it, is
  limited to moderate sweep; at large folds the distal span approaches the flow direction.

The envelope is the largest fold for which both stay within their declared limits. It is enforced
when a case is built (initial fold) and on every accepted window (any blade's fold angle).
"""
from __future__ import annotations

import math

FOLD_LIMIT_CHORD = 0.02         # worst-case junction chord distortion
FOLD_LIMIT_SWEEP_DEG = 25.0     # distal-span sweep at mid-distal radius


def _geo(case):
    g = case["geometry"] if isinstance(case, dict) else case.geometry
    get = (lambda k: g[k]) if isinstance(g, dict) else (lambda k: getattr(g, k))
    return get("hinge_radius_m"), get("last_aero_radius_m")


def junction_chord_bound(theta_rad: float) -> float:
    """Worst-case relative chord shortening of an RBF point blended equally across the hinge."""
    return 1.0 - math.cos(0.5 * theta_rad)


def distal_sweep_deg(case, theta_rad: float) -> float:
    """Angle between the folded distal span and the radial direction at mid-distal radius."""
    h, tip = _geo(case)
    d = 0.5 * (tip - h)
    x, y = -d * math.sin(theta_rad), h + d * math.cos(theta_rad)
    sx, sy = -math.sin(theta_rad), math.cos(theta_rad)
    cosang = abs(sx * x + sy * y) / math.hypot(x, y)
    return math.degrees(math.acos(min(1.0, cosang)))


def fold_envelope(case) -> dict:
    """Most negative admissible fold angle [deg] and the limit that sets it."""
    chord_deg = -math.degrees(2.0 * math.acos(1.0 - FOLD_LIMIT_CHORD))
    sweep_deg = -90.0
    for i in range(1, 9001):
        th = -0.01 * i
        if distal_sweep_deg(case, math.radians(th)) > FOLD_LIMIT_SWEEP_DEG:
            sweep_deg = th + 0.01
            break
    limit = max(chord_deg, sweep_deg)
    return {"fold_limit_deg": limit, "limited_by": "junction_chord" if chord_deg >= sweep_deg else "distal_sweep",
            "junction_chord_limit": FOLD_LIMIT_CHORD, "distal_sweep_limit_deg": FOLD_LIMIT_SWEEP_DEG,
            "chord_limit_fold_deg": chord_deg, "sweep_limit_fold_deg": sweep_deg}
