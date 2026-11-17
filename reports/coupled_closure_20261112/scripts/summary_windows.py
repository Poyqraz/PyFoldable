"""Window-averaged loads from sealed coupled records (explicit averaging windows)."""
import json
import math
from pathlib import Path

D = Path.home() / "projects/PyFoldable/outputs/coupled_runs"


def stats(rid, a, b, label):
    r = json.loads((D / rid / "result.json").read_text())
    s = [x for x in r["series"] if a <= x["window"] <= b]
    n = len(s)
    c = r["run_definition"]["case"]
    ctl = c["controls"]
    W = c["omega_rad_s"]

    def m(k):
        return sum(x[k] for x in s) / n
    th = [x["theta_deg"][0] for x in s]
    print(f"{label:34s} {rid} {ctl.get('aero_topology', 'legacy'):14s} {ctl['azimuth_step_deg']:.1f}deg nel/seg {ctl['elements_per_segment']} "
          f"w{a}-{b} t {s[0]['time_s'] - c['dt_s']:.4f}-{s[-1]['time_s']:.4f}s ({n * c['dt_s'] * W / 2 / math.pi:.2f} rev): "
          f"T {m('thrust_n'):.3f} N | Qaero {m('aero_shaft_torque_nm'):.4f} | Qdrive {m('drive_torque_nm'):.4f} N m | "
          f"Paero {m('aero_power_absorbed_w'):.1f} | Pdrive {m('drive_power_w'):.1f} W | theta {min(th):.2f}..{max(th):.2f}")


stats("20261112T073117_fab3a9a152", 289, 360, "locked open, rev 5")
stats("20261112T073117_fab3a9a152", 361, 432, "locked open, rev 6 (last)")
stats("20261112T071200_20d4a1092d", 145, 288, "main: last latched rev (-5 deg)")
stats("20261112T071200_20d4a1092d", 289, 432, "main: rev 1 after release")
stats("20261112T071200_20d4a1092d", 433, 576, "main: rev 2 after release")
stats("20261112T071200_20d4a1092d", 577, 720, "main: rev 3 after release (last)")
stats("20261112T071157_91efdf9841", 217, 288, "release 5deg: rev 2 after release")
stats("20261112T071157_91efdf9841", 289, 360, "release 5deg: rev 3 after (last)")
stats("20261112T070917_55f6aea26f", 145, 216, "static -0.5 deg latched, rev 3")
stats("20261112T070920_67c85e4108", 145, 216, "open, same duration, rev 3")
