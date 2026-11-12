"""Turn the raw outputs of one coupled run into a sealed result record.

Only accepted states are used: MBDyn writes after converged steps, the adapter
logs windows accepted by preCICE, DUST writes results only after convergence.
The three sources are aligned by window index (DUST result k <-> window k+1;
DUST's own time label lags the window time by one step) and their mutual
consistency is checked.

Status decision (never promotes a failure):
  completed                      all windows accepted and converged, coverage held
  failed_aero_coverage           a queried (alpha, Re, Mach) left the admitted table
  failed_unconverged_coupling    preCICE accepted a window at max-iterations
  cancelled | timeout | failed_solver | failed_incomplete
For every non-completed status the accepted prefix is retained as a partial
history and labelled as such.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from . import MODEL_ID, SCHEMA_VERSION
from .frames import relative_angle_about_z, rotvec_to_matrix
from .mbdyn_output import parse_jnt, parse_mov, parse_out

DRIVE_JOINT, SPRING_BASE, LATCH_BASE, HUB = 2, 500, 600, 2
CONTACT_TOL_RAD = 1e-9  # penetration below this is numerical round-off of a latched open pose


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_precice_iterations(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text().splitlines()[1:]:
        p = line.split()
        if len(p) >= 4:
            rows.append({"window": int(p[0]), "total_iterations": int(p[1]), "iterations": int(p[2]), "converged": int(p[3])})
    return rows


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _matvec(r, v):
    return tuple(sum(r[i][k] * v[k] for k in range(3)) for i in range(3))


def _dust_abort_reason(run: Path) -> str | None:
    log = run / "dust" / "dust.log"
    if not log.is_file():
        return None
    text = log.read_text(errors="replace")
    for marker in ("outside the table span of angles", "outside the table span of Mach"):
        if marker in text:
            return "aero_table_domain_exit: " + marker
    return None


# DUST 3b1d2e61 src/precice/mod_precice_rbf.f90 (build_connectivity), coupling_node_orientation = I:
# the n_wei nearest structural nodes in the anisotropic norm sqrt(d^T W d), inverse-distance weights.
COUPLING_NODE_LABEL_BASE = 1000  # deck.COUPLING_BASE (massless continuous_rbf coupling nodes)
RBF_WNORM = (1e-3, 1.0, 1e-3)
RBF_N_WEI = 2
RBF_W_ORDER = 1.0


def rbf_weights(nodes, point) -> tuple[list[int], list[float]]:
    """Indices into ``nodes`` and weights DUST uses for an aerodynamic point (component frame)."""
    d = [math.sqrt(sum(wn * (p - q) ** 2 for wn, p, q in zip(RBF_WNORM, point, n))) for n in nodes]
    idx = sorted(range(len(nodes)), key=lambda i: (d[i], i))[:RBF_N_WEI]
    inv = [1.0 / max(d[i], 1e-9) ** RBF_W_ORDER for i in idx]
    s = sum(inv)
    return idx, [v / s for v in inv]


def hinge_aero_torque(nodes, b, X, F, M, hinge_x) -> float:
    """Axial aerodynamic moment about the hinge point acting on the distal body of blade ``b``: loads
    sent to the coupling nodes rigidly attached to that body (one node on the hinge axis for
    split_rigid records, several static nodes for continuous_rbf)."""
    out = 0.0
    for i, nd in enumerate(nodes):
        if nd["blade"] == b and nd["segment"] == "distal":
            arm = [X[i][k] - hinge_x[k] for k in range(3)]
            out += M[i][2] + _cross(arm, F[i])[2]
    return out


def hinge_point(nodes, b, X, body_state) -> list[float]:
    """Hinge position: the distal body node lies on the hinge axis (exchanged state when it is itself a
    coupling node, else MBDyn's converged node state)."""
    for i, nd in enumerate(nodes):
        if nd["mbdyn_label"] == 200 + b:
            return X[i]
    return body_state["x"]


RESULT_FIXED_BYTES = 400_000  # request, decks, C81 text, definitions, checks (measured, with margin)


def estimated_bytes_per_window(case, n_coupling_nodes: int) -> int:
    """Conservative record bytes per accepted window, from measured per-item sizes of recorded runs
    plus ~10 % margin: exchanged loads/kinematics per coupling node, MBDyn states of ground, hub and
    body nodes, per-element radial rows, per-blade series/joint channels."""
    nb = case.geometry.blade_count
    return (450 * n_coupling_nodes + 320 * (2 + 2 * nb) + 260 * 2 * case.controls.elements_per_segment * nb
            + 600 * nb + 200)


def estimated_result_bytes(case, n_coupling_nodes: int) -> int:
    """Conservative size of a complete result record (JSON)."""
    return RESULT_FIXED_BYTES + case.n_steps * estimated_bytes_per_window(case, n_coupling_nodes)


def raw_manifest(run: Path) -> dict:
    files = {}
    for path in sorted(run.rglob("*")):
        if path.is_file() and path.name not in ("result.json", "status.json", "status.tmp"):
            rel = str(path.relative_to(run))
            files[rel] = {"bytes": path.stat().st_size, "sha256": _sha_file(path)}
    return files


def build_result(run: Path, *, participant_outcome: str | None, participant_message: str = "",
                 exit_codes: dict | None = None, extraction_ok: bool = True) -> dict:
    request = json.loads((run / "request.json").read_text())
    definition = json.loads((run / "run_definition.json").read_text())
    case = definition["case"]
    nodes = definition["coupling_nodes"]
    mech, geo = case["mechanics"], case["geometry"]
    dt, n_planned, W = case["dt_s"], case["n_steps"], case["omega_rad_s"]
    nb = geo["blade_count"]
    windows = []
    wlog = run / "structure" / "adapter_windows.jsonl"
    if wlog.is_file():
        windows = [json.loads(line) for line in wlog.read_text().splitlines() if line.strip()]
    iters = parse_precice_iterations(run / "structure" / "precice-MBDyn-iterations.log")
    mov = parse_mov(run / "structure" / "out.mov") if (run / "structure" / "out.mov").is_file() else []
    jnt = parse_jnt(run / "structure" / "out.jnt") if (run / "structure" / "out.jnt").is_file() else []
    steps = parse_out(run / "structure" / "out.out") if (run / "structure" / "out.out").is_file() else []
    dust = json.loads((run / "dust_extract.json").read_text()) if extraction_ok and (run / "dust_extract.json").is_file() else None
    dsteps = dust["steps"] if dust else []
    accepted = min(len(windows), max(0, len(mov) - 1), max(0, len(jnt) - 1), len(dsteps))
    envelope = request["c81"]["envelope"]
    rho, mu, a = case["density_kg_m3"], case["viscosity_pa_s"], case["speed_of_sound_m_s"]
    name_to_key = {dust["geometry"][k]["name"]: k for k in dust["geometry"]} if dust else {}
    jh = mech["distal_inertia_cg_kg_m2"] + mech["distal_mass_kg"] * mech["distal_cg_from_hinge_m"] ** 2
    kcf = mech["distal_mass_kg"] * W ** 2 * geo["hinge_radius_m"] * mech["distal_cg_from_hinge_m"]
    series, radial = [], []
    components = list(dict.fromkeys(nd["dust_component"] for nd in nodes))
    closure = {"kinematic_position_m": 0.0, "kinematic_rotation_rad": 0.0, "load_force_n": 0.0, "load_moment_nm": 0.0,
               "interface_power_w": 0.0, "max_node_force_n": 0.0, "max_node_moment_nm": 0.0, "max_interface_power_w": 0.0}
    first_uncovered = None
    for w in range(1, accepted + 1):
        win, blk, jb, ds = windows[w - 1], mov[w], jnt[w], dsteps[w - 1]
        t = w * dt
        row = {"window": w, "time_s": t, "coupling_iterations": win["iterations"]}
        row["rpm"] = blk[HUB]["w"][2] * 60.0 / (2 * math.pi)
        F = win["force"]; M = win["moment"]
        X, V, Om = win["position"], win["velocity"], win["angularvelocity"]
        row["thrust_n"] = sum(f[2] for f in F)
        m_origin_z = sum(M[i][2] + _cross(X[i], F[i])[2] for i in range(len(nodes)))
        row["aero_shaft_torque_nm"] = -m_origin_z
        p_if = sum(sum(F[i][k] * V[i][k] + M[i][k] * Om[i][k] for k in range(3)) for i in range(len(nodes)))
        row["aero_power_absorbed_w"] = -p_if
        row["drive_torque_nm"] = jb[DRIVE_JOINT]["m_global"][2]
        row["drive_power_w"] = row["drive_torque_nm"] * blk[HUB]["w"][2]
        theta, rate, m_aero_h, m_law, contact, latch_m = [], [], [], [], [], []
        for b in range(nb):
            rp, rd = rotvec_to_matrix(blk[100 + b]["phi"]), rotvec_to_matrix(blk[200 + b]["phi"])
            th = relative_angle_about_z(rp, rd)
            theta.append(th)
            rate.append(blk[200 + b]["w"][2] - blk[100 + b]["w"][2])
            m_aero_h.append(hinge_aero_torque(nodes, b, X, F, M, hinge_point(nodes, b, X, blk[200 + b])))
            m_law.append(-jb[SPRING_BASE + b]["m_local"][2])
            contact.append(th > mech["stop_angle_rad"] + CONTACT_TOL_RAD or th < mech["fold_limit_rad"] - CONTACT_TOL_RAD)
            # raw MBDyn output of the driven latch joint (zero once the driven element is inactive)
            latch_m.append(-jb[LATCH_BASE + b]["m_local"][2] if (LATCH_BASE + b) in jb else 0.0)
        # kinematic closure: state sent to DUST vs MBDyn's final converged state
        for i, nd in enumerate(nodes):
            lab = nd["mbdyn_label"]
            closure["kinematic_position_m"] = max(closure["kinematic_position_m"],
                                                  max(abs(X[i][k] - blk[lab]["x"][k]) for k in range(3)))
            closure["kinematic_rotation_rad"] = max(closure["kinematic_rotation_rad"],
                                                    max(abs(win["rotation"][i][k] - blk[lab]["phi"][k]) for k in range(3)))
        row["theta_deg"] = [math.degrees(x) for x in theta]
        row["theta_rate_rad_s"] = rate
        row["hinge_aero_torque_nm"] = m_aero_h
        row["hinge_law_torque_nm"] = m_law
        row["hinge_spring_torque_nm"] = [-mech["spring_nm_per_rad"] * (th - mech["spring_rest_rad"]) for th in theta]
        row["hinge_damping_torque_nm"] = [-mech["hinge_damping_nm_s_per_rad"] * r for r in rate]
        row["hinge_contact_torque_nm"] = [ml - sp - dp for ml, sp, dp in zip(m_law, row["hinge_spring_torque_nm"], row["hinge_damping_torque_nm"])]
        row["latch_torque_nm"] = latch_m
        # latched during at least part of this window (window spans t_{w-1}..t_w)
        row["latch_active"] = (t - dt) < mech["release_time_s"] - 1e-12
        row["contact_active"] = contact
        row["centrifugal_hinge_moment_derived_nm"] = [-kcf * math.sin(th) for th in theta]
        # aerodynamic coverage of the queried section states (final lifting-line iterate)
        lo = {"alpha": math.inf, "re": math.inf, "mach": math.inf}
        hi = {"alpha": -math.inf, "re": -math.inf, "mach": -math.inf}
        f_close = m_close = p_el = 0.0
        Rn = [rotvec_to_matrix(r) for r in win["rotation"]]
        for comp in components:
            key = name_to_key[comp]
            g, c = dust["geometry"][key], ds["components"][key]
            own = [i for i, nd in enumerate(nodes) if nd["dust_component"] == comp]
            fsum = {i: [0.0, 0.0, 0.0] for i in own}
            msum = {i: [0.0, 0.0, 0.0] for i in own}
            if len(own) > 1:  # continuous_rbf: DUST moves line points with nodal weights (mod_precice.f90)
                local = [nodes[i]["local"] for i in own]
                pts = []
                for p in g["ll_points_local"]:
                    idx, wts = rbf_weights(local, p)
                    pts.append([sum(wt * (X[own[j]][k] + _matvec(Rn[own[j]], [p[q] - local[j][q] for q in range(3)])[k])
                                    for j, wt in zip(idx, wts)) for k in range(3)])
            for e, (mid, chord) in enumerate(zip(g["element_mid_local"], g["element_chord"])):
                v2 = c["vel_2d"][e]
                al, re, ma = c["alpha_deg"][e], rho * v2 * chord / mu, v2 / a
                for k_, val in (("alpha", al), ("re", re), ("mach", ma)):
                    lo[k_] = min(lo[k_], val); hi[k_] = max(hi[k_], val)
                dF, dM = c["dF"][e], c["dMom"][e]
                if len(own) == 1:
                    i = own[0]
                    shares = [(i, 1.0, _matvec(Rn[i], [mid[k] - nodes[i]["local"][k] for k in range(3)]))]
                else:
                    # element centre = mean of its two line points; loads split with centre weights
                    cen = [0.5 * (pts[e][k] + pts[e + 1][k]) for k in range(3)]
                    idx, wts = rbf_weights(local, mid)
                    shares = [(own[j], wt, [cen[k] - X[own[j]][k] for k in range(3)]) for j, wt in zip(idx, wts)]
                for i, wt, arm in shares:
                    mom = _cross(arm, dF)
                    for k in range(3):
                        fsum[i][k] += wt * dF[k]; msum[i][k] += wt * (dM[k] + mom[k])
                    ve = [V[i][k] + _cross(Om[i], arm)[k] for k in range(3)]
                    p_el += wt * sum(dF[k] * ve[k] + dM[k] * Om[i][k] for k in range(3))
                segs = {nodes[i]["segment"] for i, _, _ in shares}
                cl, cd, cm = c["aero_coeff"][e]
                radial.append([w, nodes[own[0]]["blade"], segs.pop() if len(segs) == 1 else "junction", e, mid[1], chord,
                               al, re, ma, cl, cd, cm, dF[0], dF[1], dF[2]])
            for i in own:
                f_close = max(f_close, max(abs(fsum[i][k] - F[i][k]) for k in range(3)))
                m_close = max(m_close, max(abs(msum[i][k] - M[i][k]) for k in range(3)))
        closure["load_force_n"] = max(closure["load_force_n"], f_close)
        closure["load_moment_nm"] = max(closure["load_moment_nm"], m_close)
        closure["interface_power_w"] = max(closure["interface_power_w"], abs(p_el - p_if))
        closure["max_node_force_n"] = max(closure["max_node_force_n"], max(math.sqrt(sum(c * c for c in f)) for f in F))
        closure["max_node_moment_nm"] = max(closure["max_node_moment_nm"], max(math.sqrt(sum(c * c for c in m_)) for m_ in M))
        closure["max_interface_power_w"] = max(closure["max_interface_power_w"], abs(p_if))
        row["coverage"] = {"alpha_deg": [lo["alpha"], hi["alpha"]], "reynolds": [lo["re"], hi["re"]], "mach": [lo["mach"], hi["mach"]]}
        covered = (envelope["alpha_deg"][0] <= lo["alpha"] and hi["alpha"] <= envelope["alpha_deg"][1]
                   and envelope["reynolds"][0] <= lo["re"] and hi["re"] <= envelope["reynolds"][1]
                   and envelope["mach"][0] <= lo["mach"] and hi["mach"] <= envelope["mach"][1])
        row["within_admitted_table"] = covered
        if not covered and first_uncovered is None:
            first_uncovered = w
        series.append(row)
    # convergence per window from preCICE (authoritative)
    conv = {r["window"]: r for r in iters}
    first_unconverged = None
    for row in series:
        info = conv.get(row["window"])
        row["coupling_converged"] = bool(info and info["converged"] == 1)
        if not row["coupling_converged"] and first_unconverged is None:
            first_unconverged = row["window"]
    checks = _checks(series, case, closure, jh, dt)
    dust_abort = _dust_abort_reason(run)
    if participant_outcome in ("cancelled", "timeout"):
        status = participant_outcome
    elif participant_outcome != "finished":
        status = "failed_solver"
    elif first_unconverged is not None:
        status = "failed_unconverged_coupling"
    elif accepted < n_planned:
        status = "failed_incomplete"
    elif first_uncovered is not None:
        status = "failed_aero_coverage"
    else:
        status = "completed"
    valid_until = accepted
    for marker in (first_unconverged, first_uncovered):
        if marker is not None:
            valid_until = min(valid_until, marker - 1)
    execution = {"status": status, "participant_outcome": participant_outcome, "message": participant_message,
                 "dust_abort_reason": dust_abort, "exit_codes": exit_codes or {}, "windows_planned": n_planned,
                 "windows_accepted": accepted, "first_unconverged_window": first_unconverged,
                 "first_uncovered_window": first_uncovered, "valid_prefix_windows": valid_until,
                 "mbdyn_steps": len(steps), "mbdyn_max_newton_iterations": max((s["iterations"] for s in steps), default=None),
                 "mbdyn_termination_note": "MBDyn begins one step beyond the final coupling window and reports an "
                                           "interruption when the adapter closes; this is expected after a finished run.",
                 "dust_time_label_note": "DUST result k (0-based) is accepted window k+1; DUST's internal time label lags by dt."}
    radial_columns = ["window", "blade", "segment", "element", "span_y_m", "chord_m", "alpha_deg", "reynolds", "mach",
                      "cl", "cd", "cm", "dFx_n", "dFy_n", "dFz_n"]
    body = {
        "schema_version": SCHEMA_VERSION, "artifact_class": "pyfoldable_coupled_result", "model_id": MODEL_ID,
        "request": request, "run_definition": definition, "execution": execution,
        "series": series, "radial_columns": radial_columns, "radial": radial,
        "window_exchange": windows[:accepted],
        "joint_outputs": [{"window": w, "drive_m_global": jnt[w][DRIVE_JOINT]["m_global"],
                           "hinge_law_m_local": [jnt[w][SPRING_BASE + b]["m_local"] for b in range(nb)]}
                          for w in range(1, accepted + 1)],
        # ground, hub and body nodes; continuous_rbf coupling-node kinematics are in window_exchange
        "node_states": [{"window": w, "nodes": {str(lab): mov[w][lab] for lab in mov[w] if lab < COUPLING_NODE_LABEL_BASE}}
                        for w in range(0, accepted + 1)] if mov else [],
        "closure": closure, "checks": checks,
        "raw_outputs": {"run_id": run.name, "files": raw_manifest(run)},
        "physical_qualification": False, "reference_agreement": "NOT_ASSESSED", "joint_loss_model": "NOT_MODELED",
        "structural_stress": "NOT_SOLVED", "pressure_field": "NOT_SOLVED",
        "scope": ("Prescribed constant shaft speed; rigid proximal and distal segments; ideal in-plane revolute fold "
                  "hinge with declared spring/damper/penalty-stop law; DUST lifting line with retained provider tables. "
                  "Not CFD, not FEA, no joint strength or fatigue, no measured hardware properties unless declared."),
    }
    result = {**body, "result_sha256": digest(body)}
    tmp = run / "result.tmp"
    tmp.write_text(_json(result))
    tmp.replace(run / "result.json")
    return result


def _checks(series, case, closure, jh, dt) -> list[dict]:
    out = []
    ctrl = case["controls"]

    def add(name, value, limit, meaning):
        ok = value is not None and math.isfinite(value) and value <= limit
        out.append({"name": name, "value": value, "limit": limit, "passed": bool(ok), "meaning": meaning})

    add("kinematic_closure_position_m", closure["kinematic_position_m"], 10 * ctrl["coupling_position_tol_m"],
        "State sent to DUST vs MBDyn final converged state (finishing iterations after convergence).")
    rel = lambda a, b: a / b if b > 0 else a  # noqa: E731
    add("load_transfer_force_relative", rel(closure["load_force_n"], closure["max_node_force_n"]), 1e-3,
        "DUST element forces (final iterate) vs node forces used by MBDyn (Aitken-relaxed at convergence), "
        "relative to the largest node force.")
    add("load_transfer_moment_relative", rel(closure["load_moment_nm"], closure["max_node_moment_nm"]), 1e-3,
        "DUST element loads reduced independently about the displaced coupling node vs node moments used by MBDyn.")
    add("interface_power_closure_relative", rel(closure["interface_power_w"], closure["max_interface_power_w"]), 1e-3,
        "Power of element loads with rigid-body element velocities vs node F.v + M.w.")
    rpm = [r["rpm"] for r in series]
    if rpm:
        add("prescribed_speed_deviation_rpm", max(abs(x - case["rpm"]) for x in rpm), 1e-6 * case["rpm"],
            "Hub speed vs prescribed constant speed.")
    # hinge balance: J_h th'' = M_aero + M_law + M_centrifugal using central differences on smooth windows only
    res, scale, used = 0.0, 1e-12, 0
    contact_res, contact_scale = 0.0, 1e-12
    for i in range(1, len(series) - 1):
        r0, r1, r2 = series[i - 1], series[i], series[i + 1]
        if r0["latch_active"] or r1["latch_active"] or r2["latch_active"]:
            continue
        for b in range(len(r1["theta_deg"])):
            acc = (r2["theta_rate_rad_s"][b] - r0["theta_rate_rad_s"][b]) / (2 * dt)
            rhs = r1["hinge_aero_torque_nm"][b] + r1["hinge_law_torque_nm"][b] + r1["centrifugal_hinge_moment_derived_nm"][b]
            smooth = not (r0["contact_active"][b] or r1["contact_active"][b] or r2["contact_active"][b])
            mag = max(abs(rhs), abs(r1["centrifugal_hinge_moment_derived_nm"][b]), abs(r1["hinge_law_torque_nm"][b]),
                      abs(r1["hinge_aero_torque_nm"][b]))
            if smooth:
                res, scale, used = max(res, abs(jh * acc - rhs)), max(scale, mag), used + 1
            else:
                contact_res, contact_scale = max(contact_res, abs(jh * acc - rhs)), max(contact_scale, mag)
    if used:
        add("hinge_balance_relative_residual", res / scale, 0.05,
            "Independent planar hinge equation J_h th'' = M_aero + M_law - m W^2 r_h c_g sin(th), central differences, "
            "smooth windows only (no latch or contact in the stencil); a large value would indicate double-counted "
            "or missing inertial loads.")
    m = case["mechanics"]
    kcf = m["distal_mass_kg"] * case["omega_rad_s"] ** 2 * case["geometry"]["hinge_radius_m"] * m["distal_cg_from_hinge_m"]
    w_contact = math.sqrt((m["spring_nm_per_rad"] + m["stop_stiffness_nm_per_rad"] + kcf) / jh)
    out.append({"name": "contact_steps_per_half_period", "value": math.pi / (w_contact * dt), "limit": None, "passed": None,
                "meaning": "Diagnostic: time steps per half-period of the declared stop oscillator; below ~8 the contact "
                           "phase (and its hinge-balance residual) is under-resolved."})
    out.append({"name": "hinge_balance_contact_phase_relative_residual",
                "value": contact_res / contact_scale if contact_res else 0.0, "limit": None, "passed": None,
                "meaning": "Diagnostic only: same balance evaluated where the stencil touches contact (non-smooth law)."})
    return out


def summarize(result: dict) -> dict:
    s = result["series"]
    ex = result["execution"]
    valid = s[:ex["valid_prefix_windows"]]
    if not valid:
        return {"windows": 0}
    th = [r["theta_deg"][0] for r in valid]
    return {"windows": len(valid), "time_s": valid[-1]["time_s"],
            "theta_min_deg": min(th), "theta_max_deg": max(th),
            "thrust_final_n": valid[-1]["thrust_n"], "aero_torque_final_nm": valid[-1]["aero_shaft_torque_nm"],
            "max_contact": any(any(r["contact_active"]) for r in valid)}
