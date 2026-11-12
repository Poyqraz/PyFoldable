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


# ---------------------------------------------------------------------------
# Flow and response (flow companion: DUST-computed wake and induced velocity)

EVENT_LABELS = {"release": "Kilit açılışı", "first_contact": "İlk stop teması", "largest_opening": "En büyük açılma",
                "second_swing_min": "İkinci salınım minimumu", "last": "Son pencere"}
_EVENT_COLORS = {"release": "#6B7280", "first_contact": "#DC2626", "largest_opening": "#D97706",
                 "second_swing_min": "#7C3AED", "last": "#374151"}


def _node_state(row, window):
    for entry in row["node_states"]:
        if entry["window"] == window:
            return entry
    raise KeyError(window)


def _subsample(n, cap):
    import numpy as np
    return np.arange(n) if n <= cap else np.linspace(0, n - 1, cap).round().astype(int)


def flow_scene_figure(row, fc, window, *, max_particles=6000, show_plane=True):
    """Reconstructed blade surfaces at the MBDyn state of ``window`` with the DUST wake of the same
    accepted window: vortex particles coloured by strength and the meridional velocity plane."""
    import numpy as np
    entry = _node_state(row, window)
    fig = go.Figure()
    for mesh in segment_meshes(row):
        w = _world(mesh, entry["nodes"][str(mesh["node"]["mbdyn_label"])])
        i, j, k = zip(*mesh["faces"])
        x, y, z = zip(*[tuple(1000 * c for c in p) for p in w])
        fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, color=_SEGMENT_COLORS[mesh["node"]["segment"]],
                                flatshading=True, showlegend=False, hoverinfo="skip",
                                name=f"blade{mesh['node']['blade'] + 1}_{mesh['node']['segment']}",
                                lighting=dict(ambient=.8, diffuse=.6)))
    p, v, _ = fc.particles(window)
    pick = _subsample(len(p), max_particles)
    mag = np.linalg.norm(v[pick], axis=1)
    fig.add_trace(go.Scatter3d(
        x=1000 * p[pick, 0], y=1000 * p[pick, 1], z=1000 * p[pick, 2], mode="markers",
        marker=dict(size=1.6, color=np.log10(np.maximum(mag, 1e-12)), colorscale="Viridis", opacity=.75,
                    colorbar=dict(title="log₁₀|α|", x=1.0, len=.5, y=.75)),
        name=f"Girdap parçacıkları (DUST, {len(pick)}/{len(p)})", hoverinfo="skip"))
    pw = fc.panel_wake[fc.index(window)]
    for row_i, dash in ((0, "solid"), (1, "dot")):
        fig.add_trace(go.Scatter3d(x=1000 * pw[row_i, :, 0], y=1000 * pw[row_i, :, 1], z=1000 * pw[row_i, :, 2],
                                   mode="markers", marker=dict(size=1.8, color="#111827"), showlegend=row_i == 0,
                                   name="Panel izi (DUST, ilk sıra)", hoverinfo="skip"))
    if show_plane:
        vel = fc.plane_velocity[fc.index(window)]
        X, Z = np.meshgrid(1000 * fc.plane_x, 1000 * fc.plane_z)
        fig.add_trace(go.Surface(x=X, y=np.full_like(X, 1000 * fc.plane_y), z=Z, surfacecolor=-vel[:, :, 2],
                                 colorscale="RdBu_r", cmin=float(np.percentile(-vel[:, :, 2], 1)),
                                 cmax=float(np.percentile(-vel[:, :, 2], 99)), opacity=.55, showscale=False,
                                 name="Hız düzlemi (dust_post)", hoverinfo="skip", showlegend=True))
    R = 1000 * row["run_definition"]["case"]["geometry"]["tip_radius_m"]
    fig.update_layout(height=560, margin=dict(l=0, r=0, t=30, b=0),
                      legend=dict(orientation="h", x=0, y=0, xanchor="left", yanchor="top"),
                      scene=dict(xaxis=dict(range=[-1.35 * R, 1.35 * R], title="X [mm]"),
                                 yaxis=dict(range=[-1.35 * R, 1.35 * R], title="Y [mm]"),
                                 zaxis=dict(range=[-2.05 * R, 0.55 * R], title="Z [mm] (itki yönü)"),
                                 aspectmode="manual", aspectratio=dict(x=1, y=1, z=2.6 / 2.7),
                                 camera=dict(eye=dict(x=1.35, y=-1.35, z=.55))))
    return fig


