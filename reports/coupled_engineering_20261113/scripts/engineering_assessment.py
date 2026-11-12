"""Engineering reading of the retained deployment records (sealed records restored; no solver).

For each run: contact events (impact rate and energy against the centrifugal bound, impulse balance
over the contact, apparent restitution, peak stop torque against the undamped penalty estimate), the
shaft angular-momentum exchange and the output classes of pyfoldable.coupled.assessment. Then the
analytic sensitivities of the deployment outputs to each mechanical input at the declared values, and
the fold limits of the aerodynamic representation for other tolerances. Usage: <out.json> > <out.txt>
"""
import json
import math
import sys
from pathlib import Path

root = Path.home() / "projects/PyFoldable"
sys.path.insert(0, str(root))
from pyfoldable.application import coupled_analysis as svc  # noqa: E402
from pyfoldable.coupled import assessment, envelope  # noqa: E402

RUNS = {"-5 deg, 2400 RPM": "20261112T071200_20d4a1092d",
        "-20 deg, 2400 RPM (stopped, retained table)": "20261112T191618_02b58b9c61",
        "-15 deg, ramp 2200->2400": "20261112T203052_6971a5d10d",
        "-20 deg, ramp 2200->2400": "20261112T203049_d66ad5cd8d",
        "-22.5 deg, 2400 RPM (deploy-v3)": "20261112T220252_1f1a7bf962",
        "-20 deg, ramp 1600->2400 (deploy-v3)": "20261112T220255_14fc6eaab8",
        "-20 deg, ramp 2200->2400 control (deploy-v3)": "20261112T220258_0bb5c02ad8"}

out = {"runs": {}}
case_dict = None
for label, rid in RUNS.items():
    row = svc.load_result(root / "outputs/coupled_runs" / rid)
    case_dict = case_dict or row["run_definition"]["case"]
    ev = assessment.contact_events(row)
    sh = assessment.shaft_exchange(row)
    out["runs"][label] = {"run_id": rid, "status": row["execution"]["status"], "contact_events": ev, "shaft_exchange": sh,
                          "pointwise_contact_residual": next((c["value"] for c in row["checks"]
                                                              if c["name"] == "hinge_balance_contact_phase_relative_residual"), None),
                          "outputs": assessment.output_classes(row)}
    print(f"\n{label} ({rid}, {row['execution']['status']})")
    for e in ev[:1]:
        print(f"  impact {e['impact_rate_rad_s']:.1f} rad/s, energy {e['impact_energy_j']:.3f} J = {e['energy_ratio']:.3f} x bound "
              f"{e['centrifugal_energy_bound_j']:.3f} J; release->contact {e['release_to_contact_s'] * 1000:.2f} ms; "
              f"restitution {e['apparent_restitution']:.3f} (declared {e['declared_restitution']})")
        print(f"  impulse balance over contact {e['impulse_balance_relative_residual']:.4f} (pointwise contact-phase "
              f"{out['runs'][label]['pointwise_contact_residual']:.3f}); peak stop torque {e['peak_stop_torque_nm']:.2f} N m "
              f"= {e['peak_stop_torque_nm'] / e['penalty_peak_estimate_nm']:.3f} x undamped estimate")
    if sh:
        print(f"  shaft: net impulse {sh['angular_impulse_n_m_s']:.4f} N m s vs distal momentum change "
              f"{sh['distal_momentum_change_n_m_s']:.4f} (residual {sh['momentum_balance_relative_residual']:.4f}, speed change "
              f"{sh['speed_change_rpm']:.2f} RPM) over {sh['exchange_duration_s'] * 1000:.2f} ms; mean {sh['equivalent_mean_torque_nm']:.1f} "
              f"N m, peak {sh['peak_drive_torque_nm']:.1f} N m (peak x duration / impulse "
              f"{sh['peak_drive_torque_nm'] * sh['exchange_duration_s'] / abs(sh['angular_impulse_n_m_s']):.2f})")
    if not ev:
        print("  no finished stop contact in the valid prefix")

# analytic sensitivities at the declared (demonstration) values: d ln(output) / d ln(input)
m = case_dict["mechanics"]
M, c, Jcg, k, e = (m["distal_mass_kg"], m["distal_cg_from_hinge_m"], m["distal_inertia_cg_kg_m2"],
                   m["stop_stiffness_nm_per_rad"], m["stop_restitution"])
