"""Figures, tables and exports for coupled results (accepted solver states only).

The 3-D playback places rigid segment surfaces, built from the catalog
airfoil coordinates and the declared sections, at the MBDyn node states of each
accepted window. It is a kinematic visualization of the solved rigid-body
motion; no pressure or stress field is drawn because none was solved.
"""
from __future__ import annotations

import csv
import io
import json
import math
import zipfile

import plotly.graph_objects as go

from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.coupled.frames import rotvec_to_matrix

_COLORS = ("#0b6170", "#DC671D", "#A44AC2", "#2E7D32")
_SEGMENT_COLORS = {"proximal": "#008579", "distal": "#DC671D"}


def _layout(fig, title_y, height=300):
    fig.update_layout(height=height, margin=dict(l=55, r=20, t=24, b=45), hovermode="x unified",
                      legend=dict(orientation="h", x=0, y=-.22, xanchor="left", yanchor="top"))
    fig.update_xaxes(title="Zaman [s]")
    fig.update_yaxes(title=title_y)
    return fig


def _valid(row):
    return row["series"][:row["execution"]["valid_prefix_windows"]], row["series"][row["execution"]["valid_prefix_windows"]:]


def _shade(fig, series, key, color, name):
    """Shade windows where a boolean flag is true (latch / contact)."""
    spans, start = [], None
    for r in series:
        flag = r[key] if isinstance(r[key], bool) else any(r[key])
        if flag and start is None:
            start = r["time_s"]
        if not flag and start is not None:
            spans.append((start, r["time_s"])); start = None
    if start is not None and series:
        spans.append((start, series[-1]["time_s"]))
    for a, b in spans:
        fig.add_vrect(x0=a, x1=b, fillcolor=color, opacity=.12, line_width=0)
    if spans:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(color=color, opacity=.35, size=10),
                                 name=name, showlegend=True))


def time_figure(row, channels, unit, *, per_blade=False, shade=True):
    valid, invalid = _valid(row)
    fig = go.Figure()
    for i, (key, label) in enumerate(channels):
        for part, dash, suffix in ((valid, "solid", ""), (invalid, "dot", " (kapsam/yakınsama dışı)")):
            if not part:
                continue
            t = [r["time_s"] for r in part]
            if per_blade:
                for b in range(len(part[0][key])):
                    # colour identifies the channel, line style the blade
                    fig.add_trace(go.Scatter(x=t, y=[r[key][b] for r in part], mode="lines",
                                             name=f"{label} · kanat {b + 1}{suffix}",
                                             line=dict(color=_COLORS[i % 4], width=2.4 if b == 0 else 1.6,
                                                       dash=dash if dash != "solid" else ("solid" if b == 0 else "dash"))))
            else:
                fig.add_trace(go.Scatter(x=t, y=[r[key] for r in part], mode="lines", name=label + suffix,
                                         line=dict(color=_COLORS[i % 4], dash=dash, width=2)))
    if shade:
        _shade(fig, row["series"], "latch_active", "#76889A", "Kilit (serbest bırakma öncesi)")
        _shade(fig, row["series"], "contact_active", "#CB4B66", "Stop teması")
    return _layout(fig, unit)


def coverage_figure(row, quantity):
    key = {"alpha": "alpha_deg", "re": "reynolds", "mach": "mach"}[quantity]
    env = row["request"]["c81"]["envelope"]["reynolds" if quantity == "re" else key]
    s = row["series"]
    t = [r["time_s"] for r in s]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=[r["coverage"][key][1] for r in s], name="En büyük", mode="lines",
                             line=dict(color="#0b6170")))
    fig.add_trace(go.Scatter(x=t, y=[r["coverage"][key][0] for r in s], name="En küçük", mode="lines",
                             line=dict(color="#DC671D")))
    for v, name in ((env[0], "Tablo alt sınırı"), (env[1], "Tablo üst sınırı")):
        fig.add_hline(y=v, line_dash="dash", line_color="#CB4B66", annotation_text=name, annotation_position="top left")
    return _layout(fig, {"alpha": "α [°]", "re": "Re", "mach": "Mach"}[quantity], height=260)


def iterations_figure(row):
    s = row["series"]
    fig = go.Figure(go.Bar(x=[r["time_s"] for r in s], y=[r["coupling_iterations"] for r in s],
                           marker_color=["#0b6170" if r["coupling_converged"] else "#CB4B66" for r in s],
                           name="Bağlaşım iterasyonu"))
    return _layout(fig, "İterasyon", height=220)


_SEG_NAMES = {"proximal": "iç parça", "distal": "dış parça", "junction": "menteşe geçiş elemanı"}


def radial_rows(row, window):
    cols = row["radial_columns"]
    return [dict(zip(cols, rec)) for rec in row["radial"] if rec[0] == window]


