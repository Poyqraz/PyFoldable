"""Build the compact review package reports/coupled_closure_20261112/ from local raw outputs.

Only extracted evidence, manifests, digests, scripts and one sealed compressed record enter Git;
raw run directories (0.2-0.8 GB each) stay local under outputs/coupled_runs and ~/pyf-work.
Run with the coupling venv (h5py): ~/pyf-work/opt/coupling-venv/bin/python make_review_package.py
"""
import csv
import glob
import gzip
import hashlib
import json
import math
import shutil
from pathlib import Path

import h5py
import numpy as np

HOME = Path.home()
REPO = HOME / "projects/PyFoldable"
RUNS = REPO / "outputs/coupled_runs"
W = HOME / "pyf-work"
OUT = REPO / "reports/coupled_closure_20261112"
OMEGA = 251.32741228718345


def redact(obj):
    if isinstance(obj, str):
        return obj.replace(str(HOME), "~")
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    return obj


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(rel, obj):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(redact(obj), indent=1, sort_keys=True) + "\n", encoding="utf-8")


def record(rid):
    return json.loads((RUNS / rid / "result.json").read_text())


def window_stats(rid, a, b):
    r = record(rid)
    s = [x for x in r["series"] if a <= x["window"] <= b]
    c = r["run_definition"]["case"]
    n = len(s)

    def m(k):
        return sum(x[k] for x in s) / n
    return {"run_id": rid, "result_sha256": r["result_sha256"], "topology": c["controls"].get("aero_topology", "split_rigid (legacy record)"),
            "azimuth_step_deg": c["controls"]["azimuth_step_deg"], "elements_per_segment": c["controls"]["elements_per_segment"],
            "windows": [a, b], "time_s": [round(s[0]["time_s"] - c["dt_s"], 6), round(s[-1]["time_s"], 6)],
            "revolutions": round(n * c["dt_s"] * c["omega_rad_s"] / (2 * math.pi), 4),
            "thrust_n": m("thrust_n"), "aero_shaft_torque_nm": m("aero_shaft_torque_nm"), "drive_torque_nm": m("drive_torque_nm"),
            "aero_power_w": m("aero_power_absorbed_w"), "drive_power_w": m("drive_power_w"),
            "theta_deg_range": [min(x["theta_deg"][0] for x in s), max(x["theta_deg"][0] for x in s)]}


# ---------------------------------------------------------------- toolchain and environment binding
if OUT.exists():
    shutil.rmtree(OUT)
pre = W / "coupled_toolchain.pre-ubuntu-upgrade-20261112.json"
post = HOME / ".pyfoldable/coupled_toolchain.json"
dump("toolchain/manifest_pre_upgrade.json", json.loads(pre.read_text()))
dump("toolchain/manifest_post_upgrade.json", json.loads(post.read_text()))
P, Q = json.loads(pre.read_text()), json.loads(post.read_text())
binding = {"note": ("Each run is bound to the manifest it copied at start (toolchain.json in its run directory). "
                    "Ubuntu unattended upgrades: libgfortran5 12.3.0-1ubuntu1~22.04.3 installed 2026-11-12 06:58:13, "
                    "python3.10 3.10.12-1~22.04.12 -> ~22.04.18 at 06:59:49-50 (/var/log/dpkg.log). The manifest hashes the "
                    "coupling interpreter, solvers and libprecice, not system libraries such as libgfortran5. Readiness failed "
                    "closed (toolchain_invalid) until re-attestation at 07:06:37. No cited run spans 06:58-07:06."),
           "manifest_pre_upgrade_sha256": sha(pre), "manifest_post_upgrade_sha256": sha(post),
           "manifest_difference": {k: [P["executables_sha256"][k], Q["executables_sha256"][k]]
                                   for k in P["executables_sha256"] if P["executables_sha256"][k] != Q["executables_sha256"][k]},
           "coupled_runs": [], "standalone_runs": []}