rh = case_dict["geometry"]["hinge_radius_m"]
Jh = Jcg + M * c * c
fm, fj = M * c * c / Jh, Jcg / Jh          # shares of J_h
lever = Jh + M * rh * c
sens = {
    "impact_energy (= eta m c_g W^2 r_h (1 - cos th0))": {"mass": 1.0, "cg": 1.0, "inertia_cg": 0.0, "stop_stiffness": 0.0,
                                                           "restitution": 0.0, "shaft_speed": 2.0},
    "impact_rate (sqrt(2E/J_h))": {"mass": 0.5 * (1 - fm), "cg": 0.5 * (1 - 2 * fm), "inertia_cg": -0.5 * fj,
                                   "stop_stiffness": 0.0, "restitution": 0.0, "shaft_speed": 1.0},
    "release_to_contact_time (~ sqrt(J_h/(m r_h c_g))/W)": {"mass": -0.5 * (1 - fm), "cg": -0.5 * (1 - 2 * fm),
                                                            "inertia_cg": 0.5 * fj, "stop_stiffness": 0.0, "restitution": 0.0,
                                                            "shaft_speed": -1.0},
    "peak_stop_torque (~ sqrt(2 E k) f(e))": {"mass": 0.5, "cg": 0.5, "inertia_cg": 0.0, "stop_stiffness": 0.5,
                                              "restitution": "f(e): damping set from e", "shaft_speed": 1.0},
    "shaft_angular_impulse (~ (1+e)(J_h + m r_h c_g) th_dot)": {
        "mass": (M * c * c + M * rh * c) / lever + 0.5 * (1 - fm), "cg": (2 * M * c * c + M * rh * c) / lever + 0.5 * (1 - 2 * fm),
        "inertia_cg": Jcg / lever - 0.5 * fj, "stop_stiffness": 0.0, "restitution": e / (1 + e), "shaft_speed": 1.0},
}
out["mechanics_sensitivity"] = {"declared": {"mass_kg": M, "cg_m": c, "inertia_cg_kg_m2": Jcg, "J_h_kg_m2": Jh,
                                             "stop_stiffness_nm_per_rad": k, "restitution": e, "hinge_radius_m": rh},
                                "share_of_J_h_from_m_cg2": fm, "elasticities": sens,
                                "note": "Log-derivatives of the scaling laws at the declared values; eta = energy ratio "
                                        "observed in the runs. Friction is not modelled: a hinge friction moment M_f removes "
                                        "about M_f |th0| of impact energy."}
etas = [r["contact_events"][0]["energy_ratio"] for r in out["runs"].values() if r["contact_events"]]
out["mechanics_sensitivity"]["observed_eta_range"] = [min(etas), max(etas)]
print("\nSensitivities d ln(output)/d ln(input) at declared values (J_h share from m c_g^2: %.2f):" % fm)
for name, s in sens.items():
    print(" ", name, {kk: (round(v, 2) if isinstance(v, float) else v) for kk, v in s.items()})
print(f"  observed energy ratio eta {min(etas):.3f}..{max(etas):.3f}")

# fold limits of the aerodynamic representation for other tolerances (geometry only)
chord = {f"{tol:.2f}": -math.degrees(2 * math.acos(1 - tol)) for tol in (0.02, 0.05, 0.10)}
sweep = {}
for lim in (25.0, 35.0, 45.0):
    th = next((-0.1 * i for i in range(1, 901) if envelope.distal_sweep_deg(case_dict, math.radians(-0.1 * i)) > lim), -90.0)
    sweep[f"{lim:.0f}"] = th + 0.1
at = {f"{f}": {"junction_chord": envelope.junction_chord_bound(math.radians(f)),
               "distal_sweep_deg": envelope.distal_sweep_deg(case_dict, math.radians(f))} for f in (-23, -30, -45, -60, -90)}
out["fold_representation_limits"] = {"chord_tolerance_to_fold_deg": chord, "sweep_limit_to_fold_deg": sweep, "at_fold": at}
print("\nFold limit of the representation: chord tolerance -> fold", {kk: round(v, 1) for kk, v in chord.items()},
      "; sweep limit -> fold", {kk: round(v, 1) for kk, v in sweep.items()})
for f, d in at.items():
    print(f"  fold {f} deg: junction chord {100 * d['junction_chord']:.1f} %, mid-distal sweep {d['distal_sweep_deg']:.1f} deg")
json.dump(out, open(sys.argv[1], "w"), indent=1)
