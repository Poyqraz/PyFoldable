"""Complete opening–closing cycle of a tip-hinged foldable propeller with the loads carried by each folding connection.

Mechanical model (dynamically predicted fold motion, prescribed shaft speed)
--------------------------------------------------------------------------
Per blade a rigid distal segment on an ideal revolute joint whose pin is parallel to the shaft at the hinge
radius, the same axis and fold convention as the coupled DUST–MBDyn model (pin-and-lug / clevis–tang with the pin
parallel to the shaft; an optional axial offset ``delta`` lifts the distal segment and its tang along the pin).
Frames: hub-fixed blade frame of blade b (x chord LE→TE, y span outward, z along the shaft and thrust); the hub
turns by psi(t) about +z; blade b sits at psi + 2*pi*b/N. Fold angle theta about the pin: 0 open, negative folded
toward the trailing side.

The shaft speed is prescribed (rest → spin-up → operation → spin-down → rest, smooth cosine ramps); the drive
torque the shaft must supply to each distal segment is an output. Hinge elements, all between proximal and distal:
torsion return spring (torque toward stowed with a preload at the stowed stop), viscous damper, Coulomb friction
(regularised: no continuous dissipation while the joint is stationary), unilateral open and stowed stops
(linear spring with a Kelvin–Voigt dashpot from a declared restitution, as in the coupled model), optional open
latch (engages at the open stop, released at a commanded time), optional actuator torque window.
Centrifugal, Coriolis and Euler effects are *not* added as torques: they follow from the distal-body kinematics
(Newton–Euler about the moving pin), exactly as they arise from the body inertia in MBDyn. Gravity is optional.

Aerodynamic model (explicit, exploratory; not retained polar data)
-----------------------------------------------------------------
Quasi-steady strips along the distal segment with the declared chord and twist: relative wind from the free stream
(0, 0, -V), the shaft rotation and the fold rate, no induced velocity, normal-force coefficient blending a thin
airfoil slope 2*pi*sin(alpha) into a flat plate 2*sin(alpha) above a declared stall angle, chordwise drag C_D0 and a
centre of pressure moving from c/4 to c/2. Without induction the thrust is over-predicted; deep folds and low
speed are outside any retained data. ``model="off"`` gives the purely mechanical cycle.

Connection loads
----------------
At every sample, per blade, the resultant force and moment the proximal part transmits to the distal part at the
pin point H (and transported to the tang mid-plane H + delta*z), from the distal body's Newton–Euler balance with
its retained motion and applied loads. The revolute joint constrains all three forces and the two moments normal
to the pin; the moment about the pin is carried only by the hinge elements (spring, damper, friction, stops,
latch, actuator), which are reported separately and are not added again.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace

import numpy as np
from scipy.integrate import solve_ivp

G0 = 9.80665
RPM = 2.0 * math.pi / 60.0
MODEL_ID = "pyfoldable_fold_cycle_v1"


# ----------------------------------------------------------------------------------------------- inputs
@dataclass(frozen=True)
class ShaftSchedule:
    """Prescribed shaft speed: rest, cosine spin-up, operation, cosine spin-down to ``final_rpm``, rest."""
    operating_rpm: float = 2400.0
    rest_s: float = 0.1
    spinup_s: float = 0.6
    hold_s: float = 0.6
    spindown_s: float = 0.8
    end_rest_s: float = 0.6
    final_rpm: float = 0.0

    def __post_init__(self):
        for k, v in asdict(self).items():
            if not (isinstance(v, (int, float)) and math.isfinite(v)) or v < 0:
                raise ValueError(f"{k} must be a finite non-negative number.")
        if self.spinup_s <= 0 or self.spindown_s <= 0 or self.operating_rpm <= 0:
            raise ValueError("Spin-up, spin-down and operating speed must be positive.")
        if self.final_rpm > self.operating_rpm:
            raise ValueError("The final speed must not exceed the operating speed.")

    @property
    def knots(self):
        t1 = self.rest_s
        t2 = t1 + self.spinup_s
        t3 = t2 + self.hold_s
        t4 = t3 + self.spindown_s
        return (0.0, t1, t2, t3, t4, t4 + self.end_rest_s)

    def _segments(self):
        k, w, wf = self.knots, self.operating_rpm * RPM, self.final_rpm * RPM
        return ((k[0], k[1], 0.0, 0.0), (k[1], k[2], 0.0, w), (k[2], k[3], w, w), (k[3], k[4], w, wf), (k[4], k[5], wf, wf))

    def state(self, t):
        """(Omega, dOmega/dt, psi) at time(s) t; psi is the exact integral of Omega."""
        t = np.asarray(t, dtype=float)
        om, od, psi = np.zeros_like(t), np.zeros_like(t), np.zeros_like(t)
        acc = 0.0
        for a, b, wa, wb in self._segments():
            T = b - a
            if T <= 0:
                continue
            sel = (t >= a) & ((t < b) if b < self.knots[-1] else (t <= b + 1e-12))
            s = np.clip((t[sel] - a) / T, 0.0, 1.0)
            om[sel] = wa + (wb - wa) * 0.5 * (1.0 - np.cos(np.pi * s))
            od[sel] = (wb - wa) * 0.5 * np.pi / T * np.sin(np.pi * s)
            psi[sel] = acc + wa * T * s + (wb - wa) * 0.5 * T * (s - np.sin(np.pi * s) / np.pi)
            acc += wa * T + (wb - wa) * 0.5 * T
        late = t > self.knots[-1]
        if late.any():
            wf = self._segments()[-1][3]
            om[late], psi[late] = wf, acc + wf * (t[late] - self.knots[-1])
        return om, od, psi


@dataclass(frozen=True)
class FoldMechanism:
    """Distal-segment mass properties, connection geometry and hinge elements (explicit SI values)."""
    mass_kg: float = 0.030
    cg_from_hinge_m: float = 0.055
    inertia_cg_kg_m2: float = 3.0e-5          # isotropic about the CG, as in the coupled model
    axial_offset_m: float = 0.0               # distal segment / tang mid-plane above the proximal mid-plane
    spring_nm_per_rad: float = 0.05
    spring_preload_nm: float = 0.30           # return torque toward stowed while resting on the stowed stop
    damping_nm_s_per_rad: float = 3.0e-3
    coulomb_nm: float = 0.0
    friction_transition_rad_s: float = 0.05
    open_stop_rad: float = 0.0
    stowed_stop_rad: float = -math.radians(110.0)
    stop_stiffness_nm_per_rad: float = 200.0
    stop_restitution: float = 0.5
    open_latch: bool = False
    latch_release_s: float = 1.3
    latch_stiffness_nm_per_rad: float = 2000.0
    actuator_nm: float = 0.0                  # signed torque on the distal segment (negative folds)
    actuator_start_s: float = 0.0
    actuator_end_s: float = 0.0
    declaration_kind: str = "exploratory_assumption"
    source: str = "Keşif varsayımı: kullanıcı tarafından değiştirilebilir; donanım ölçümü değildir."

    def __post_init__(self):
        for k, v in asdict(self).items():
            if k in ("open_latch", "declaration_kind", "source"):
                continue
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"{k} must be a finite number.")
        if self.mass_kg <= 0 or self.cg_from_hinge_m <= 0 or self.inertia_cg_kg_m2 <= 0:
            raise ValueError("Mass, CG distance and inertia must be positive.")
        if min(self.spring_nm_per_rad, self.spring_preload_nm, self.damping_nm_s_per_rad, self.coulomb_nm) < 0:
            raise ValueError("Spring, preload, damping and friction must be non-negative.")
        if self.friction_transition_rad_s <= 0 or self.stop_stiffness_nm_per_rad <= 0 or self.latch_stiffness_nm_per_rad <= 0:
            raise ValueError("Friction transition and stop/latch stiffness must be positive.")
        if not 0 < self.stop_restitution <= 1:
            raise ValueError("Restitution must be in (0, 1].")
        if not -math.pi < self.stowed_stop_rad < self.open_stop_rad <= 0.2:
            raise ValueError("Require -180° < stowed stop < open stop ≤ ~11°.")
        if self.declaration_kind not in ("exploratory_assumption", "declared_hardware_property"):
            raise ValueError("Unknown declaration kind.")

    @property
    def hinge_inertia_kg_m2(self):
        return self.inertia_cg_kg_m2 + self.mass_kg * self.cg_from_hinge_m ** 2

    def _damping(self, stiffness, zeta):
        return 2.0 * zeta * math.sqrt(stiffness * self.hinge_inertia_kg_m2)

    @property
    def latch_target_rad(self):
        """A detent presses the blade onto its open stop: its neutral angle lies 1 mrad inside the stop."""
        return self.open_stop_rad + 1e-3

    @property
    def stop_damping_nm_s_per_rad(self):
        le = math.log(self.stop_restitution)
        return self._damping(self.stop_stiffness_nm_per_rad, -le / math.sqrt(math.pi ** 2 + le ** 2))

    @property
    def latch_damping_nm_s_per_rad(self):
        return self._damping(self.latch_stiffness_nm_per_rad, 0.7)


@dataclass(frozen=True)
class AeroModel:
    """Explicit quasi-steady strip model on the distal segment (see module docstring)."""
    model: str = "plate"                      # "plate" or "off"
    inflow_m_s: float = 14.0
    density_kg_m3: float = 1.225
    cd0: float = 0.02
    stall_deg: float = 12.0
    blend_deg: float = 3.0
    strips: tuple = ()                        # ((s_from_hinge_m, ds_m, chord_m, twist_rad), ...)

    def __post_init__(self):
        if self.model not in ("plate", "off"):
            raise ValueError("Aerodynamic model must be 'plate' or 'off'.")
        if self.model == "plate" and not self.strips:
            raise ValueError("The strip model needs distal strips.")


@dataclass(frozen=True)
class CycleCase:
    hinge_radius_m: float
    blade_count: int
    schedule: ShaftSchedule
    mechanism: FoldMechanism
    aero: AeroModel
    gravity: str = "off"                      # "off", "shaft_vertical" (g along -z) or "shaft_horizontal" (g along -x)
    output_dt_s: float = 1.0e-3
    contact_dt_s: float = 2.0e-5
    rtol: float = 1e-8
    max_step_s: float = 2.5e-4

    def __post_init__(self):
        if not (self.hinge_radius_m > 0 and 1 <= self.blade_count <= 8):
            raise ValueError("Hinge radius must be positive and 1–8 blades.")
        if self.gravity not in ("off", "shaft_vertical", "shaft_horizontal"):
            raise ValueError("Unknown gravity option.")


def strips_from_stations(stations, hinge_radius_m, n=10):
    """Uniform strips over the distal aerodynamic span [hinge, last station] with linearly interpolated chord/twist."""
    r = [s[0] for s in stations]
    if not r[0] < hinge_radius_m < r[-1]:
        raise ValueError("The hinge must lie inside the station span.")
    edges = np.linspace(hinge_radius_m, r[-1], n + 1)
    mid = 0.5 * (edges[1:] + edges[:-1])
    chord = np.interp(mid, r, [s[1] for s in stations])
    twist = np.interp(mid, r, [s[2] for s in stations])
    return tuple((float(m - hinge_radius_m), float(e1 - e0), float(c), float(t))
                 for m, e0, e1, c, t in zip(mid, edges[:-1], edges[1:], chord, twist))


# ---------------------------------------------------------------------------------------------- kinematics
def _rot(theta, v):
    """Rotate vectors v[..., 3] about z by theta (broadcast)."""
    c, s = np.cos(theta), np.sin(theta)
    x, y = c * v[..., 0] - s * v[..., 1], s * v[..., 0] + c * v[..., 1]
    return np.stack([x, y, np.broadcast_to(v[..., 2], x.shape)], axis=-1)


def _zcross(v):
    return np.stack([-v[..., 1], v[..., 0], np.zeros_like(v[..., 0])], axis=-1)


class _Model:
    """Row-vectorised dynamics: every array argument has one row per (sample, blade) pair."""

    def __init__(self, case: CycleCase):
        self.c, self.m = case, case.mechanism
        self.N = case.blade_count
        self.az = 2.0 * math.pi * np.arange(self.N) / self.N
        self.xH = np.array([0.0, case.hinge_radius_m, 0.0])
        a = case.aero
        self.strips = np.array(a.strips, dtype=float).reshape(-1, 4) if a.model == "plate" else np.zeros((0, 4))
        g = {"off": (0.0, 0.0, 0.0), "shaft_vertical": (0.0, 0.0, -G0), "shaft_horizontal": (-G0, 0.0, 0.0)}[case.gravity]
        self.g = np.array(g)

    # -- aerodynamics ---------------------------------------------------------------------------------------
    def aero(self, Om, th, thd):
        """Distal aero loads per row in the blade frame: force F[M,3], moment about the pin point M_H[M,3],
        aero power on the body P[M], moment about the shaft axis Mshaft[M], strip alpha [deg][M,S]."""
        M_, S = len(th), len(self.strips)
        if S == 0:
            z = np.zeros((M_, 3))
            return z, z.copy(), np.zeros(M_), np.zeros(M_), np.zeros((M_, 0))
        a, m = self.c.aero, self.m
        Om = np.broadcast_to(np.asarray(Om, dtype=float), th.shape)[:, None, None]
        s, ds, ch, tw = (self.strips[:, k] for k in range(4))
        loc = np.stack([np.zeros(S), s, np.full(S, m.axial_offset_m)], axis=-1)           # distal frame
        p = self.xH + _rot(th[:, None], np.broadcast_to(loc, (M_, S, 3)))                  # [M,S,3]
        cvec = _rot(th[:, None], np.stack([np.cos(tw), np.zeros(S), -np.sin(tw)], -1)[None])
        nvec = _rot(th[:, None], np.stack([np.sin(tw), np.zeros(S), np.cos(tw)], -1)[None])
        evec = _rot(th[:, None], np.broadcast_to(np.array([0.0, 1.0, 0.0]), (1, S, 3)))
        v = Om * _zcross(p) + thd[:, None, None] * _zcross(p - self.xH)
        w = np.array([0.0, 0.0, -a.inflow_m_s]) - v
        w = w - np.sum(w * evec, -1, keepdims=True) * evec
        wn, wc = np.sum(w * nvec, -1), np.sum(w * cvec, -1)
        q = 0.5 * a.density_kg_m3 * (wn ** 2 + wc ** 2)
        alpha = np.arctan2(wn, wc)
        sa = np.sin(alpha)
        sig = 1.0 / (1.0 + np.exp(-(np.abs(sa) - math.sin(math.radians(a.stall_deg))) / math.sin(math.radians(a.blend_deg))))
        cn = (1.0 - sig) * 2.0 * math.pi * sa + sig * 2.0 * sa
        speed = np.sqrt(np.maximum(wn ** 2 + wc ** 2, 1e-30))
        ct = a.cd0 * wc / speed
        f = (q * ch * ds)[..., None] * (cn[..., None] * nvec + ct[..., None] * cvec)         # [M,S,3]
        pc = p + ((0.25 * sig) * ch)[..., None] * cvec                                        # centre of pressure
        vc = Om * _zcross(pc) + thd[:, None, None] * _zcross(pc - self.xH)
        return (f.sum(1), np.cross(pc - self.xH, f).sum(1), np.sum(f * vc, (-1, -2)),
                np.cross(pc, f)[..., 2].sum(1), np.degrees(alpha))

    # -- hinge elements ------------------------------------------------------------------------------------
    def elements(self, t, th, thd, latched):
        m = self.m
        t = np.broadcast_to(np.asarray(t, dtype=float), th.shape)
        out = {"spring": -m.spring_preload_nm - m.spring_nm_per_rad * (th - m.stowed_stop_rad),
               "damper": -m.damping_nm_s_per_rad * thd,
               "friction": -m.coulomb_nm * np.tanh(thd / m.friction_transition_rad_s)}
        kc, cc = m.stop_stiffness_nm_per_rad, m.stop_damping_nm_s_per_rad
        po, ps = np.maximum(th - m.open_stop_rad, 0.0), np.maximum(m.stowed_stop_rad - th, 0.0)
        out["open_stop"] = np.where(po > 0, -kc * po - cc * thd, 0.0)
        out["stowed_stop"] = np.where(ps > 0, kc * ps - cc * thd, 0.0)
        kl, cl = m.latch_stiffness_nm_per_rad, m.latch_damping_nm_s_per_rad
        out["latch"] = np.where(latched, -kl * (th - m.latch_target_rad) - cl * thd, 0.0)
        out["actuator"] = np.where((t >= m.actuator_start_s) & (t < m.actuator_end_s), m.actuator_nm, 0.0)
        return out

    def gravity(self, psi, az):
        """Gravity vector in each row's blade frame [M,3]."""
        return _rot(-(psi + az), np.broadcast_to(self.g, (len(az), 3)))

    def dynamics(self, t, az, th, thd, latched):
        """Shaft state, hinge elements, aero, gravity and the fold acceleration for each row."""
        m = self.m
        Om, Od, psi = self.c.schedule.state(t)
        el = self.elements(t, th, thd, latched)
        aero = self.aero(Om, th, thd)
        r = _rot(th, np.broadcast_to(np.array([0.0, m.cg_from_hinge_m, m.axial_offset_m]), (len(th), 3)))
        gb = self.gravity(psi, az)
        tau_g = np.cross(r, m.mass_kg * gb)[:, 2]
        inertial = -m.mass_kg * m.cg_from_hinge_m * self.c.hinge_radius_m * (Om ** 2 * np.sin(th) + Od * np.cos(th))
        acc = (sum(el.values()) + aero[1][:, 2] + tau_g + inertial) / m.hinge_inertia_kg_m2 - Od
        return {"Om": Om, "Od": Od, "psi": psi, "el": el, "aero": aero, "gb": gb, "r": r, "acc": acc}

    def accel(self, t, th, thd, latched):
        return self.dynamics(np.full(self.N, t), self.az, th, thd, latched)["acc"]


