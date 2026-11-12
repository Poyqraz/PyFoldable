"""Independent hinge balance of a ramp run with and without the rotating-frame acceleration term
-(J_h + m r_h c_g cos th) dOmega/dt (smooth windows: no latch or contact in the stencil)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "projects/PyFoldable"))
from pyfoldable.application import coupled_analysis as s  # noqa: E402

row = s.load_result(Path.home() / "projects/PyFoldable/outputs/coupled_runs" / sys.argv[1])
m = row["run_definition"]["case"]["mechanics"]
jh = m["distal_inertia_cg_kg_m2"] + m["distal_mass_kg"] * m["distal_cg_from_hinge_m"] ** 2
dt, ser = row["run_definition"]["case"]["dt_s"], row["series"]


def resid(with_frame, ramp_only):
    res = scale = 0.0
    n = 0
    for i in range(1, len(ser) - 1):
        r0, r1, r2 = ser[i - 1], ser[i], ser[i + 1]
        if any(r["latch_active"] or any(r["contact_active"]) for r in (r0, r1, r2)):
            continue
        if ramp_only and abs(r1["frame_acceleration_hinge_moment_derived_nm"][0]) < 1e-6:
            continue
        acc = (r2["theta_rate_rad_s"][0] - r0["theta_rate_rad_s"][0]) / (2 * dt)
        rhs = (r1["hinge_aero_torque_nm"][0] + r1["hinge_law_torque_nm"][0] + r1["centrifugal_hinge_moment_derived_nm"][0]
               + (r1["frame_acceleration_hinge_moment_derived_nm"][0] if with_frame else 0.0))
        res = max(res, abs(jh * acc - rhs))
        scale = max(scale, abs(rhs), abs(r1["centrifugal_hinge_moment_derived_nm"][0]), abs(r1["hinge_aero_torque_nm"][0]))
        n += 1
    return res / scale, n


print("run", sys.argv[1])
print("max |frame-acceleration hinge moment| %.3f N m" % max(abs(r["frame_acceleration_hinge_moment_derived_nm"][0]) for r in ser))
print("max |aerodynamic hinge moment| after release %.3f N m" % max(abs(r["hinge_aero_torque_nm"][0]) for r in ser if not r["latch_active"]))
for ramp_only in (False, True):
    a, n = resid(True, ramp_only)
    b, _ = resid(False, ramp_only)
    print(f"{'ramp windows' if ramp_only else 'all smooth windows'} (n={n}): residual with frame term {a:.4f}, without {b:.4f}")
