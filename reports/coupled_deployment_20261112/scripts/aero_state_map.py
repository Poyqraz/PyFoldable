"""No-induction section states over shaft speed and fold angle (14 m/s axial inflow), versus the
admitted polar envelope. Simple sweep theory for the folded distal segment: the section sees the
velocity component normal to its span (in the rotor plane) plus the axial inflow.
Induction lowers the inflow angle under load, so this is a readiness map, not a solution."""
import json
import math
import sys

r = json.load(open(sys.argv[1]))
case = r["run_definition"]["case"]
g = case["geometry"]
env = r["request"]["c81"]["envelope"]
V = case["inflow_m_s"]; rho, mu, a = case["density_kg_m3"], case["viscosity_pa_s"], case["speed_of_sound_m_s"]
h = g["hinge_radius_m"]


def states(rpm, fold_deg):
    W = rpm * 2 * math.pi / 60
    th = math.radians(fold_deg)
    out = []
    for segname in ("proximal_sections", "distal_sections"):
        for s in g[segname]:
            if segname == "proximal_sections":
                vt = W * s["radius_m"]
            else:
                # distal point position after in-plane fold; blade velocity W x r, component normal to the distal span
                d = s["radius_m"] - h
                x, y = -d * math.sin(th), h + d * math.cos(th)  # fold rotates the distal span by th about the hinge
                vx, vy = -W * y, W * x                          # W e_z x r
                span = (-math.sin(th), math.cos(th))
                vt = abs(vx * span[1] - vy * span[0])         # in-plane speed normal to the span
            U = math.hypot(V, vt)
            alpha = math.degrees(s["twist_rad"] - math.atan2(V, vt))
            out.append((alpha, rho * U * s["chord_m"] / mu, U / a))
    return out


print(f"admitted: alpha {env['alpha_deg']}, Re {env['reynolds']}, Mach {env['mach']}; inflow {V} m/s")
print(" fold  rpm    alpha[min,max]       Re[min,max]          inside table?")
res = []
for fold in (0, -10, -20, -30, -45):
    for rpm in (0, 300, 600, 900, 1200, 1500, 1800, 2100, 2400):
        st = states(rpm, fold)
        al = [x[0] for x in st]; re = [x[1] for x in st]; ma = [x[2] for x in st]
        ok = (env["alpha_deg"][0] <= min(al) and max(al) <= env["alpha_deg"][1] and env["reynolds"][0] <= min(re)
              and max(re) <= env["reynolds"][1] and max(ma) <= env["mach"][1])
        res.append({"fold": fold, "rpm": rpm, "alpha": [min(al), max(al)], "re": [min(re), max(re)], "mach_max": max(ma), "inside": ok})
        print(f" {fold:4d} {rpm:5d}  [{min(al):7.1f},{max(al):6.1f}]   [{min(re):8.0f},{max(re):8.0f}]   {'yes' if ok else 'NO'}")
json.dump(res, open(sys.argv[2], "w"), indent=1)