for d in sorted(RUNS.iterdir()):
    t = d / "toolchain.json"
    if not t.is_file():
        continue
    tj = json.loads(t.read_text())
    env = "pre_upgrade" if tj == P else ("post_upgrade" if tj == Q else "other")
    end = (d / "status.json").stat().st_mtime if (d / "status.json").is_file() else None
    row = {"run_id": d.name, "environment": env, "started": d.name[:15]}
    if end:
        import datetime
        row["ended_local"] = datetime.datetime.fromtimestamp(end).strftime("%Y%m%dT%H%M%S")
    if (d / "result.json").is_file():
        r = json.loads((d / "result.json").read_text())
        row.update({"status": r["execution"]["status"], "windows_accepted": r["execution"]["windows_accepted"],
                    "result_sha256": r["result_sha256"],
                    "topology": r["run_definition"]["case"]["controls"].get("aero_topology", "split_rigid (legacy record)")})
    binding["coupled_runs"].append(row)
import datetime
for name, d, binary in (("sa_n2412_s5_d150 (split, stock standalone)", W / "runs/sa_n2412_s5_d150/dust", "opt/dust-3b1d2e61-standalone/bin/dust"),
                        ("sa_cont_s5_d150 (continuous, stock standalone)", W / "runs/sa_cont_s5_d150/dust", "opt/dust-3b1d2e61-standalone/bin/dust"),
                        ("sa_cont_s5_d150_ubcen (continuous, DIAGNOSTIC build)", W / "diag/runs/sa_cont_s5_d150_ubcen", "diag/opt/dust-ubcen/bin/dust")):
    outs = sorted(glob.glob(str(d / "Output/run_res_*.h5")))
    t0 = datetime.datetime.fromtimestamp(Path(outs[0]).stat().st_mtime)
    t1 = datetime.datetime.fromtimestamp(Path(outs[-1]).stat().st_mtime)
    pkg = "pre_upgrade" if t1 < datetime.datetime(2026, 11, 12, 6, 58) else (
        "post_upgrade" if t0 > datetime.datetime(2026, 11, 12, 7, 0) else "SPANS_UPGRADE")
    binding["standalone_runs"].append({"run": name, "first_output": t0.strftime("%H:%M:%S"), "last_output": t1.strftime("%H:%M:%S"),
                                       "system_libraries": pkg, "binary_sha256": sha(W / binary),
                                       "geo_input_sha256": sha(d / "geo_input.h5"), "dust_in_sha256": sha(d / "dust.in")})
dump("toolchain/run_environment_binding.json", binding)
import filecmp
A_, B_ = RUNS / "20261112T004422_676d3c8c65", RUNS / "20261112T070700_c891c455ae"
ra, rb = record(A_.name), record(B_.name)
h5a = sorted((A_ / "dust/Output").glob("run_res_*.h5"))
dump("toolchain/replay_comparison.json", {
    "before_upgrade": A_.name, "after_upgrade": B_.name,
    "byte_identical_files": {f: filecmp.cmp(A_ / f, B_ / f, shallow=False) for f in (
        "structure/adapter_windows.jsonl", "structure/out.mov", "structure/out.jnt", "structure/out.out", "dust_extract.json")},
    "dust_hdf5_results_byte_identical": sum(filecmp.cmp(f, B_ / "dust/Output" / f.name, shallow=False) for f in h5a),
    "dust_hdf5_results_total": len(h5a),
    "record_sections_equal": {k: ra[k] == rb[k] for k in ("window_exchange", "node_states", "joint_outputs", "radial",
                                                          "series", "checks", "closure")},
    "series_fields_differing": sorted({k for x, y in zip(ra["series"], rb["series"]) for k in x if x[k] != y.get(k)}),
    "request_keys_differing": sorted(k for k in ra["request"] if ra["request"][k] != rb["request"].get(k)),
    "deck_files_differing": sorted(k for k in set(ra["request"]["deck"]["files"]) | set(rb["request"]["deck"]["files"])
                                   if ra["request"]["deck"]["files"].get(k) != rb["request"]["deck"]["files"].get(k)),
    "notes": ("preCICE configuration differs by an XML comment only; contact_active and checks differ because "
              "post-processing (contact round-off tolerance, relative closure checks) changed between the runs; HDF5 files "
              "differ in file metadata while dust_extract.json (all extracted per-element data) is byte-identical")})