def radial_figure(rows, field, label):
    fig = go.Figure()
    for (blade, seg), color in (((0, "proximal"), "#008579"), ((0, "distal"), "#DC671D"),
                                ((1, "proximal"), "#5BB5A9"), ((1, "distal"), "#F0A672"),
                                ((0, "junction"), "#6B6B6B"), ((1, "junction"), "#A3A3A3")):
        pts = [r for r in rows if r["blade"] == blade and r["segment"] == seg]
        if pts:
            fig.add_trace(go.Scatter(x=[1000 * r["span_y_m"] for r in pts], y=[r[field] for r in pts],
                                     mode="lines+markers", line=dict(color=color, width=2),
                                     name=f"Kanat {blade + 1} · {_SEG_NAMES[seg]}"))
    fig.update_layout(height=280, margin=dict(l=55, r=20, t=24, b=45),
                      legend=dict(orientation="h", x=0, y=-.25, xanchor="left", yanchor="top"))
    fig.update_xaxes(title="Gövde ekseninde açıklık konumu (açık geometri) [mm]")
    fig.update_yaxes(title=label)
    return fig


# --------------------------------------------------------------------------- geometry


def _section_loop(foil, n=24):
    coords = foil.coordinates
    step = max(1, len(coords) // n)
    pts = list(coords[::step])
    if pts[-1] != coords[-1]:
        pts.append(coords[-1])
    return pts


def segment_meshes(row, n_loop=24):
    """Body-frame vertices/faces per rigid segment (open geometry, quarter-chord stacking).

    Records with ``bodies`` (continuous_rbf) place one surface per MBDyn body node; earlier records
    used the coupling nodes, which were the body nodes."""
    case = row["run_definition"]["case"]
    foil = load_project_airfoil(case["geometry"]["profile"])
    loop = _section_loop(foil, n_loop)
    meshes = []
    for node in row["run_definition"].get("bodies") or row["run_definition"]["coupling_nodes"]:
        sections = case["geometry"]["proximal_sections" if node["segment"] == "proximal" else "distal_sections"]
        verts, faces = [], []
        for s in sections:
            c, tw, y = s["chord_m"], s["twist_rad"], s["radius_m"]
            for xc, zc in loop:
                X, Z = (xc - 0.25) * c, zc * c
                verts.append((X * math.cos(tw) + Z * math.sin(tw), y, -X * math.sin(tw) + Z * math.cos(tw)))
        m = len(loop)
        for i in range(len(sections) - 1):
            for j in range(m - 1):
                a, b = i * m + j, i * m + j + 1
                faces += [(a, b, a + m), (b, b + m, a + m)]
        meshes.append({"node": node, "verts": verts, "faces": faces})
    return meshes


def _world(mesh, state):
    R = rotvec_to_matrix(state["phi"])
    x0, local = state["x"], mesh["node"]["local"]
    out = []
    for v in mesh["verts"]:
        d = (v[0] - local[0], v[1] - local[1], v[2] - local[2])
        out.append(tuple(x0[k] + sum(R[k][j] * d[j] for j in range(3)) for k in range(3)))
    return out


def playback_figure(row, max_frames=90):
    meshes = segment_meshes(row)
    states = row["node_states"]
    if not states:
        return None
    stride = max(1, math.ceil(len(states) / max_frames))
    picked = states[::stride]
    if picked[-1] is not states[-1]:
        picked.append(states[-1])
    times = {r["window"]: r for r in row["series"]}

    def traces(entry):
        out = []
        for mesh in meshes:
            label = str(mesh["node"]["mbdyn_label"])
            w = _world(mesh, entry["nodes"][label])
            i, j, k = zip(*mesh["faces"])
            x, y, z = zip(*[tuple(1000 * c for c in p) for p in w])
            out.append(go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, color=_SEGMENT_COLORS[mesh["node"]["segment"]],
                                 flatshading=True, name=f"blade{mesh['node']['blade'] + 1}_{mesh['node']['segment']}", showlegend=False,
                                 lighting=dict(ambient=.8, diffuse=.6)))
        return out

    def label(entry):
        r = times.get(entry["window"])
        if r is None:
            return "t = 0 s"
        th = ", ".join(f"{v:.2f}°" for v in r["theta_deg"])
        return f"t = {r['time_s']:.4f} s · θ = {th} · T = {r['thrust_n']:.2f} N"

    first = traces(picked[0])
    fig = go.Figure(data=first, frames=[go.Frame(data=traces(e), name=str(e["window"]), layout=dict(title=label(e)))
                                       for e in picked])
    R = 1000 * row["run_definition"]["case"]["geometry"]["tip_radius_m"] * 1.1
    fig.update_layout(
        height=520, margin=dict(l=0, r=0, t=40, b=0), title=label(picked[0]),
        scene=dict(xaxis=dict(range=[-R, R], title="X [mm]"), yaxis=dict(range=[-R, R], title="Y [mm]"),
                   zaxis=dict(range=[-R / 3, R / 3], title="Z [mm] (itki yönü)"), aspectmode="manual",
                   aspectratio=dict(x=1, y=1, z=1 / 3), camera=dict(eye=dict(x=.75, y=-.75, z=.65))),
        updatemenus=[dict(type="buttons", showactive=False, x=0, y=0, xanchor="left", yanchor="top",
                          buttons=[dict(label="▶ Oynat", method="animate",
                                        args=[None, dict(frame=dict(duration=80, redraw=True), fromcurrent=True)]),
                                   dict(label="❚❚ Durdur", method="animate",
                                        args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
        sliders=[dict(active=0, x=.12, len=.86, y=0, currentvalue=dict(prefix="Pencere: "),
                      steps=[dict(method="animate", label=str(e["window"]),
                                  args=[[str(e["window"])], dict(mode="immediate", frame=dict(duration=0, redraw=True))])
                             for e in picked])])
    return fig


def vtk_zip(row) -> bytes:
    """ParaView-compatible legacy VTK polydata series plus a .pvd time collection."""
    meshes = segment_meshes(row, n_loop=48)
    times = {r["window"]: r["time_s"] for r in row["series"]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        entries = []
        for entry in row["node_states"]:
            pts, polys, seg = [], [], []
            for mid, mesh in enumerate(meshes):
                base = len(pts)
                pts += _world(mesh, entry["nodes"][str(mesh["node"]["mbdyn_label"])])
                polys += [tuple(base + v for v in f) for f in mesh["faces"]]
                seg += [mid] * len(mesh["faces"])
            lines = ["# vtk DataFile Version 3.0", f"PyFoldable coupled window {entry['window']}", "ASCII",
                     "DATASET POLYDATA", f"POINTS {len(pts)} double"]
            lines += [f"{p[0]!r} {p[1]!r} {p[2]!r}" for p in pts]
            lines.append(f"POLYGONS {len(polys)} {4 * len(polys)}")
            lines += [f"3 {a} {b} {c}" for a, b, c in polys]
            lines += [f"CELL_DATA {len(polys)}", "SCALARS segment_id int 1", "LOOKUP_TABLE default"]
            lines += [str(s) for s in seg]
            name = f"rotor_{entry['window']:05d}.vtk"
            zf.writestr(name, "\n".join(lines) + "\n")
            entries.append((times.get(entry["window"], 0.0), name))
        pvd = ['<?xml version="1.0"?>', '<VTKFile type="Collection" version="0.1">', "<Collection>"]
        pvd += [f'<DataSet timestep="{t!r}" file="{n}"/>' for t, n in entries]
        pvd += ["</Collection>", "</VTKFile>"]
        zf.writestr("rotor.pvd", "\n".join(pvd) + "\n")
        zf.writestr("README.txt", "Rigid segment surfaces at MBDyn accepted states (catalog airfoil, declared sections).\n"
                                  "No pressure or stress field is included: none was solved.\n")
    return buf.getvalue()


SERIES_CSV_FIELDS = ("window", "time_s", "rpm", "thrust_n", "aero_shaft_torque_nm", "drive_torque_nm",
                     "aero_power_absorbed_w", "drive_power_w", "coupling_iterations", "coupling_converged",
                     "within_admitted_table", "latch_active")


def series_csv(row) -> str:
    stream = io.StringIO(newline="")
    nb = len(row["series"][0]["theta_deg"]) if row["series"] else 0
    per = ("theta_deg", "theta_rate_rad_s", "hinge_aero_torque_nm", "hinge_law_torque_nm", "hinge_spring_torque_nm",
           "hinge_damping_torque_nm", "hinge_contact_torque_nm", "centrifugal_hinge_moment_derived_nm")
    header = list(SERIES_CSV_FIELDS) + [f"{k}_b{b + 1}" for k in per for b in range(nb)] + \
        ["alpha_min_deg", "alpha_max_deg", "re_min", "re_max", "mach_min", "mach_max"]
    w = csv.writer(stream)
    w.writerow(header)
    for r in row["series"]:
        cov = r["coverage"]
        w.writerow([r[k] for k in SERIES_CSV_FIELDS] + [r[k][b] for k in per for b in range(nb)] +
                   [cov["alpha_deg"][0], cov["alpha_deg"][1], cov["reynolds"][0], cov["reynolds"][1],
                    cov["mach"][0], cov["mach"][1]])
    return stream.getvalue()


def radial_csv(row) -> str:
    stream = io.StringIO(newline="")
    w = csv.writer(stream)
    w.writerow(row["radial_columns"])
    w.writerows(row["radial"])
    return stream.getvalue()


def saved_json(row) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