def flow_traces(row, fc, window, *, max_particles=6000, show_plane=True, view_rotation_rad=0.0):
    """DUST wake of one accepted window (particles, first panel-wake rows, dust_post velocity plane) as traces,
    optionally rotated about the shaft (rotor-relative view)."""
    import math
    import numpy as np
    c, s = math.cos(view_rotation_rad), math.sin(view_rotation_rad)

    def rot(x, y):
        return x * c - y * s, x * s + y * c
    out = []
    p, v, _ = fc.particles(window)
    pick = _subsample(len(p), max_particles)
    mag = np.linalg.norm(v[pick], axis=1)
    x, y = rot(1000 * p[pick, 0], 1000 * p[pick, 1])
    out.append(go.Scatter3d(
        x=x, y=y, z=1000 * p[pick, 2], mode="markers",
        marker=dict(size=1.6, color=np.log10(np.maximum(mag, 1e-12)), colorscale="Greys", opacity=.6,
                    colorbar=dict(title="log₁₀|α|<br>(parçacık)", x=-0.02, xanchor="right", len=.45, y=.75)),
        name=f"Girdap parçacıkları (DUST, {len(pick)}/{len(p)})", hoverinfo="skip"))
    pw = fc.panel_wake[fc.index(window)]
    for row_i in (0, 1):
        x, y = rot(1000 * pw[row_i, :, 0], 1000 * pw[row_i, :, 1])
        out.append(go.Scatter3d(x=x, y=y, z=1000 * pw[row_i, :, 2], mode="markers",
                                marker=dict(size=1.8, color="#111827"), showlegend=row_i == 0,
                                name="Panel izi (DUST, ilk sıra)", hoverinfo="skip"))
    if show_plane:
        vel = fc.plane_velocity[fc.index(window)]
        X, Z = np.meshgrid(1000 * fc.plane_x, 1000 * fc.plane_z)
        Xr, Yr = rot(X, np.full_like(X, 1000 * fc.plane_y))
        down = -vel[:, :, 2]
        out.append(go.Surface(x=Xr, y=Yr, z=Z, surfacecolor=down, colorscale="RdBu_r",
                              cmin=float(np.percentile(down, 1)), cmax=float(np.percentile(down, 99)), opacity=.45,
                              showscale=False, name="Hız düzlemi (dust_post, −w)", showlegend=True,
                              hovertemplate="−w %{surfacecolor:.2f} m/s<extra>Hız düzlemi</extra>"))
    return out


def flow_blade_scene(row, fc, window, mesh, *, fields=None, crange=None, rotor_fixed=False, show_plane=True,
                     max_particles=6000, selected_radius_m=None, colorscale="Viridis"):
    """One accepted window: lofted blades posed from that window's MBDyn body states (coloured with that window's
    element results when ``fields`` is given), with that window's wake and velocity plane. ``rotor_fixed``
    removes the rotor azimuth from everything (blades, wake and plane rotate together)."""
    from . import blade_geometry as bg
    from . import blade_views as bv
    rotation = -bg.rotor_azimuth(row, window) if rotor_fixed else 0.0
    R = 1000 * row["run_definition"]["case"]["geometry"]["tip_radius_m"]
    return bv.blade_figure(mesh, field=fields, crange=crange, transforms=bg.node_transforms(row, window),
                           view_rotation_rad=rotation, selected_radius_m=selected_radius_m, colorscale=colorscale,
                           extra_traces=flow_traces(row, fc, window, max_particles=max_particles, show_plane=show_plane,
                                                    view_rotation_rad=rotation),
                           scene_ranges=((-1.35 * R, 1.35 * R), (-1.35 * R, 1.35 * R), (-2.05 * R, 0.55 * R)),
                           uirevision=f"flow:{row['result_sha256']}:{rotor_fixed}")