# ---------------------------------------------------------------- topology control
dump("topology_control/per_revolution_means.json", {
    "question": "Does a static, latched fold (no hinge motion) change thrust? Two-line layout vs continuous line.",
    "split_rigid_static_minus_0p5deg": [window_stats("20261112T064948_aba91dea80", a, a + 71) for a in (1, 73, 145, 217, 289)],
    "split_rigid_open_reference_5deg": [window_stats("20261112T004422_676d3c8c65", a, a + 71) for a in (1, 73, 145, 217, 289, 361)],
    "continuous_rbf_static_minus_0p5deg": [window_stats("20261112T070917_55f6aea26f", a, a + 71) for a in (1, 73, 145)],
    "continuous_rbf_open_same_duration": [window_stats("20261112T070920_67c85e4108", a, a + 71) for a in (1, 73, 145)],
})

# ---------------------------------------------------------------- RBF discrepancy evidence
SA = W / "runs/sa_cont_s5_d150/dust"
UB = W / "diag/runs/sa_cont_s5_d150_ubcen"
CP = RUNS / "20261112T073117_fab3a9a152/dust"
SAS = W / "runs/sa_n2412_s5_d150/dust"
CPS = RUNS / "20261112T004422_676d3c8c65/dust"


def elements(d, k, comp="Comp001"):
    fn = sorted(glob.glob(str(d / "Output/run_res_*.h5")))[k]
    with h5py.File(fn, "r") as f:
        s = f[f"Components/{comp}/Solution"]
        out = {"file": Path(fn).name, "time_label_s": float(np.array(f["time"]))}
        for n in ("alpha", "vel_2d", "vel_outplane", "up_x", "up_y", "Gamma_old"):
            out[n] = np.array(s[n]).tolist()
        out["cl"] = np.array(s["aero_coeff"])[0].tolist()
        out["dFz"] = np.array(s["dF"])[:, 2].tolist()
        g = f.get(f"Components/{comp}/Geometry/rr")
        out["geometry_rr_written"] = None if g is None else np.array(g).tolist()
    return out


with h5py.File(SA / "geo_input.h5", "r") as g:
    rr0 = np.array(g["Components/Comp001/Geometry/rr"])
line = rr0[0::2]
r_mid = np.linalg.norm(0.5 * (line[:-1, :2] + line[1:, :2]), axis=1).tolist()
dump("rbf_discrepancy/element_states.json", {
    "element_mid_radius_m": r_mid,
    "runs": {"standalone_stock": str(SA), "standalone_diagnostic_ub_at_leading_line": str(UB), "coupled_rbf_locked_open": str(CP),
             "standalone_stock_split": str(SAS), "coupled_rigid_split_locked_open": str(CPS)},
    "index_0": {k: elements(d, 0) for k, d in (("standalone_stock", SA), ("standalone_diagnostic", UB), ("coupled_rbf", CP))},
    "index_300": {k: elements(d, 300) for k, d in (("standalone_stock", SA), ("standalone_diagnostic", UB), ("coupled_rbf", CP),
                                                     ("standalone_stock_split", SAS), ("coupled_rigid_split", CPS))},
})


def loads(d, off):
    with h5py.File(d / "geo_input.h5", "r") as g:
        comps = sorted(k for k in g["Components"] if k.startswith("Comp"))
        ref = {c: (np.array(g[f"Components/{c}/Geometry/rr"]), np.array(g[f"Components/{c}/Geometry/ee"]) - 1) for c in comps}
    rows = []
    for fn in sorted(glob.glob(str(d / "Output/run_res_*.h5"))):
        with h5py.File(fn, "r") as f:
            t = float(np.array(f["time"]))
            T = Q = 0.0
            for i, c in enumerate(comps):
                s = f[f"Components/{c}/Solution"]
                dF, dM = np.array(s["dF"]), np.array(s["dMom"])
                g = f.get(f"Components/{c}/Geometry/rr")
                if g is not None:
                    rr = np.array(g)
                else:
                    p = OMEGA * t + math.pi * i
                    rr = ref[c][0] @ np.array([[math.cos(p), -math.sin(p), 0], [math.sin(p), math.cos(p), 0], [0, 0, 1]]).T
                ee = ref[c][1]
                cen = 0.5 * (rr[ee[:, 0]] + rr[ee[:, 1]])
                T += dF[:, 2].sum()
                Q += -(np.cross(cen, dF)[:, 2].sum() + dM[:, 2].sum())
        rows.append((t, T, Q))
    return rows