# --------------------------------------------------------------------------------------------- integration
def _initial_angle(m: FoldMechanism):
    """Resting on the stowed stop under the spring preload (static equilibrium inside the stop)."""
    return m.stowed_stop_rad - m.spring_preload_nm / m.stop_stiffness_nm_per_rad


def _crossings(sol, a, b, idx, angle, rate_idx, dt=2e-5):
    """Sign changes of theta_idx - angle on the dense solution over [a, b], refined by root finding."""
    from scipy.optimize import brentq
    ts = np.unique(np.append(np.arange(a, b, dt), b))
    g = sol(ts)[idx] - angle
    out = []
    for i in np.flatnonzero(g[:-1] * g[1:] < 0):
        try:
            tc = brentq(lambda x: float(sol(x)[idx] - angle), ts[i], ts[i + 1], xtol=1e-12)
        except ValueError:
            tc = 0.5 * (ts[i] + ts[i + 1])
        out.append((float(tc), float(sol(tc)[rate_idx])))
    return out


def _integrate(case: CycleCase):
    """Piecewise integration between schedule/command knots; stop crossings are found on the dense solution and the
    latch is switched on at the first open-stop arrival of an armed blade (the segment is cut there and restarted)."""
    model = _Model(case)
    N, m = model.N, case.mechanism
    breaks = sorted({*case.schedule.knots, *(x for x in (m.latch_release_s if m.open_latch else None,
                                                        m.actuator_start_s if m.actuator_nm else None,
                                                        m.actuator_end_s if m.actuator_nm else None)
                                             if x is not None and 0 < x < case.schedule.knots[-1])})
    t_end = case.schedule.knots[-1]
    y = np.concatenate([np.full(N, _initial_angle(m)), np.zeros(N)])
    latched = np.zeros(N, bool)
    armed = np.full(N, bool(m.open_latch))
    segments, crossings, latch_events = [], [], []
    t = 0.0
    while t < t_end - 1e-12:
        t_next = min([b for b in breaks if b > t + 1e-12] + [t_end])
        lat_now = latched.copy()

        def rhs(tt, yy, lat_now=lat_now):
            th, thd = yy[:N], yy[N:]
            return np.concatenate([thd, model.accel(tt, th, thd, lat_now)])

        sol = solve_ivp(rhs, (t, t_next), y, method="LSODA", rtol=case.rtol, atol=1e-9,
                        max_step=case.max_step_s, dense_output=True)
        if sol.status < 0:
            raise RuntimeError(f"Cycle integration failed at t = {t:.4f} s: {sol.message}")
        t_stop, engage = float(sol.t[-1]), []
        if m.open_latch and t < m.latch_release_s:
            for b in np.flatnonzero(armed & ~latched):
                up = [c for c in _crossings(sol.sol, t, t_stop, b, m.open_stop_rad, N + b) if c[1] > 0]
                if up and up[0][0] < min(t_stop, m.latch_release_s):
                    engage.append((up[0][0], b))
        if engage:
            t_stop = min(e[0] for e in engage)
        segments.append((t, t_stop, sol.sol, lat_now))
        for b in range(N):
            for kind, ang in (("open", m.open_stop_rad), ("stowed", m.stowed_stop_rad)):
                for tc, rate in _crossings(sol.sol, t, t_stop, b, ang, N + b):
                    crossings.append({"stop": kind, "blade": b, "time_s": tc, "rate_rad_s": rate})
        y = np.asarray(sol.sol(t_stop), dtype=float).copy()
        if engage:
            for tc, b in engage:
                if abs(tc - t_stop) < 1e-12:
                    latched[b] = True
                    latch_events.append({"kind": "latch_engaged", "blade": int(b), "time_s": tc})
        t = t_stop
        if m.open_latch and t >= m.latch_release_s - 1e-12 and armed.any():
            if latched.any():
                latch_events.append({"kind": "latch_released", "blade": None, "time_s": float(m.latch_release_s)})
            latched[:] = False
            armed[:] = False
    return model, segments, crossings, latch_events