def flow_plane_figure(row, fc, window):
    """Downward axial velocity −w on the meridional plane y = 0 (lab frame), from dust_post: the
    velocity DUST's lifting lines, panel wake and particles induce, plus the free stream."""
    import numpy as np
    i = fc.index(window)
    vel = fc.plane_velocity[i]
    down = -vel[:, :, 2]
    fig = go.Figure(go.Heatmap(x=1000 * fc.plane_x, y=1000 * fc.plane_z, z=down, colorscale="RdBu_r",
                               zmin=float(np.percentile(down, 1)), zmax=float(np.percentile(down, 99)),
                               colorbar=dict(title="−w [m/s]"),
                               hovertemplate="x %{x:.0f} mm · z %{y:.0f} mm · −w %{z:.2f} m/s<extra></extra>"))
    p, v, _ = fc.particles(window)
    near = np.abs(p[:, 1] - fc.plane_y) < 0.01
    fig.add_trace(go.Scatter(x=1000 * p[near, 0], y=1000 * p[near, 2], mode="markers",
                             marker=dict(size=3, color="rgba(17,24,39,.55)"), name="Parçacıklar (|y| < 10 mm)"))
    R = 1000 * row["run_definition"]["case"]["geometry"]["tip_radius_m"]
    for sgn in (-1, 1):
        fig.add_shape(type="line", x0=sgn * R, x1=sgn * R, y0=-2 * R, y1=0.5 * R, line=dict(dash="dot", width=1, color="#6B7280"))
    fig.update_layout(height=420, margin=dict(l=55, r=20, t=24, b=45),
                      legend=dict(orientation="h", x=0, y=-.18, xanchor="left", yanchor="top"))
    fig.update_xaxes(title="X [mm] (y = 0 düzlemi, laboratuvar çerçevesi)", scaleanchor="y", scaleratio=1,
                     constrain="domain", range=[1000 * fc.plane_x[0], 1000 * fc.plane_x[-1]])
    fig.update_yaxes(title="Z [mm] (itki yönü)", constrain="domain", range=[1000 * fc.plane_z[0], 1000 * fc.plane_z[-1]])
    return fig


def response_timeline_figure(row, window, ev):
    """θ, thrust, torques and hinge moment on one time axis with the selected window and events."""
    from plotly.subplots import make_subplots
    s = row["series"][:row["execution"]["valid_prefix_windows"]]
    t = [r["time_s"] for r in s]
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=.035,
                        subplot_titles=("Katlanma açısı θ [°]", "İtki [N]", "Tork [N·m]", "Menteşe momenti [N·m]",
                                        "Şaft devri [RPM]"))
    nb = len(s[0]["theta_deg"]) if s else 0
    for b in range(nb):
        fig.add_trace(go.Scatter(x=t, y=[r["theta_deg"][b] for r in s], name=f"θ · kanat {b + 1}",
                                 line=dict(color=_COLORS[b % 4], width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=[r["thrust_n"] for r in s], name="İtki", line=dict(color="#0b6170")), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=[r["aero_shaft_torque_nm"] for r in s], name="Aero şaft torku",
                             line=dict(color="#0b6170")), row=3, col=1)
    fig.add_trace(go.Scatter(x=t, y=[r["drive_torque_nm"] for r in s], name="Tahrik (tepki) torku",
                             line=dict(color="#DC671D", width=1)), row=3, col=1)
    fig.add_trace(go.Scatter(x=t, y=[r["hinge_aero_torque_nm"][0] for r in s], name="Aerodinamik (kanat 1)",
                             line=dict(color="#0b6170")), row=4, col=1)
    fig.add_trace(go.Scatter(x=t, y=[r["hinge_law_torque_nm"][0] for r in s], name="Yay+sönüm+stop (kanat 1)",
                             line=dict(color="#A44AC2", width=1)), row=4, col=1)
    fig.add_trace(go.Scatter(x=t, y=[r["rpm"] for r in s], name="Şaft devri", line=dict(color="#374151")), row=5, col=1)
    by_w = {r["window"]: r for r in s}
    for key, w in ev.items():  # events: dotted lines with legend entries (labels would overlap in time)
        if key == "last" or w not in by_w:
            continue
        fig.add_vline(x=by_w[w]["time_s"], line=dict(color=_EVENT_COLORS[key], dash="dot", width=1))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=_EVENT_COLORS[key], dash="dot"),
                                 name=f"{EVENT_LABELS[key]} · {by_w[w]['time_s']:.4f} s"), row=1, col=1)
    if window in by_w:
        fig.add_vline(x=by_w[window]["time_s"], line=dict(color="#111827", width=2))
    # y ranges from the data after the first quarter revolution: the impulsive start of the
    # lifting-line wake (first windows) would otherwise dominate the scale; it stays plotted.
    case = row["run_definition"]["case"]
    t0 = 0.25 * 2 * math.pi / case["omega_rad_s"]
    late = [r for r in s if r["time_s"] >= t0] or s
    channels = {2: (("thrust_n", None),), 3: (("aero_shaft_torque_nm", None), ("drive_torque_nm", None)),
                4: (("hinge_aero_torque_nm", 0), ("hinge_law_torque_nm", 0))}
    for rown, keys in channels.items():
        vals = sorted(r[k][i] if i is not None else r[k] for r in late for k, i in keys)
        if rown in (3, 4):  # stop impacts give very short reaction spikes; they stay plotted beyond the range
            vals = vals[int(0.01 * len(vals)):max(int(0.01 * len(vals)) + 1, int(0.99 * len(vals)))]
        lo, hi = min(vals), max(vals)
        pad = 0.06 * (hi - lo or 1.0)
        fig.update_yaxes(range=[lo - pad, hi + pad], row=rown, col=1)
    fig.update_layout(height=820, margin=dict(l=55, r=20, t=30, b=40), hovermode="x unified",
                      legend=dict(orientation="h", x=0, y=-.05, xanchor="left", yanchor="top"))
    fig.update_xaxes(title="Zaman [s]", row=5, col=1)
    return fig