L = {k: loads(d, 0) for k, d in (("standalone_stock", SA), ("standalone_diagnostic", UB), ("coupled_rbf", CP))}
p = OUT / "rbf_discrepancy/rotor_loads_per_output.csv"
with p.open("w", newline="") as fh:
    wr = csv.writer(fh)
    wr.writerow(["index", "time_label_s", *[f"{k}_{q}" for k in L for q in ("thrust_n", "torque_nm")]])
    for i in range(min(len(v) for v in L.values())):
        wr.writerow([i, f"{L['standalone_stock'][i][0]:.8f}", *[f"{L[k][i][j]:.6f}" for k in L for j in (1, 2)]])
means = {}
for k, v in L.items():
    for nrev in (1, 2):
        sl = v[-72 * nrev:]
        means[f"{k}_last_{nrev}_rev"] = {"thrust_n": sum(x[1] for x in sl) / len(sl), "torque_nm": sum(x[2] for x in sl) / len(sl),
                                         "power_w": OMEGA * sum(x[2] for x in sl) / len(sl), "outputs": len(sl)}
dump("rbf_discrepancy/matched_means.json", {
    "conditions": "NACA2412, 800 mm template, 2400 RPM, 14 m/s axial, 5 deg azimuth step, 16 lifting-line elements per blade, "
                  "6 revolutions (0.15 s), identical geo_input.h5 and dust.in (sha256 in toolchain/run_environment_binding.json); "
                  "loads from DUST's own result files with one arithmetic for all runs (coupled values reproduce the sealed "
                  "record's thrust/aero torque to within 1e-7 relative)",
    "means": means})
shutil.copy(W / "diag/dust-ubcen.patch", OUT / "rbf_discrepancy/dust-ubcen.diagnostic.patch")

# geometry/timing and node velocity
psi = []
fs = sorted(glob.glob(str(CP / "Output/run_res_*.h5")))
dt = math.radians(5) / OMEGA
for k in (0, 20, 100, 200, 300, 431):
    with h5py.File(fs[k], "r") as f:
        rr = np.array(f["Components/Comp001/Geometry/rr"])
    i = len(rr) - 2
    ps = math.atan2(rr[i, 1], rr[i, 0]) - math.atan2(rr0[i, 1], rr0[i, 0])
    c, s_ = math.cos(ps), math.sin(ps)
    resid = float(np.abs(rr - rr0 @ np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]]).T).max())
    psi.append({"result_index": k, "time_label_s": k * dt, "psi_fit_deg": math.degrees(ps) % 360,
                "psi_minus_Omega_window_time_deg": (math.degrees(ps - OMEGA * (k + 1) * dt) + 180) % 360 - 180,
                "rigid_fit_residual_m": resid})
vel = {}
for rid, sl in (("20261112T073117_fab3a9a152", slice(10, None, 7)), ("20261112T071200_20d4a1092d", slice(10, 280, 5)),
                ("20261112T004422_676d3c8c65", slice(10, None, 7))):
    r = record(rid)
    rat = []
    for w in r["window_exchange"][sl]:
        X, V = np.array(w["position"]), np.array(w["velocity"])
        Ve = np.cross(np.array([0, 0, OMEGA]), X)
        m = np.linalg.norm(X[:, :2], axis=1) > 0.05
        rat += list(np.linalg.norm(V[m], axis=1) / np.linalg.norm(Ve[m], axis=1) - 1)
    vel[rid] = {"azimuth_step_deg": r["run_definition"]["case"]["controls"]["azimuth_step_deg"],
                "node_speed_over_Omega_r_minus_1": [min(rat), float(np.mean(rat)), max(rat)],
                "windows": "rigid (locked/latched) windows only"}
dump("rbf_discrepancy/geometry_timing_velocity.json", {"coupled_rbf_geometry_vs_reference": psi, "mbdyn_node_velocity": vel})