def _sample_times(case, crossings, dt=None):
    t_end = case.schedule.knots[-1]
    base = np.arange(0.0, t_end + 0.5 * (dt or case.output_dt_s), dt or case.output_dt_s)
    fine = [np.arange(max(0.0, c["time_s"] - 2e-3), min(t_end, c["time_s"] + 4e-3), case.contact_dt_s)
            for c in [c for c in crossings if c["blade"] == 0][:24]] if dt is None else []
    tt = np.unique(np.concatenate([base, *fine, np.array(case.schedule.knots)]))
    return tt[(tt >= 0) & (tt <= t_end)]


def _evaluate(model, segments, t):
    N = model.N
    th, thd, lat = np.zeros((len(t), N)), np.zeros((len(t), N)), np.zeros((len(t), N), bool)
    for a, b, sol, latched in segments:
        sel = (t >= a - 1e-12) & (t <= b + 1e-12)
        if sel.any():
            yy = sol(np.clip(t[sel], a, b))
            th[sel], thd[sel] = yy[:N].T, yy[N:].T
            lat[sel] = latched
    return th, thd, lat


# ----------------------------------------------------------------------------------------- loads & energy
LOAD_KEYS = ("N_tension", "V_inplane", "V_axial", "M_torsion", "M_bending", "M_pin")
CONTRIBUTIONS = ("shaft_centripetal", "shaft_euler", "fold_motion", "aerodynamic", "gravity")
ELEMENTS = ("spring", "damper", "friction", "open_stop", "stowed_stop", "latch", "actuator")


