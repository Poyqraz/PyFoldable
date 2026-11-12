"""Deployment runs: events, hinge response, coverage, checks, loads (sealed records, restored)."""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "projects/PyFoldable"))
from pyfoldable.application import coupled_analysis as s  # noqa: E402
from pyfoldable.coupled import flow  # noqa: E402

root = Path.home() / "projects/PyFoldable"
runs = {"main_-5_const": "20261112T071200_20d4a1092d", "m20_const_2400": "20261112T191618_02b58b9c61",
        "m20_ramp_2200_2400": "20261112T203049_d66ad5cd8d", "m15_ramp_2200_2400": "20261112T203052_6971a5d10d"}
out = {}
for label, rid in runs.items():
    row = s.load_result(root / "outputs/coupled_runs" / rid)
    ex, case = row["execution"], row["run_definition"]["case"]
    v = row["series"][:ex["valid_prefix_windows"]]
    ev = flow.events(row)
    by = {r["window"]: r for r in v}
    rate = max(abs(r["theta_rate_rad_s"][0]) for r in v)
    i_peak = max(range(len(v)), key=lambda i: abs(v[i]["theta_rate_rad_s"][0]))
    peak = v[i_peak]
    W_peak = peak["rpm"] * math.pi / 30
    cov = {q: [min(r["coverage"][q][0] for r in v), max(r["coverage"][q][1] for r in v)] for q in ("alpha_deg", "reynolds", "mach")}
    fc = by.get(ev.get("first_contact"))
    nrev = int(round(2 * math.pi / (case["omega_rad_s"] * case["dt_s"])))
    last = v[-nrev:]
    lat = [r for r in v if r["latch_active"]][-nrev:]
    d = {"run_id": rid, "status": ex["status"], "windows": ex["windows_accepted"], "valid": ex["valid_prefix_windows"],
         "events": ev, "max_fold_rate_rad_s": rate, "fold_rate_over_shaft_speed_at_peak": abs(peak["theta_rate_rad_s"][0]) / W_peak,
         "impact_rate_at_first_contact_rad_s": fc["theta_rate_rad_s"][0] if fc else None,
         "time_release_to_contact_ms": (fc["time_s"] - by[ev["release"]]["time_s"]) * 1000 if fc else None,
         "theta_max_deg": max(max(r["theta_deg"]) for r in v), "second_swing_min_deg": by[ev["second_swing_min"]]["theta_deg"][0] if "second_swing_min" in ev else None,
         "theta_final_deg": v[-1]["theta_deg"][0], "coverage": cov,
         "thrust_last_latched_rev_n": sum(r["thrust_n"] for r in lat) / len(lat) if lat else None,
         "thrust_last_rev_n": sum(r["thrust_n"] for r in last) / len(last),
         "aero_torque_last_rev_nm": sum(r["aero_shaft_torque_nm"] for r in last) / len(last),
         "drive_torque_last_rev_nm": sum(r["drive_torque_nm"] for r in last) / len(last),
         "peak_thrust_n": max(r["thrust_n"] for r in v[ (ev.get("release",1)-1):]),
         "peak_drive_torque_abs_nm": max(abs(r["drive_torque_nm"]) for r in v[(ev.get("release",1)-1):]),
         "rpm_range": [min(r["rpm"] for r in v), max(r["rpm"] for r in v)],
         "checks": {c["name"]: c["value"] for c in row["checks"]},
         "fold_envelope_deg": ex.get("fold_envelope", {}).get("fold_limit_deg")}
    out[label] = d
    print(f"\n{label} {rid}: {d['status']} {d['valid']}/{d['windows']} events {ev}")
    print(f"  max theta_dot {rate:.1f} rad/s (theta_dot/Omega {d['fold_rate_over_shaft_speed_at_peak']:.2f}), impact {d['impact_rate_at_first_contact_rad_s']}, "
          f"release->contact {d['time_release_to_contact_ms']} ms, theta max {d['theta_max_deg']:.2f}, second swing {d['second_swing_min_deg']}, final {d['theta_final_deg']:.2f}")
    print(f"  coverage alpha {cov['alpha_deg'][0]:.2f}..{cov['alpha_deg'][1]:.2f} Re {cov['reynolds'][0]:.0f}..{cov['reynolds'][1]:.0f} Mach max {cov['mach'][1]:.4f}; rpm {d['rpm_range'][0]:.1f}..{d['rpm_range'][1]:.1f}")
    print(f"  thrust latched rev {d['thrust_last_latched_rev_n']}, last rev {d['thrust_last_rev_n']:.3f} N, Qaero {d['aero_torque_last_rev_nm']:.4f}, Qdrive {d['drive_torque_last_rev_nm']:.4f}; "
          f"peak thrust after release {d['peak_thrust_n']:.2f} N, peak |Qdrive| {d['peak_drive_torque_abs_nm']:.1f}")
    print("  checks", {k: (round(x, 9) if isinstance(x, float) else x) for k, x in d["checks"].items()})
json.dump(out, open(sys.argv[1], "w"), indent=1)
