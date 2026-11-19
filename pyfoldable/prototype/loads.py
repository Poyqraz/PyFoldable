"""Steady deployed connection loads of the single-lug joint from the distal mass properties (rotating frame).

The distal segment (printed part; the pin set sits on the axis and is booked to the proximal side) seats on the open
stop. In the blade frame rotating at Ω about +z, its loads are the centrifugal field Ω²(x, y, 0) dm, optional
aerodynamic forces (thrust T along +z, in-plane drag D along +x, acting at radius r_a on the quarter-chord line of
the distal plane) and the proximal's reactions: the stop force on the nose (normal +y, at the stop-face centroid) and
the pin/lug-stack resultant. The pin cannot carry a moment about its own axis, so the z-moment balance fixes the stop
force; the rest is the pin resultant (force and the couple about in-plane axes that the lug stack must carry).

    M_z(pin) = Ω² (y_p S_x − x_p S_y) − (r_a − r_j) D     (S = ∫ r dm)
    F_stop = M_z / (x_p − x_c)    (> 0: seated; ≤ 0: the segment leaves the stop and folds back)

Moments are taken about the pin axis at the lug interface plane z_i. All centrifugal terms scale with Ω²; aero
inputs are absolute forces given for the owner's maximum speed and are only applied there.
"""
from __future__ import annotations

import math

import numpy as np

RPM = 2.0 * math.pi / 60.0


def deployed(distal, d, meta, rpm: float, thrust_n: float | None = None, drag_n: float | None = None,
             aero_radius_mm: float | None = None) -> dict:
    """Loads [N, N·mm] at one speed. ``distal``: MassProps of the distal part; ``meta``: Parts.meta."""
    om2 = (rpm * RPM) ** 2
    c = d.connection
    px, py, zi = c.pin_x_mm, c.hinge_radius_mm, d.interface_z_mm
    m_kg = distal.mass_g / 1000.0
    S = m_kg * np.array(distal.cg_mm)                                   # kg·mm
    J = distal.second_moments() / 1000.0                                # kg·mm²
    F_cf = om2 * np.array([S[0], S[1], 0.0]) / 1000.0                   # N
    # ∫ (r − Q) × (x, y, 0) dm with Q = (px, py, zi)
    M_cf = om2 / 1000.0 * np.array([-(J[2, 1] - zi * S[1]),
                                    J[2, 0] - zi * S[0],
                                    py * S[0] - px * S[1]])             # N·mm
    F_aero, M_aero = np.zeros(3), np.zeros(3)
    aero = thrust_n is not None or drag_n is not None
    if aero:
        if aero_radius_mm is None:
            raise ValueError("Aerodynamic forces need their radius.")
        T, D = thrust_n or 0.0, drag_n or 0.0
        F_aero = np.array([D, 0.0, T])
        arm = np.array([0.0 - px, aero_radius_mm - py, c.axial_offset_mm - zi])
        M_aero = np.cross(arm, F_aero)
    x_front, x_back = meta["stop_x_mm"]
    z0, z1 = meta["stop_z_mm"]
    xc, zc = 0.5 * (x_front + x_back), 0.5 * (z0 + z1)
    Mz = M_cf[2] + M_aero[2]
    f_stop = Mz / (px - xc)
    seated = f_stop > 0
    F_stop = np.array([0.0, f_stop if seated else 0.0, 0.0])
    M_stop = np.cross(np.array([xc - px, py - py, zc - zi]), F_stop)
    F_pin = -(F_cf + F_aero + F_stop)                                   # proximal → distal through the pin stack
    M_pin = -(M_cf + M_aero + M_stop)
    if seated:
        M_pin[2] = 0.0
    return {
        "rpm": rpm, "aero_included": aero, "seated": bool(seated),
        "deploy_moment_nmm": float(Mz), "centrifugal_moment_nmm": float(M_cf[2]), "aero_moment_nmm": float(M_aero[2]),
        "centrifugal_force_n": F_cf.tolist(), "stop_force_n": float(F_stop[1]), "stop_lever_mm": float(px - xc),
        "pin_force_n": F_pin.tolist(), "pin_force_inplane_n": float(math.hypot(F_pin[0], F_pin[1])),
        "pin_axial_force_n": float(F_pin[2]),
        "pin_couple_nmm": M_pin.tolist(), "pin_couple_inplane_nmm": float(math.hypot(M_pin[0], M_pin[1])),
        # hinge-local (fold 0): e_s = +y, e_t = −x; force/moment the proximal transmits through pin + stop
        "local": {"N_tension": float(-(F_pin[1] + F_stop[1])), "V_inplane": float(-(F_pin[0])),
                  "V_axial": float(F_pin[2]), "M_torsion": float(M_pin[1] + M_stop[1]),
                  "M_bending": float(-(M_pin[0] + M_stop[0]))},
    }


def sweep(distal, d, meta, rpms) -> list[dict]:
    return [deployed(distal, d, meta, r) for r in rpms]


def owner_case(distal, d, meta):
    """The owner's operating point if the maximum speed is known (with aero forces if supplied), else None."""
    o = d.operating
    if o.max_rpm is None:
        return None
    return deployed(distal, d, meta, o.max_rpm, o.distal_thrust_n, o.distal_drag_n, o.distal_aero_radius_mm)