def _postprocess(model, t, th, thd, lat):
    """All derived quantities per sample and blade [T, N] (vectors [T, N, 3] in the blade frame)."""
    c, m = model.c, model.m
    T, N = th.shape
    rows = lambda a: np.asarray(a).reshape(T * N, *np.asarray(a).shape[2:])  # noqa: E731
    back = lambda a: a.reshape(T, N, *a.shape[1:])  # noqa: E731
    tr, az = np.repeat(t, N), np.tile(model.az, T)
    d = model.dynamics(tr, az, rows(th), rows(thd), rows(lat))
    Om, Od, psi, el, gb, r, acc = d["Om"], d["Od"], d["psi"], d["el"], d["gb"], d["r"], d["acc"]
    F_a, M_a, P_a, Msh, alpha = d["aero"]
    mass, J = m.mass_kg, m.inertia_cg_kg_m2
    thd_r = rows(thd)
    ez = np.array([0.0, 0.0, 1.0])
    xG = model.xH + r
    flat = lambda v: np.concatenate([v[:, :2], np.zeros((len(v), 1))], 1)  # noqa: E731
    a_cent = -(Om ** 2)[:, None] * flat(xG)
    a_eul = Od[:, None] * _zcross(xG)
    a_fold = acc[:, None] * _zcross(r) - (thd_r ** 2 + 2 * Om * thd_r)[:, None] * flat(r)
    parts_F = {"shaft_centripetal": mass * a_cent, "shaft_euler": mass * a_eul, "fold_motion": mass * a_fold,
               "aerodynamic": -F_a, "gravity": -mass * gb}
    parts_M = {"shaft_centripetal": np.cross(r, mass * a_cent),
               "shaft_euler": np.cross(r, mass * a_eul) + J * Od[:, None] * ez,
               "fold_motion": np.cross(r, mass * a_fold) + J * acc[:, None] * ez,
               "aerodynamic": -M_a, "gravity": -np.cross(r, mass * gb)}
    F, M = sum(parts_F.values()), sum(parts_M.values())
    vH = Om[:, None] * _zcross(np.broadcast_to(model.xH, (len(Om), 3)))
    vG = Om[:, None] * _zcross(xG) + thd_r[:, None] * _zcross(r)
    th_r = rows(th)
    dth = th_r - m.stowed_stop_rad
    po, ps = np.maximum(th_r - m.open_stop_rad, 0.0), np.maximum(m.stowed_stop_rad - th_r, 0.0)
    lat_r = rows(lat)
    res = {k: back(el[k]) for k in ELEMENTS}
    res.update({
        "theta_ddot": back(acc), "aero_pin": back(M_a[:, 2]), "aero_thrust": back(F_a[:, 2]), "aero_power": back(P_a),
        "aero_shaft": back(Msh), "drive_power": back((F * vH).sum(1) + Om * M[:, 2]),
        "drive_torque": back(np.cross(np.broadcast_to(model.xH, F.shape), F)[:, 2] + M[:, 2]),
        "gravity_power": back(mass * (gb * vG).sum(1)),
        "kinetic": back(0.5 * mass * (vG ** 2).sum(1) + 0.5 * J * (Om + thd_r) ** 2),
        "potential": back(m.spring_preload_nm * dth + 0.5 * m.spring_nm_per_rad * dth ** 2
                          + 0.5 * m.stop_stiffness_nm_per_rad * (po ** 2 + ps ** 2)
                          + np.where(lat_r, 0.5 * m.latch_stiffness_nm_per_rad * (th_r - m.latch_target_rad) ** 2, 0.0)),
        "dissipation_power": back(m.damping_nm_s_per_rad * thd_r ** 2
                                  + m.coulomb_nm * np.tanh(thd_r / m.friction_transition_rad_s) * thd_r
                                  + np.where((po > 0) | (ps > 0), m.stop_damping_nm_s_per_rad * thd_r ** 2, 0.0)
                                  + np.where(lat_r, m.latch_damping_nm_s_per_rad * thd_r ** 2, 0.0)),
        "actuator_power": back(el["actuator"] * thd_r),
    })
    vec = {"F": back(F), "M": back(M), **{f"F_{k}": back(v) for k, v in parts_F.items()},
           **{f"M_{k}": back(v) for k, v in parts_M.items()}}
    alo = alpha.min(1).reshape(T, N)[:, 0] if alpha.size else np.full(T, np.nan)
    ahi = alpha.max(1).reshape(T, N)[:, 0] if alpha.size else np.full(T, np.nan)
    return Om.reshape(T, N)[:, 0], Od.reshape(T, N)[:, 0], psi.reshape(T, N)[:, 0], res, vec, alo, ahi