def wake_radial_figure(row, fc, window, ref_window):
    """Near-wake particle strength by radius (within half a tip radius below the disk): where the
    blades shed vorticity. Compared with a reference window (e.g. the last latched frame)."""
    from pyfoldable.coupled.flow import radial_wake_strength
    g = row["run_definition"]["case"]["geometry"]
    R = g["tip_radius_m"]
    fig = go.Figure()
    for w, name, color in ((ref_window, f"Referans (pencere {ref_window})", "#9CA3AF"), (window, f"Seçili (pencere {window})", "#0b6170")):
        r, total = radial_wake_strength(fc, w, R)
        fig.add_trace(go.Scatter(x=1000 * r, y=total, mode="lines+markers", name=name, line=dict(color=color, shape="hvh")))
    fig.add_vline(x=1000 * g["hinge_radius_m"], line=dict(dash="dot", color="#DC671D"))
    fig.add_annotation(x=1000 * g["hinge_radius_m"], y=1, yref="paper", text="menteşe yarıçapı", showarrow=False,
                       xanchor="left", yanchor="top", font=dict(size=10, color="#DC671D"))
    fig.update_layout(height=300, margin=dict(l=55, r=20, t=24, b=45),
                      legend=dict(orientation="h", x=0, y=-.25, xanchor="left", yanchor="top"))
    fig.update_xaxes(title="Yarıçap r [mm]")
    fig.update_yaxes(title="Σ|α| yakın iz [m³/s]")
    return fig


def _vtk_binary(values, dtype) -> bytes:
    import numpy as np
    return np.ascontiguousarray(values, dtype=np.dtype(dtype).newbyteorder(">")).tobytes()


