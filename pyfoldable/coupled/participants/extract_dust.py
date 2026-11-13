"""Extract DUST lifting-line results to JSON (runs in the coupling venv, needs h5py).

Usage: python -I extract_dust.py <dust_dir> <output_json>

Writes, per result file (in order), the time label and for each component the
per-element alpha [deg], vel_2d [m/s], aero_coeff (cl, cd, cm), dF [N] and
dMom [N m] (global frame), plus the reference geometry from geo_input.h5:
quarter-chord line points (component local frame) and element chords.
This file must not import pyfoldable.
"""
import glob
import json
import os
import sys

import h5py
import numpy as np


def _s(value):
    return value.decode().strip() if isinstance(value, bytes) else str(value).strip()


def main(dust_dir, output_json):
    geo = {}
    with h5py.File(os.path.join(dust_dir, "geo_input.h5"), "r") as g:
        for key in sorted(k for k in g["Components"].keys() if k.startswith("Comp")):
            grp = g["Components"][key]
            rr = np.array(grp["Geometry"]["rr"])
            line = rr[0::2]
            chord_p = np.linalg.norm(rr[1::2] - rr[0::2], axis=1)
            geo[key] = {"name": _s(grp["CompName"][()]),
                        "ll_points_local": line.tolist(),
                        "element_mid_local": (0.5 * (line[:-1] + line[1:])).tolist(),
                        "element_chord": (0.5 * (chord_p[:-1] + chord_p[1:])).tolist(),
                        "element_span": np.linalg.norm(line[1:] - line[:-1], axis=1).tolist()}
    steps = []
    files = sorted(glob.glob(os.path.join(dust_dir, "Output", "run_res_*.h5")))
    for fn in files:
        with h5py.File(fn, "r") as f:
            row = {"file": os.path.basename(fn), "time_label_s": float(np.array(f["time"])), "components": {}}
            for key in geo:
                s = f["Components"][key]["Solution"]
                row["components"][key] = {
                    "alpha_deg": np.array(s["alpha"]).tolist(),
                    "vel_2d": np.array(s["vel_2d"]).tolist(),
                    "aero_coeff": np.array(s["aero_coeff"]).T.tolist() if np.array(s["aero_coeff"]).shape[0] == 3 else np.array(s["aero_coeff"]).tolist(),
                    "dF": np.array(s["dF"]).tolist(),
                    "dMom": np.array(s["dMom"]).tolist(),
                }
            steps.append(row)
    with open(output_json, "w", encoding="utf-8") as fh:
        json.dump({"schema_version": 1, "geometry": geo, "steps": steps}, fh)
    print(f"extracted {len(steps)} result files, {len(geo)} components")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