def hinge_frame(theta):
    """Unit vectors (e_s along the distal span, e_t in-plane toward the leading side, e_z along the pin)."""
    th = np.asarray(theta)
    es = np.stack([-np.sin(th), np.cos(th), np.zeros_like(th)], -1)
    et = np.stack([-np.cos(th), -np.sin(th), np.zeros_like(th)], -1)
    ez = np.broadcast_to(np.array([0.0, 0.0, 1.0]), es.shape)
    return es, et, ez


def local_components(F, M, theta, axial_offset_m=0.0):
    """Hinge-local components of the force/moment the proximal part transmits to the distal part. M is about the
    pin point H; components are reported about the tang mid-plane H + delta*z (moment transport M_P = M_H − δ z × F).
    N_tension = −F·e_s (positive pulls the distal part outward against the connection)."""
    es, et, ez = hinge_frame(theta)
    MP = M - axial_offset_m * np.cross(np.broadcast_to(np.array([0.0, 0.0, 1.0]), F.shape), F)
    dot = lambda a, b: np.sum(a * b, -1)  # noqa: E731
    return {"N_tension": -dot(F, es), "V_inplane": dot(F, et), "V_axial": dot(F, ez),
            "M_torsion": dot(MP, es), "M_bending": dot(MP, et), "M_pin": dot(MP, ez)}


# ------------------------------------------------------------------------------------------- events
def _contacts(model, segments, crossings, case):
    """Per stop contact: entry/exit, duration, peak stop torque, angular impulse, effective restitution."""
    m = case.mechanism
    out = []
    by = {}
    for c in sorted(crossings, key=lambda c: c["time_s"]):
        by.setdefault((c["blade"], c["stop"]), []).append(c)
    for (b, stop), cs in by.items():
        entering = (lambda r: r > 0) if stop == "open" else (lambda r: r < 0)
        i = 0
        while i < len(cs):
            if entering(cs[i]["rate_rad_s"]):
                t0 = cs[i]["time_s"]
                t1 = next((c["time_s"] for c in cs[i + 1:] if not entering(c["rate_rad_s"])), None)
                exit_rate = next((c["rate_rad_s"] for c in cs[i + 1:] if not entering(c["rate_rad_s"])), None)
                if t1 is None:
                    t1 = case.schedule.knots[-1]
                tt = np.linspace(t0, t1, max(3, int((t1 - t0) / case.contact_dt_s) + 1))
                th, thd, lat = _evaluate(model, segments, tt)
                tau = model.elements(tt, th[:, b], thd[:, b], lat[:, b])[f"{stop}_stop"]
                latched_exit = bool(lat[-1, b])
                k = int(np.argmax(np.abs(tau)))
                out.append({"blade": b, "stop": stop, "t_in_s": t0, "t_out_s": t1, "duration_s": t1 - t0,
                            "peak_torque_nm": float(tau[k]), "peak_time_s": float(tt[k]),
                            "impulse_nm_s": float(np.trapezoid(tau, tt) if hasattr(np, "trapezoid") else np.trapz(tau, tt)),
                            "rate_in_rad_s": cs[i]["rate_rad_s"], "rate_out_rad_s": exit_rate,
                            "effective_restitution": (abs(exit_rate / cs[i]["rate_rad_s"]) if exit_rate is not None
                                                      and abs(cs[i]["rate_rad_s"]) > 1e-9 and not latched_exit else None)})
                i = next((j + 1 for j in range(i + 1, len(cs)) if not entering(cs[j]["rate_rad_s"])), len(cs))
            else:
                i += 1
    return sorted((c for c in out if c["duration_s"] > 1e-5), key=lambda c: c["t_in_s"])