def flow_vtk_zip(row, fc) -> bytes:
    """ParaView series for the flow companion frames (binary legacy VTK, .pvd collections):
    DUST vortex particles (strength vector, |alpha|, core radius), the dust_post velocity plane and
    the reconstructed blade surfaces at the same accepted windows."""
    import numpy as np
    meshes = segment_meshes(row, n_loop=48)
    times = {r["window"]: r["time_s"] for r in row["series"]}
    states = {e["window"]: e for e in row["node_states"]}
    buf = io.BytesIO()
    cols = {"particles": [], "plane": [], "rotor": []}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for w in fc.windows.tolist():
            t = times.get(w, 0.0)
            p, v, rad = fc.particles(w)
            n = len(p)
            head = (f"# vtk DataFile Version 3.0\nPyFoldable DUST vortex particles, window {w}\nBINARY\n"
                    f"DATASET POLYDATA\nPOINTS {n} float\n").encode()
            body = _vtk_binary(p, "f4") + f"\nVERTICES {n} {2 * n}\n".encode()
            body += _vtk_binary(np.column_stack([np.ones(n, dtype=int), np.arange(n)]), "i4")
            body += f"\nPOINT_DATA {n}\nVECTORS alpha float\n".encode() + _vtk_binary(v, "f4")
            body += b"\nSCALARS alpha_magnitude float 1\nLOOKUP_TABLE default\n" + _vtk_binary(np.linalg.norm(v, axis=1), "f4")
            body += b"\nSCALARS core_radius_m float 1\nLOOKUP_TABLE default\n" + _vtk_binary(rad, "f4") + b"\n"
            name = f"particles/particles_{w:05d}.vtk"
            zf.writestr(name, head + body)
            cols["particles"].append((t, name))
            vel = fc.plane_velocity[fc.index(w)]
            nx, nz = len(fc.plane_x), len(fc.plane_z)
            head = (f"# vtk DataFile Version 3.0\nPyFoldable dust_post velocity plane, window {w}\nBINARY\n"
                    f"DATASET RECTILINEAR_GRID\nDIMENSIONS {nx} 1 {nz}\n").encode()
            body = f"X_COORDINATES {nx} float\n".encode() + _vtk_binary(fc.plane_x, "f4")
            body += b"\nY_COORDINATES 1 float\n" + _vtk_binary([fc.plane_y], "f4")
            body += f"\nZ_COORDINATES {nz} float\n".encode() + _vtk_binary(fc.plane_z, "f4")
            body += f"\nPOINT_DATA {nx * nz}\nVECTORS velocity float\n".encode() + _vtk_binary(vel.reshape(-1, 3), "f4") + b"\n"
            name = f"plane/plane_{w:05d}.vtk"
            zf.writestr(name, head + body)
            cols["plane"].append((t, name))
            if w in states:
                pts, polys = [], []
                for mesh in meshes:
                    base = len(pts)
                    pts += _world(mesh, states[w]["nodes"][str(mesh["node"]["mbdyn_label"])])
                    polys += [tuple(base + q for q in f) for f in mesh["faces"]]
                head = (f"# vtk DataFile Version 3.0\nPyFoldable reconstructed blade surfaces, window {w}\nBINARY\n"
                        f"DATASET POLYDATA\nPOINTS {len(pts)} float\n").encode()
                body = _vtk_binary(pts, "f4") + f"\nPOLYGONS {len(polys)} {4 * len(polys)}\n".encode()
                body += _vtk_binary([(3, a, b, c) for a, b, c in polys], "i4") + b"\n"
                name = f"rotor/rotor_{w:05d}.vtk"
                zf.writestr(name, head + body)
                cols["rotor"].append((t, name))
        for key, entries in cols.items():
            pvd = ['<?xml version="1.0"?>', '<VTKFile type="Collection" version="0.1">', "<Collection>"]
            pvd += [f'<DataSet timestep="{t!r}" file="{n}"/>' for t, n in entries]
            pvd += ["</Collection>", "</VTKFile>"]
            zf.writestr(f"{key}.pvd", "\n".join(pvd) + "\n")
        zf.writestr("flow_companion.json", json.dumps(fc.manifest, indent=1, sort_keys=True))
        zf.writestr("README.txt",
                    "PyFoldable coupled flow export (accepted windows of one sealed record).\n"
                    "particles.pvd : DUST vortex particles (computed): alpha = particle strength vector,\n"
                    "                core_radius_m = regularisation radius. Coordinates in metres, lab frame.\n"
                    "plane.pvd     : velocity on the y = 0 plane from dust_post (DUST kernels: lifting lines,\n"
                    "                panel wake and particles plus free stream). A vortex-model velocity, not CFD.\n"
                    "rotor.pvd     : blade surfaces reconstructed from catalog sections at the MBDyn states\n"
                    "                (not DUST's lifting-line geometry).\n"
                    "Not resolved by this model: boundary layers, surface pressure, viscous core structure below\n"
                    "the particle radius, hub/spinner and hinge-gap flow, structural deformation.\n"
                    "flow_companion.json lists, for every frame, the record's raw DUST file (and the geometry file\n"
                    "dust_post read) with the sha256 the sealed record holds; the loader checks these and the array\n"
                    "digest. That proves consistency with the record's sources, not who produced the arrays.\n")
    return buf.getvalue()