# spacing sensitivity
runs = {"1.0": "20261112T104303_5d5d234081", "0.5": "20261112T104306_fc454dbf5a", "2.0": "20261112T104309_3578a648d8"}
R = {k: record(v) for k, v in runs.items()}
base = R["1.0"]["series"]
sens = {"case": "release from -5 deg at 0.01 s, 2.5 deg steps, 259 windows, 8 elements per segment (fixed); "
                "node spacing scaled by a diagnostic-only driver override (records do not restore by design)",
        "runs": {k: {"run_id": runs[k], "coupling_nodes": len(R[k]["run_definition"]["coupling_nodes"]),
                     "status": R[k]["execution"]["status"], "closure": R[k]["closure"]} for k in runs}, "vs_default": {}}
for k in ("0.5", "2.0"):
    s = R[k]["series"]
    sens["vs_default"][k] = {
        "max_abs_dtheta_deg": max(abs(a["theta_deg"][0] - c["theta_deg"][0]) for a, c in zip(s, base)),
        "max_abs_dthrust_n": max(abs(a["thrust_n"] - c["thrust_n"]) for a, c in zip(s, base)),
        "max_abs_dthrust_latched_n": max(abs(a["thrust_n"] - c["thrust_n"]) for a, c in zip(s[:57], base[:57])),
        "max_abs_daero_torque_nm": max(abs(a["aero_shaft_torque_nm"] - c["aero_shaft_torque_nm"]) for a, c in zip(s, base)),
        "max_abs_dhinge_aero_moment_nm": max(abs(a["hinge_aero_torque_nm"][0] - c["hinge_aero_torque_nm"][0]) for a, c in zip(s, base)),
        "max_abs_hinge_aero_moment_default_nm": max(abs(c["hinge_aero_torque_nm"][0]) for c in base),
        "last_rev_mean_thrust_rel": sum(x["thrust_n"] for x in s[-144:]) / sum(x["thrust_n"] for x in base[-144:]) - 1}
dump("spacing_sensitivity/summary.json", sens)

# ---------------------------------------------------------------- current release case
main = "20261112T071200_20d4a1092d"
r = record(main)
(OUT / "release_case").mkdir(parents=True, exist_ok=True)
plain = (json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()
(OUT / "release_case" / f"{main}.json.gz").write_bytes(gzip.compress(plain, compresslevel=6, mtime=0))
import lzma  # same parameters as coupled_analysis.record_xz_bytes (fits the 5 MiB upload limit)
(OUT / "release_case" / f"{main}.json.xz").write_bytes(
    lzma.compress(plain, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=6))
dump("release_case/summary.json", {
    "run_id": main, "result_sha256": r["result_sha256"], "status": r["execution"]["status"],
    "windows": r["execution"]["windows_accepted"],
    "case": {k: r["run_definition"]["case"][k] for k in ("dt_s", "n_steps", "omega_rad_s")},
    "mechanics": r["request"]["mechanics"], "controls": r["run_definition"]["case"]["controls"],
    "averaging_windows": {
        "last_latched_rev_minus5deg": window_stats(main, 145, 288),
        "rev1_after_release": window_stats(main, 289, 432),
        "rev2_after_release": window_stats(main, 433, 576),
        "rev3_after_release_last": window_stats(main, 577, 720)},
    "locked_open_coupled_5deg_last_rev": window_stats("20261112T073117_fab3a9a152", 361, 432),
    "release_5deg_last_rev": window_stats("20261112T071157_91efdf9841", 289, 360)})

# ---------------------------------------------------------------- scripts
for s_ in ("rbf_diag.py", "rbf_geo.py", "rbf_ub_predict.py", "dust_loads.py", "rbf_motion_closure.py", "summary_windows.py",
           "make_review_package.py"):
    (OUT / "scripts").mkdir(exist_ok=True)
    shutil.copy(W / "scripts" / s_, OUT / "scripts" / s_)
shutil.copy(W / "scripts" / "review_README.md", OUT / "README.md")
files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
(OUT / "SHA256SUMS").write_text("".join(f"{sha(p)}  {p.relative_to(OUT)}\n" for p in files))
print("package files:", len(files), "bytes:", sum(p.stat().st_size for p in files))