def _first(mask, t):
    idx = np.flatnonzero(mask)
    return (float(t[idx[0]]), int(idx[0])) if idx.size else (None, None)


def _events(t, th, thd, res, contacts, case, b=0):
    """Selectable events for blade b, in time order."""
    m, k = case.mechanism, case.schedule.knots
    ev = []

    def add(key, label, time):
        if time is not None:
            ev.append({"key": key, "label": label, "time_s": float(time), "index": int(np.argmin(np.abs(t - time)))})
    add("spinup_start", "Hızlanma başlangıcı", k[1])
    # release: the stowed stop stops reacting (centrifugal, shaft-acceleration and aerodynamic moments now exceed the
    # spring preload); the motion start follows once the blade has measurably left the stop
    resting = np.abs(res["stowed_stop"][:, b]) > 0
    release = None
    if resting[0]:
        j = np.flatnonzero(~resting)
        release = float(t[j[0]]) if j.size else None
    add("release", "Bırakma (kapalı stop tepkisi sıfırlandı)", release)
    start, _ = _first((th[:, b] > m.stowed_stop_rad + math.radians(0.5)) & (thd[:, b] > 0.2), t)
    add("motion_start", "Hareket başlangıcı", start)
    opens = [c for c in contacts if c["blade"] == b and c["stop"] == "open"]
    stowed = [c for c in contacts if c["blade"] == b and c["stop"] == "stowed" and c["t_in_s"] > (start or 0)]
    if opens:
        add("first_open_contact", "Açık stopa ilk temas", opens[0]["t_in_s"])
        add("peak_open_contact", "En büyük stop darbesi", max(opens, key=lambda c: abs(c["peak_torque_nm"]))["peak_time_s"])
        add("rebound", "Geri sekme (stoptan ayrılma)", opens[0]["t_out_s"] if opens[0]["t_out_s"] < k[-1] else None)
    if start is not None:
        upto = opens[0]["t_in_s"] if opens else k[3]
        sel = (t >= start) & (t <= upto)
        if sel.any():
            j = np.flatnonzero(sel)[np.argmax(thd[sel, b])]
            add("max_opening_rate", "En büyük açılma hızı", t[j])
    add("operating_reached", "Çalışma devrine ulaşıldı", k[2])
    if start is not None:
        quiet = (np.abs(thd[:, b]) < 0.5) & (t > (opens[0]["t_in_s"] if opens else start)) & (t < k[3])             & (th[:, b] > m.open_stop_rad - math.radians(5.0))
        settle = None
        for j in np.flatnonzero(quiet):
            span = (t >= t[j]) & (t <= t[j] + 0.05)
            if t[j] + 0.05 <= t[-1] and quiet[span].all():
                settle = float(t[j])
                break
        add("settled", "Oturma (açık konumda sakin)", settle)
    add("spindown_start", "Yavaşlama başlangıcı", k[3])
    if m.open_latch:
        add("latch_release", "Mandal bırakma (komut)", m.latch_release_s)
    hold = (t > k[2]) & (t <= k[3])
    th_op = float(np.median(th[hold, b])) if hold.any() else m.open_stop_rad
    t_cmd = min(k[3], m.latch_release_s) if m.open_latch else k[3]
    if m.actuator_nm < 0:
        t_cmd = min(t_cmd, m.actuator_start_s)
    retract, _ = _first((thd[:, b] < -0.5) & (t >= t_cmd) & (th[:, b] < th_op - math.radians(2.0)), t)
    add("retraction_start", "Geri katlanma başlangıcı", retract)
    if stowed:
        late = [c for c in stowed if retract is not None and c["t_in_s"] > retract]
        if late:
            add("closed_arrival", "Kapalı stopa varış", late[0]["t_in_s"])
    add("rest_reached", "Mil durdu / son devir", k[4])
    return sorted(ev, key=lambda e: e["time_s"])


def _peaks(t, th, comps, rpm, b=0):
    out = []
    for key, label in (("N_tension", "En büyük eksenel çekme"), ("V_inplane", "En büyük düzlem içi kesme"),
                       ("V_axial", "En büyük eksenel (pim yönü) kesme"), ("M_bending", "En büyük eğilme momenti"),
                       ("M_torsion", "En büyük burulma momenti"), ("M_pin", "En büyük pim ekseni momenti")):
        x = comps[key][:, b]
        j = int(np.argmax(np.abs(x)))
        out.append({"key": key, "label": label, "value": float(x[j]), "time_s": float(t[j]),
                    "theta_deg": float(np.degrees(th[j, b])), "rpm": float(rpm[j]), "index": j})
    return out


def _cumtrapz(y, t):
    out = np.zeros_like(y)
    out[1:] = np.cumsum(0.5 * (y[1:] + y[:-1]) * np.diff(t)[:, None] if y.ndim == 2 else 0.5 * (y[1:] + y[:-1]) * np.diff(t), axis=0)
    return out


