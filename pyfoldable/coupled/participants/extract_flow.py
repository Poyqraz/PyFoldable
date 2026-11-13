"""Extract a flow companion from retained DUST outputs (coupling venv: needs h5py; no solver run).

Usage: python -I extract_flow.py <run_dir> <spec_json>

spec = {"result_sha256": str, "windows": [ascending window numbers],
        "dust_post": path, "plane": {"n_xyz": [nx, 1, nz], "min_xyz": [...], "max_xyz": [...]}}

For each selected accepted window w (DUST result file run_res_{w:04d}.h5 is window w) it stores
what DUST computed: vortex-particle positions, vorticity vectors and core radii, and the implicit
panel-wake rows. DUST's own post-processor (dust_post, flow_field analysis) then evaluates the
velocity induced by the lifting lines, panel wake and particles plus the free stream on one
meridional plane per window; that is the vortex model's velocity, not a CFD field. Output:
<run_dir>/flow/flow_companion.npz and flow_companion.json (manifest binding every source file
by sha256). Raw outputs are only read. This file must not import pyfoldable.
"""
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time

import numpy as np

SCHEMA = 1
MAX_PARTICLES_PER_FRAME = 60000


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_vtr(path):
    """Velocity on a rectilinear grid from DUST's VTK-XML output (appended raw, UInt32 headers)."""
    b = open(path, "rb").read()
    head, _, data = b.partition(b'<AppendedData encoding="raw">')
    data = data[data.index(b"_") + 1:]
    out = {}
    for m in re.finditer(r'<DataArray type="Float32" Name="(\w+)"(?: NumberOfComponents="(\d+)")? format="appended" '
                         r'offset="(\d+)"', head.decode("latin1")):
        name, ncomp, off = m.group(1), int(m.group(2) or 1), int(m.group(3))
        n = struct.unpack_from("<I", data, off)[0]
        a = np.frombuffer(data, dtype="<f4", count=n // 4, offset=off + 4)
        out[name] = a.reshape(-1, ncomp) if ncomp > 1 else a
    return out


def main(run_dir, spec_path):
    import h5py  # coupling venv only; the VTK reader above stays importable without it

    spec = json.load(open(spec_path, encoding="utf-8"))
    windows = [int(w) for w in spec["windows"]]
    if not windows or windows != sorted(set(windows)) or windows[0] < 1:
        raise SystemExit("windows must be ascending, unique and positive")
    out_dir = os.path.join(run_dir, "flow")
    work = os.path.join(out_dir, "work")
    os.makedirs(os.path.join(work, "Postpro"), exist_ok=True)
    link = os.path.join(work, "Output")
    target = os.path.join("..", "..", "dust", "Output")
    if os.path.lexists(link) and (not os.path.islink(link) or os.readlink(link) != target):
        raise SystemExit("flow/work/Output exists and is not the expected link to dust/Output")
    if not os.path.lexists(link):
        os.symlink(target, link)
    for f in os.listdir(os.path.join(work, "Postpro")):  # never read a stale file from an earlier attempt
        os.remove(os.path.join(work, "Postpro", f))

    sources, times, offsets, pos, vort, rad, panel = [], [], [0], [], [], [], []
    for w in windows:
        rel = f"dust/Output/run_res_{w:04d}.h5"
        fn = os.path.join(run_dir, rel)
        sources.append({"window": w, "file": rel, "sha256": _sha(fn), "bytes": os.path.getsize(fn)})
        with h5py.File(fn, "r") as f:
            times.append(float(np.array(f["time"])))
            pw = f["ParticleWake"]
            p = np.array(pw["WakePoints"], dtype=np.float32).reshape(-1, 3)
            if len(p) > MAX_PARTICLES_PER_FRAME:
                raise SystemExit(f"window {w}: {len(p)} particles exceed the bound")
            pos.append(p)
            vort.append(np.array(pw["WakeVort"], dtype=np.float32).reshape(-1, 3))
            rad.append(np.array(pw["VortexRad"], dtype=np.float32).reshape(-1))
            offsets.append(offsets[-1] + len(p))
            panel.append(np.array(f["PanelWake"]["WakePoints"], dtype=np.float32))

    plane = spec["plane"]
    blocks = []  # regular runs of windows -> one dust_post analysis each (start/end/step)
    for w in windows:
        if blocks and (len(blocks[-1]) == 1 or w - blocks[-1][-1] == blocks[-1][1] - blocks[-1][0]):
            blocks[-1].append(w)
        else:
            blocks.append([w])
    lines = ["basename = Postpro/ff", "data_basename = Output/run"]
    for k, b in enumerate(blocks):
        lines += ["analysis = {", "  type = flow_field", f"  name = ff{k}", f"  start_res = {b[0]}", f"  end_res = {b[-1]}",
                  f"  step_res = {b[1] - b[0] if len(b) > 1 else 1}", "  format = vtk", "  average = F",
                  "  variable = Velocity",
                  "  n_xyz = (/ {} /)".format(", ".join(str(int(v)) for v in plane["n_xyz"])),
                  "  min_xyz = (/ {} /)".format(", ".join(repr(float(v)) for v in plane["min_xyz"])),
                  "  max_xyz = (/ {} /)".format(", ".join(repr(float(v)) for v in plane["max_xyz"])), "}"]
    post_in = "\n".join(lines) + "\n"
    block_of = {w: k for k, b in enumerate(blocks) for w in b}
    with open(os.path.join(work, "dust_post.in"), "w") as fh:
        fh.write(post_in)
    aux_rel = "dust/Output/run_geo.h5"  # geometry dust_post reads in addition to the result files
    auxiliary = [{"file": aux_rel, "sha256": _sha(os.path.join(run_dir, aux_rel))}]
    t0 = time.time()
    proc = subprocess.run([spec["dust_post"], "dust_post.in"], cwd=work, capture_output=True, text=True, timeout=1800)
    with open(os.path.join(out_dir, "dust_post.log"), "w") as fh:
        fh.write(proc.stdout + proc.stderr)
    if proc.returncode != 0:
        raise SystemExit(f"dust_post failed with code {proc.returncode}")
    nx, _, nz = (int(v) for v in plane["n_xyz"])
    vel, gx, gz = [], None, None
    for w in windows:
        a = _read_vtr(os.path.join(work, "Postpro", f"ff_ff{block_of[w]}_{w:04d}.vtr"))
        if gx is None:
            gx, gz = np.array(a["x"], dtype=np.float64), np.array(a["z"], dtype=np.float64)
        vel.append(a["velocity"].reshape(nz, nx, 3).astype(np.float32))
    for f in os.listdir(os.path.join(work, "Postpro")):  # dust_post scratch; the arrays are kept in the npz
        os.remove(os.path.join(work, "Postpro", f))
    for src in sources + auxiliary:  # the inputs did not change while dust_post read them
        if _sha(os.path.join(run_dir, src["file"])) != src["sha256"]:
            raise SystemExit(f"{src['file']} changed during extraction")

    npz = os.path.join(out_dir, "flow_companion.npz")
    np.savez_compressed(npz, windows=np.array(windows, dtype=np.int32), time_label_s=np.array(times),
                        particle_offsets=np.array(offsets, dtype=np.int64),
                        particle_position_m=np.concatenate(pos), particle_vorticity=np.concatenate(vort),
                        particle_core_radius_m=np.concatenate(rad), panel_wake_m=np.stack(panel),
                        plane_x_m=gx, plane_z_m=gz, plane_y_m=np.array(float(plane["min_xyz"][1])),
                        plane_velocity_m_s=np.stack(vel))
    manifest = {
        "schema_version": SCHEMA, "artifact_class": "pyfoldable_coupled_flow_companion",
        "result_sha256": spec["result_sha256"], "run_id": os.path.basename(os.path.abspath(run_dir)),
        "windows": windows, "sources": sources, "auxiliary_sources": auxiliary,
        "dust_post": {"executable": os.path.basename(spec["dust_post"]), "sha256": _sha(spec["dust_post"]), "input": post_in,
                      "elapsed_s": round(time.time() - t0, 2)},
        "extractor_sha256": _sha(os.path.abspath(__file__)),
        "plane": plane, "particles_total": int(offsets[-1]),
        "npz": {"file": "flow_companion.npz", "sha256": _sha(npz), "bytes": os.path.getsize(npz)},
        "computed": ["vortex-particle positions, vorticity vectors and core radii (DUST)",
                     "implicit panel-wake rows (DUST)",
                     "induced plus free-stream velocity on a meridional plane (dust_post, DUST kernels)"],
    }
    with open(os.path.join(out_dir, "flow_companion.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
    print(f"flow companion: {len(windows)} windows, {offsets[-1]} particles, {manifest['npz']['bytes']} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
