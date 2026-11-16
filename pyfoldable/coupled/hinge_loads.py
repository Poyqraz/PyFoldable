"""Connection loads of a coupled DUST–MBDyn–preCICE record, from MBDyn's own joint reactions.

Per accepted window and blade, the resultant the proximal body transmits to the distal body at the hinge point:
the ideal revolute hinge (label 400+b) supplies the constraint force and the two moments normal to the pin; the
deformable hinge (500+b: spring, damper, stops) and the release latch (600+b) supply the moment about the pin.
MBDyn writes the revolute ``f_global``/``m_global`` as acting on the distal node and the deformable hinge and latch
moments as acting on the proximal node (verified on recorded runs: the distal force balance closes to rounding),
so M = m_rev − m_hinge − m_latch on the distal body.

Independent check from the sealed record only: the distal body's Newton–Euler balance with its retained motion
(CG acceleration and spin rate by central differences of the node states) and the exchanged aerodynamic loads of
its coupling nodes. Sampling is one value per coupling window; peaks inside stop contacts are window samples of a
penalty stop, not resolved impact histories.

The companion is written next to the run's raw outputs, bound to the sealed record (result_sha256) and to the raw
joint file (sha256); it is re-derived on request, never by the solver.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .frames import rotvec_to_matrix
from .mbdyn_output import parse_jnt

COMPANION = "hinge_loads.json"
REV, HINGE, LATCH = 400, 500, 600
NODE_Z_OFFSET_M = 0.01


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def local_components(F, M, R):
    """Hinge-local components (N tension +, in-plane shear toward the leading side, shear along the pin; torsion,
    bending, pin-axis moment) from global F, M and the distal node orientation R (columns: chord, span, pin)."""
    es, ez = R[:, 1], R[:, 2]
    et = np.cross(ez, es)
    return {"N_tension": -float(F @ es), "V_inplane": float(F @ et), "V_axial": float(F @ ez),
            "M_torsion": float(M @ es), "M_bending": float(M @ et), "M_pin": float(M @ ez)}


def startup_windows(residual: dict, magnitude: dict, W: int, rel: float = 0.02) -> int:
    """Number of leading windows in MBDyn's constraint start-up transient: the contiguous run from the first checked
    window whose force residual exceeds ``rel`` of the steady joint-force level (median of later windows), capped at
    half the record. A mismatch after a balanced window is never relabelled as start-up."""
    if not residual:
        return 0
    ks = sorted(residual)
    level = float(np.median([magnitude[k] for k in ks[len(ks) // 2:]])) or 1e-12
    n = 0
    for k in ks:
        if residual[k] > rel * level and k < W // 2:
            n = k + 1
        else:
            break
    return n


def extract(run_dir: Path, row: dict) -> dict:
    run_dir = Path(run_dir)
    jpath = run_dir / "structure" / "out.jnt"
    if not jpath.is_file():
        raise FileNotFoundError("Raw MBDyn joint output (structure/out.jnt) is not in the run folder.")
    jnt = parse_jnt(jpath)
    series = row["series"][:row["execution"]["valid_prefix_windows"]]
    if not series:
        raise ValueError("The record has no valid windows.")
    rd = json.loads((run_dir / "run_definition.json").read_text()) if (run_dir / "run_definition.json").is_file() else None
    nodes = (rd or {}).get("coupling_nodes") or row.get("run_definition", {}).get("coupling_nodes")
    mech = row["request"]["mechanics"]
    m, cg, J = mech["distal_mass_kg"], mech["distal_cg_from_hinge_m"], mech["distal_inertia_cg_kg_m2"]
    nb = len(series[0]["theta_deg"])
    W = len(series)
    if len(jnt) < W + 1:
        raise ValueError("Joint output is shorter than the record.")
    ns = row["node_states"]
    dt = series[1]["time_s"] - series[0]["time_s"] if W > 1 else 0.0
    out_blades = []
    per_window = {}                       # (blade, k) -> (force, bending, pin residual, |F|, |M|)
    for b in range(nb):
        comps = {k: [] for k in ("N_tension", "V_inplane", "V_axial", "M_torsion", "M_bending", "M_pin")}
        Fg, Mg = [], []
        xg, vg, wz, Rs, MaH, Fa = [], [], [], [], [], []
        for k, s in enumerate(series):
            w = s["window"]
            jb = jnt[w]
            F = np.array(jb[REV + b]["f_global"]) - (np.array(jb[LATCH + b]["f_global"]) if (LATCH + b) in jb else 0.0)
            M = (np.array(jb[REV + b]["m_global"]) - np.array(jb[HINGE + b]["m_global"])
                 - (np.array(jb[LATCH + b]["m_global"]) if (LATCH + b) in jb else 0.0))
            st = ns[w]["nodes"][str(200 + b)]
            R = np.array(rotvec_to_matrix(st["phi"]))
            for key, val in local_components(F, M, R).items():
                comps[key].append(val)
            Fg.append(F.tolist()); Mg.append(M.tolist())
            c = R @ np.array([0.0, cg, -NODE_Z_OFFSET_M * b])
            xH, vH, om = np.array(st["x"]), np.array(st["v"]), np.array(st["w"])
            xg.append(xH + c); vg.append(vH + np.cross(om, c)); wz.append(om); Rs.append(c)
            if nodes is not None:
                win = row["window_exchange"][w - 1]
                Fn, Mn, Xn = (np.array(win[q]) for q in ("force", "moment", "position"))
                sel = [i for i, nd in enumerate(nodes) if nd["blade"] == b and nd["segment"] == "distal"]
                Fa.append(Fn[sel].sum(0))
                MaH.append(sum(Mn[i] + np.cross(Xn[i] - xH, Fn[i]) for i in sel))
        # Newton–Euler from the retained motion (central differences, interior windows)
        if nodes is not None and W >= 3 and dt > 0:
            vg, wz = np.array(vg), np.array(wz)
            for k in range(1, W - 1):
                stencil = range(max(0, k - 2), min(W, k + 2))   # differences must not straddle a release or contact
                if (any(series[j]["contact_active"][b] for j in stencil)
                        or len({series[j]["latch_active"] for j in stencil}) > 1):
                    continue
                a = (vg[k + 1] - vg[k - 1]) / (2 * dt)
                al = (wz[k + 1] - wz[k - 1]) / (2 * dt)
                F_ne = m * a - Fa[k]
                M_ne = np.cross(Rs[k], m * a) + J * al - MaH[k]
                per_window[(b, k)] = (float(np.abs(F_ne - np.array(Fg[k])).max()),
                                      float(np.abs(M_ne[:2] - np.array(Mg[k])[:2]).max()), float(abs(M_ne[2] - Mg[k][2])),
                                      float(np.abs(Fg[k]).max()), float(np.abs(Mg[k]).max()))
        out_blades.append({"blade": b, **{k: v for k, v in comps.items()}, "F_global_n": Fg, "M_global_nm": Mg})
    # MBDyn's constraint reactions start with a decaying numerical transient (algebraic variables of the ms
    # integrator settling from the initial state): windows before the force balance settles are flagged, not hidden
    startup = startup_windows({k: max(v[0] for (b2, k2), v in per_window.items() if k2 == k) for (_, k) in per_window},
                              {k: max(v[3] for (b2, k2), v in per_window.items() if k2 == k) for (_, k) in per_window}, W)
    kept = {key: v for key, v in per_window.items() if key[1] >= startup}
    scale_f = max([v[3] for v in kept.values()] or [1e-12])
    scale_m = max([v[4] for v in kept.values()] or [1e-12])
    t = [s["time_s"] for s in series]
    valid = np.array([k >= startup for k in range(W)])
    peaks = []
    for key, label in (("N_tension", "En büyük eksenel çekme"), ("V_inplane", "En büyük düzlem içi kesme"),
                       ("V_axial", "En büyük pim yönü kesme"), ("M_bending", "En büyük eğilme momenti"),
                       ("M_torsion", "En büyük burulma momenti"), ("M_pin", "En büyük pim ekseni momenti")):
        x = np.where(valid, np.array(out_blades[0][key]), 0.0)
        j = int(np.argmax(np.abs(x)))
        peaks.append({"key": key, "label": label, "value": float(x[j]), "time_s": t[j], "window": series[j]["window"],
                      "theta_deg": series[j]["theta_deg"][0], "rpm": series[j]["rpm"],
                      "in_contact": bool(series[j]["contact_active"][0])})
    checks = []
    if kept:
        checks = [
            {"name": "distal_force_balance_relative", "value": max(v[0] for v in kept.values()) / scale_f, "limit": 2e-2,
             "meaning": "MBDyn revolute force vs m·a_G − F_aero from the retained motion (central differences), outside contacts and the start-up transient."},
            {"name": "distal_bending_balance_relative", "value": max(v[1] for v in kept.values()) / scale_m, "limit": 5e-2,
             "meaning": "Revolute moments normal to the pin vs the distal Newton–Euler balance about the hinge point."},
            {"name": "distal_pin_moment_balance_relative", "value": max(v[2] for v in kept.values()) / scale_m, "limit": 5e-2,
             "meaning": "Pin-axis moment of the hinge law and latch vs the distal Newton–Euler balance (finite differences)."},
        ]
        for c in checks:
            c["passed"] = bool(c["value"] <= c["limit"])
    return {"schema_version": 1, "artifact_class": "pyfoldable_coupled_hinge_loads",
            "record_result_sha256": row["result_sha256"], "raw_joint_sha256": _sha(jpath),
            "time_s": t, "window": [s["window"] for s in series], "rpm": [s["rpm"] for s in series],
            "theta_deg": [s["theta_deg"] for s in series], "contact_active": [s["contact_active"] for s in series],
            "latch_active": [s["latch_active"] for s in series], "blades": out_blades, "peaks": peaks, "checks": checks,
            "startup_transient_windows": startup,
            "startup_note": ("MBDyn's joint reactions settle from the initial state over the first windows (numerical "
                             "transient of the constraint multipliers, decaying ≈0.7× per window); those windows are "
                             "flagged and excluded from peaks and checks."),
            "force_residual_n": [max((per_window[(b, k)][0] for b in range(nb) if (b, k) in per_window), default=None)
                                 for k in range(W)],
            "frames": {"reference": "hinge point on the pin axis (distal node); force/moment on the distal body from the proximal body",
                       "hinge_local": "e_s distal span, e_t = e_z × e_s (leading side), e_z pin (shaft) axis",
                       "constrained": "revolute: all forces, torsion and bending; pin-axis moment only through the hinge law and latch"},
            "sampling": "one sample per coupling window; contact peaks are window samples of a penalty stop",
            "physical_qualification": False}


def path_for(run_dir: Path) -> Path:
    return Path(run_dir) / COMPANION


def _seal(body: dict) -> dict:
    body = {k: v for k, v in body.items() if k != "companion_sha256"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return {**json.loads(text), "companion_sha256": hashlib.sha256(text.encode()).hexdigest()}


def store(run_dir: Path, companion: dict) -> Path:
    p = path_for(run_dir)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(_seal(companion), separators=(",", ":"), allow_nan=False), encoding="utf-8")
    tmp.replace(p)
    return p


def load(run_dir: Path, row: dict) -> dict | None:
    """The stored companion when it belongs to this record and the raw joint file is unchanged, else None."""
    p = path_for(run_dir)
    if not p.is_file():
        return None
    try:
        c = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    jpath = Path(run_dir) / "structure" / "out.jnt"
    try:
        sealed = _seal(c)["companion_sha256"] == c.get("companion_sha256")
    except (TypeError, ValueError):
        sealed = False
    if (not sealed or c.get("artifact_class") != "pyfoldable_coupled_hinge_loads" or c.get("record_result_sha256") != row.get("result_sha256")
            or not jpath.is_file() or c.get("raw_joint_sha256") != _sha(jpath)):
        return None
    return c


def bounded(x):
    return x if (isinstance(x, (int, float)) and math.isfinite(x)) else None