# ------------------------------------------------------------------------------------------------- run
def run_cycle(case: CycleCase, *, sensitivity: bool = True, extra: dict | None = None) -> dict:
    model, segments, crossings, latch_events = _integrate(case)
    t = _sample_times(case, crossings)
    th, thd, lat = _evaluate(model, segments, t)
    Om, Od, psi, res, vec, alo, ahi = _postprocess(model, t, th, thd, lat)
    m = case.mechanism
    comps = local_components(vec["F"], vec["M"], th, m.axial_offset_m)
    contrib = {k: local_components(vec[f"F_{k}"], vec[f"M_{k}"], th, m.axial_offset_m) for k in CONTRIBUTIONS}
    contacts = _contacts(model, segments, crossings, case)
    rpm = Om / RPM
    # checks: (1) moment about the pin from Newton–Euler equals the hinge elements; (2) the same balance with the
    # angular acceleration recovered independently from the retained rates (finite differences); (3) energy
    el_sum = sum(res[k] for k in ELEMENTS)
    nonuni = np.gradient(thd, t, axis=0)
    J_h = m.hinge_inertia_kg_m2
    fd_pin = comps["M_pin"] + J_h * (nonuni - res["theta_ddot"])      # pin moment with the finite-difference θ̈
    contact_any = np.zeros_like(th, bool)
    for c in contacts:
        pad = 2.0 * case.output_dt_s                        # finite-difference stencil reaching into the contact
        contact_any[:, c["blade"]] |= (t >= c["t_in_s"] - pad) & (t <= c["t_out_s"] + pad)
    scale = max(1e-9, float(np.abs(el_sum).max()))
    # energy on a fine uniform grid (the hinge oscillation is lightly damped; 1 ms sampling would alias the powers)
    tf = _sample_times(case, crossings, dt=1e-4)
    thf, thdf, latf = _evaluate(model, segments, tf)
    resf = _postprocess(model, tf, thf, thdf, latf)[3]
    # integration consistency on the 0.1 ms grid: θ̈ from finite differences of the retained rates vs the model's θ̈,
    # as a pin-moment error J_h·Δθ̈, outside contacts, relative to the free-motion element torque level
    fd_err = J_h * np.abs(np.gradient(thdf, tf, axis=0) - resf["theta_ddot"])
    contact_f = np.zeros_like(thf, bool)
    for c in contacts:
        contact_f[:, c["blade"]] |= (tf >= c["t_in_s"] - 3e-4) & (tf <= c["t_out_s"] + 3e-4)
    el_f = sum(resf[k] for k in ELEMENTS)
    free_scale = max(1e-3, float(np.abs(el_f)[~contact_f].max()) if (~contact_f).any() else 1e-3)
    W_in = _cumtrapz(resf["drive_power"] + resf["aero_power"] + resf["gravity_power"] + resf["actuator_power"]
                     - resf["dissipation_power"], tf)
    Ef = resf["kinetic"] + resf["potential"]
    res_f = (Ef - Ef[0]) - W_in
    E_scale = max(1e-9, float(np.abs(_cumtrapz(np.abs(resf["drive_power"]), tf)).max()))
    energy_residual = np.stack([np.interp(t, tf, res_f[:, b]) for b in range(th.shape[1])], 1)
    work = {k: np.interp(t, tf, _cumtrapz(resf[p][:, 0], tf)) for k, p in
            (("drive", "drive_power"), ("aero", "aero_power"), ("gravity", "gravity_power"),
             ("actuator", "actuator_power"), ("dissipated", "dissipation_power"))}
    checks = [
        {"name": "pin_moment_equals_hinge_elements", "value": float(np.abs(comps["M_pin"] - el_sum).max() / scale),
         "limit": 1e-9, "meaning": "Newton–Euler pin-axis moment vs the sum of hinge-element torques (same state)."},
        {"name": "pin_moment_fd_outside_contact", "value": float(fd_err[~contact_f].max() / free_scale) if (~contact_f).any() else 0.0,
         "limit": 1e-2, "meaning": ("Integration consistency (0.1 ms grid): the pin balance with θ̈ recovered from the retained "
                                    "rates by finite differences, outside stop contacts, relative to the free-motion element torque level.")},
        {"name": "pin_moment_fd_in_contact", "value": float(np.abs(fd_pin - el_sum)[contact_any].max() / scale) if contact_any.any() else 0.0,
         "limit": None, "meaning": "Same, inside contacts relative to the contact peak (sampling of a stiff contact; informative)."},
        {"name": "energy_balance_relative", "value": float(np.abs(energy_residual).max() / E_scale), "limit": 1e-3,
         "meaning": "Kinetic + stored energy change vs drive, aerodynamic, gravity and actuator work minus dissipation."},
    ]
    for ch in checks:
        ch["passed"] = None if ch["limit"] is None else bool(ch["value"] <= ch["limit"])
    events = _events(t, th, thd, res, contacts, case)
    stowed_end = bool(th[-1, 0] < m.stowed_stop_rad + math.radians(2.0))
    open_reached = bool(th[:, 0].max() > m.open_stop_rad - math.radians(2.0))
    eq_open = float(np.degrees(th[(t > case.schedule.knots[2] + 0.5 * case.schedule.hold_s) & (t <= case.schedule.knots[3]), 0].mean())) \
        if case.schedule.hold_s > 0 else None

    def rd(a, n=5):
        return np.round(np.asarray(a, dtype=float), n).tolist()
    b0 = lambda a: a[:, 0]  # noqa: E731  # blade-1 detail (all blades identical unless gravity acts in-plane)
    series = {"time_s": rd(t, 7), "rpm": rd(rpm, 3), "omega_dot_rad_s2": rd(Od, 3), "psi_rad": rd(psi, 6),
              "theta_deg": rd(np.degrees(th), 4), "theta_rate_rad_s": rd(thd, 4), "theta_acc_rad_s2": rd(res["theta_ddot"], 2),
              "latched": lat.astype(int).tolist(),
              "aero_thrust_n": rd(res["aero_thrust"], 4), "aero_pin_torque_nm": rd(res["aero_pin"], 5),
              "aero_power_w": rd(b0(res["aero_power"]), 4), "aero_shaft_moment_nm": rd(b0(res["aero_shaft"]), 5),
              "alpha_min_deg": rd(alo, 2) if case.aero.model == "plate" else [],
              "alpha_max_deg": rd(ahi, 2) if case.aero.model == "plate" else [],
              "drive_torque_nm": rd(res["drive_torque"], 5), "drive_power_w": rd(b0(res["drive_power"]), 4),
              "kinetic_j": rd(b0(res["kinetic"]), 6), "potential_j": rd(b0(res["potential"]), 6),
              "dissipation_power_w": rd(b0(res["dissipation_power"]), 5), "energy_residual_j": rd(b0(energy_residual), 7),
              **{f"work_{k}_j": rd(v, 6) for k, v in work.items()},
              "F_global_n": rd(b0(_rot((psi[:, None] + model.az[None]), vec["F"])), 4),
              "M_global_nm": rd(b0(_rot((psi[:, None] + model.az[None]), vec["M"])), 5),
              **{f"hinge_{k}_nm": rd(res[k], 5) for k in ELEMENTS},
              **{f"load_{k}": rd(v, 5) for k, v in comps.items()},
              **{f"contrib_{c}_{k}": rd(b0(v), 5) for c, d in contrib.items() for k, v in d.items()}}
    out = {"schema_version": 1, "artifact_class": "pyfoldable_fold_cycle", "model_id": MODEL_ID,
           "analysis_mode": "mechanical_cycle_explicit_aero" if case.aero.model == "plate" else "mechanical_cycle_no_aero",
           "case": _case_dict(case), "derived": {"hinge_inertia_kg_m2": J_h, "stop_damping_nm_s_per_rad": m.stop_damping_nm_s_per_rad,
                                                 "latch_damping_nm_s_per_rad": m.latch_damping_nm_s_per_rad,
                                                 "initial_theta_deg": math.degrees(_initial_angle(m))},
           "series": series, "contacts": contacts, "latch_events": latch_events, "events": events,
           "peaks": _peaks(t, th, comps, rpm), "checks": checks,
           "outcome": {"open_reached": open_reached, "returned_to_stowed": stowed_end,
                       "final_theta_deg": float(np.degrees(th[-1, 0])), "operating_theta_deg": eq_open},
           "frames": {"blade_frame": "x chord LE→TE, y span outward, z along the shaft (thrust); hub turns +psi about +z",
                      "hinge_local": "e_s along the distal span, e_t in the rotor plane toward the leading side, e_z along the pin",
                      "load_reference": "force/moment transmitted by the proximal part to the distal part; moments about the tang mid-plane H + δz",
                      "constrained": "revolute: F_s, F_t, F_z, M_s (torsion), M_t (bending) are constraint reactions; M_z only through hinge elements"},
           "physical_qualification": False, "structural_stress": "NOT_SOLVED"}
    if sensitivity:
        out["sensitivity"] = contact_sensitivity(case, contacts)
    out.update(extra or {})
    return seal(out)


def _case_dict(case):
    d = asdict(case)
    d["aero"]["strips"] = [list(s) for s in case.aero.strips]
    return d


def case_from_dict(d) -> CycleCase:
    return CycleCase(hinge_radius_m=d["hinge_radius_m"], blade_count=d["blade_count"],
                     schedule=ShaftSchedule(**d["schedule"]), mechanism=FoldMechanism(**d["mechanism"]),
                     aero=AeroModel(**{**d["aero"], "strips": tuple(tuple(s) for s in d["aero"]["strips"])}),
                     gravity=d["gravity"], output_dt_s=d["output_dt_s"], contact_dt_s=d["contact_dt_s"],
                     rtol=d["rtol"], max_step_s=d["max_step_s"])


def contact_sensitivity(case: CycleCase, reference_contacts) -> dict:
    """First open-stop contact under a finer integration and under half/double stop stiffness."""
    first = next((c for c in reference_contacts if c["stop"] == "open" and c["blade"] == 0), None)
    if first is None:
        return {"available": False, "reason": "Açık stopa temas yok."}
    variants = [("Referans", case),
                ("Daha sıkı tolerans (rtol/100, adım/4)", replace(case, rtol=case.rtol / 100, max_step_s=case.max_step_s / 4)),
                ("Stop rijitliği ×0,5", replace(case, mechanism=replace(case.mechanism, stop_stiffness_nm_per_rad=case.mechanism.stop_stiffness_nm_per_rad / 2))),
                ("Stop rijitliği ×2", replace(case, mechanism=replace(case.mechanism, stop_stiffness_nm_per_rad=case.mechanism.stop_stiffness_nm_per_rad * 2)))]
    rows = []
    for label, cs in variants:
        if label == "Referans":
            c = first
        else:
            short = replace(cs, schedule=replace(cs.schedule, hold_s=min(cs.schedule.hold_s, 0.05), spindown_s=1e-3,
                                                 end_rest_s=0.0))
            model, segments, crossings, _ = _integrate(short)
            cc = _contacts(model, segments, crossings, short)
            c = next((x for x in cc if x["stop"] == "open" and x["blade"] == 0), None)
        rows.append({"variant": label, "available": c is not None,
                     **({} if c is None else {k: c[k] for k in ("t_in_s", "duration_s", "peak_torque_nm", "impulse_nm_s",
                                                                   "rate_in_rad_s", "effective_restitution")})})
    ok = [r for r in rows if r["available"]]
    spread = lambda k: (max(abs(r[k]) for r in ok) / max(1e-12, min(abs(r[k]) for r in ok)) - 1.0) if ok else None  # noqa: E731
    numeric = [r for r in ok if r["variant"].startswith(("Referans", "Daha"))]
    num_peak = (max(abs(r["peak_torque_nm"]) for r in numeric) / max(1e-12, min(abs(r["peak_torque_nm"]) for r in numeric)) - 1.0
                if len(numeric) == 2 else None)
    return {"available": True, "rows": rows, "impulse_spread": spread("impulse_nm_s"), "peak_spread": spread("peak_torque_nm"),
            "numerical_peak_change": num_peak,
            "reading": ("Tepe stop momenti temas rijitliğiyle değişir (rijit bir stop için zaman adımına ve rijitliğe bağlı bir "
                        "tepe); darbe impulsu ve giriş hızı daha kararlıdır. Tepe değer, ölçülmüş stop rijitliği ve sönümü "
                        "olmadan donanım tasarım yükü olarak kullanılmamalıdır.")}


def seal(body: dict) -> dict:
    import hashlib
    import json
    body = {k: v for k, v in body.items() if k != "result_sha256"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return {**json.loads(text), "result_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def verify(row: dict) -> dict:
    """Content check of a saved cycle record (digest, class, schema); raises ValueError."""
    if not isinstance(row, dict) or row.get("artifact_class") != "pyfoldable_fold_cycle" or row.get("schema_version") != 1:
        raise ValueError("Not a PyFoldable fold-cycle record.")
    if seal(row)["result_sha256"] != row.get("result_sha256"):
        raise ValueError("Fold-cycle record digest does not match its content.")
    case = case_from_dict(row["case"])
    s = row["series"]
    n = len(s.get("time_s", ()))
    if n < 2 or any(isinstance(v, list) and v and len(v) != n for v in s.values()):
        raise ValueError("Fold-cycle series lengths are inconsistent.")
    if any(isinstance(v, list) and v and isinstance(v[0], list) and len(v[0]) not in (case.blade_count, 3)
           for v in s.values()):
        raise ValueError("Fold-cycle per-blade series do not match the blade count.")
    if any(not 0 <= e.get("index", -1) < n for e in row.get("events", ())):
        raise ValueError("Fold-cycle event index outside the series.")
    return row
