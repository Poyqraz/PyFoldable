"""Views of a fold-cycle record: posed 3-D state with connection force/moment arrows, synchronized load timeline
with events, load versus fold angle, contributions, energy, playback, exports. One sample index selects one
physical state for every view."""
from __future__ import annotations

import csv
import io
import math

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pyfoldable.visualization import blade_surface as bs

from . import blade_views as bv
from . import figure_style as fs

LOADS ={"N_tension": ("Eksenel çekme N", "N"), "V_inplane": ("Düzlem içi kesme V_t", "N"), "V_axial": ("Pim yönü kesme V_z", "N"),
         "M_pin": ("Pim ekseni momenti M_z", "N·m"), "M_bending": ("Eğilme momenti M_t", "N·m"), "M_torsion": ("Burulma momenti M_s", "N·m")}
CONTRIB_LABEL = {"shaft_centripetal": "Mil dönüşü (merkezcil)", "shaft_euler": "Mil ivmesi (Euler)",
                 "fold_motion": "Katlanma hareketi (θ̈, θ̇², Coriolis)", "aerodynamic": "Aerodinamik (dış parça)",
                 "gravity": "Yerçekimi"}
ELEMENT_LABEL = {"spring": "Geri dönüş yayı", "damper": "Sönümleyici", "friction": "Sürtünme", "open_stop": "Açık stop",
                 "stowed_stop": "Kapalı stop", "latch": "Mandal", "actuator": "Aktüatör"}
FRAMES = {"lab": "Sabit (laboratuvar)", "rotor": "Rotorla birlikte", "hinge": "Menteşe yakın görünüm (rotorla)"}
_CACHE: dict = {}                    # arrays of the most recent record
_MESH: dict = {}
_TIMELINE: dict = {}                 # timeline of the most recent (record, blade); only the cursor moves
_PLAYBACK: dict = {}


def unit_of(key):
    return LOADS[key][1]


def _blade(a, name, blade):
    """One blade's column of a series stored for blade 1. Such series exist per blade (``_by_blade``) only with in-plane
    gravity; otherwise the blades are identical and blade 1 stands for every blade."""
    by = a.get(f"{name}_by_blade")
    return by[:, blade] if by is not None else a[name]


def _total(t, y, name):
    # thin dashed high-contrast line on top: a contribution equal to the total stays visible underneath
    return go.Scatter(x=t, y=y, name=name, line=dict(color=fs.TEXT, width=1.5, dash="dash"))


def _operating_range(row, a, ys, blade):
    """y-range from the 1–99 % quantiles in the operating (hold) phase outside the blade's stop contacts, so a short
    impact does not flatten the operating loads; None when that window is empty."""
    t, s = a["time_s"], row["case"]["schedule"]
    t2 = s["rest_s"] + s["spinup_s"]
    keep = (t >= t2) & (t <= t2 + s["hold_s"]) if s["hold_s"] > 0 else np.ones(len(t), bool)
    for c in row["contacts"]:
        if c["blade"] == blade:
            keep &= (t < c["t_in_s"]) | (t > c["t_out_s"])
    if keep.sum() < 2:
        return None
    lo, hi = np.quantile(np.concatenate([y[keep] for y in ys]), [0.01, 0.99])
    pad = 0.1 * (hi - lo) or 0.1 * max(abs(lo), 1e-9)
    return [float(lo - pad), float(hi + pad)]


def spec_payload(spec: bs.BladeSpec) -> dict:
    return {"profile_id": spec.profile_id, "profile": [list(p) for p in spec.profile], "stations": [list(s) for s in spec.stations],
            "hub_radius_m": spec.hub_radius_m, "root_radius_m": spec.root_radius_m, "hinge_radius_m": spec.hinge_radius_m,
            "tip_radius_m": spec.tip_radius_m, "blade_count": spec.blade_count, "distal_axial_offset_m": spec.distal_axial_offset_m}


def spec_from_payload(d: dict) -> bs.BladeSpec:
    return bs.BladeSpec(d["profile_id"], tuple(tuple(p) for p in d["profile"]), tuple(tuple(s) for s in d["stations"]),
                        d["hub_radius_m"], d["root_radius_m"], d["hinge_radius_m"], d["tip_radius_m"], d["blade_count"],
                        d.get("distal_axial_offset_m", 0.0))


def _as_arrays(row) -> dict:
    return {k: np.asarray(v, dtype=float) for k, v in row["series"].items() if isinstance(v, list) and v}


def arrays(row) -> dict:
    key = row["result_sha256"]
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = _as_arrays(row)
    return _CACHE[key]


def transforms(spec, thetas, psi):
    out = []
    for b, th in enumerate(thetas):
        az = psi + 2.0 * math.pi * b / spec.blade_count
        out.append(lambda p, moving, th=th, az=az: bs.pose_points(p, np.asarray(moving, bool), spec.hinge_radius_m, th, az,
                                                                spec.distal_axial_offset_m))
    return out


def _arrow(p, v, color, name, text, width=6):
    q = p + v
    return [go.Scatter3d(x=[p[0], q[0]], y=[p[1], q[1]], z=[p[2], q[2]], mode="lines", line=dict(color=color, width=width),
                         name=name, hovertext=text, hoverinfo="text"),
            go.Cone(x=[q[0]], y=[q[1]], z=[q[2]], u=[v[0]], v=[v[1]], w=[v[2]], anchor="tip", sizemode="absolute",
                    sizeref=max(1e-6, 0.25 * float(np.linalg.norm(v))), colorscale=[[0, color], [1, color]],
                    showscale=False, name=name, hovertext=text, hoverinfo="text")]


def scales(row, spec):
    a = arrays(row)
    R = spec.tip_radius_m * 1000.0
    fmax = float(np.abs(a["F_global_n"]).max()) or 1.0
    mmax = float(np.abs(a["M_global_nm"]).max()) or 1.0
    return 0.35 * R / fmax, 0.3 * R / mmax          # mm per N, mm per N·m (fixed for the whole record)


def _view_rot(frame, psi):
    return -psi if frame in ("rotor", "hinge") else 0.0


def arrow_traces(row, spec, i, frame="rotor"):
    """Force (red) and moment (purple) the proximal part applies to the distal part of blade 1 at the connection."""
    a = arrays(row)
    psi = float(a["psi_rad"][i])
    rot = _view_rot(frame, psi)
    sF, sM = scales(row, spec)
    th = math.radians(float(a["theta_deg"][i][0]))
    P = bs.pose_points(np.array([[0.0, spec.hinge_radius_m, 0.0]]), np.array([True]), spec.hinge_radius_m, th, psi,
                       spec.distal_axial_offset_m)[0] * 1000.0
    F, M = np.asarray(a["F_global_n"][i]), np.asarray(a["M_global_nm"][i])
    P, Fv, Mv = (bv._rot(np.atleast_2d(x), rot)[0] for x in (P, F * sF, M * sM))
    loads = {k: float(a[f"load_{k}"][i][0]) for k in LOADS}
    ft = (f"Bağlantı kuvveti |F| = {np.linalg.norm(F):.1f} N · N = {loads['N_tension']:.1f} · V_t = {loads['V_inplane']:.1f} · "
          f"V_z = {loads['V_axial']:.2f} N (iç parçadan dış parçaya)")
    mt = (f"Bağlantı momenti |M| = {np.linalg.norm(M):.3f} N·m · M_z (pim) = {loads['M_pin']:.3f} · M_t (eğilme) = "
          f"{loads['M_bending']:.3f} · M_s (burulma) = {loads['M_torsion']:.3f} N·m")
    return _arrow(P, Fv, "#d62728", "Bağlantı kuvveti", ft, 9) + _arrow(P, Mv, "#a855f7", "Bağlantı momenti (vektör)", mt, 7)


def mesh_for(spec):
    joint = "plane" if spec.distal_axial_offset_m > 0 else "relief"
    if spec not in _MESH:
        _MESH.clear()
        _MESH[spec] = bs.loft(spec, n_side=24, dr=0.006, joint=joint)
    return _MESH[spec]


def scene_figure(row, spec, i, frame="rotor", ghosts=True, height=560):
    a = arrays(row)
    mesh = mesh_for(spec)
    psi = float(a["psi_rad"][i])
    thetas = [math.radians(x) for x in a["theta_deg"][i]]
    rot = _view_rot(frame, psi)
    traces = bv._frame_traces(mesh, {"transforms": transforms(spec, thetas, psi), "field": None}, None, "Viridis", rot)
    traces[0].opacity = 0.45                              # the connection arrows start inside the blade at the pin
    if ghosts:
        mech = row["case"]["mechanism"]
        for ang, name in ((mech["open_stop_rad"], "Açık sınır (blade 1)"), (mech["stowed_stop_rad"], "Kapalı sınır (blade 1)")):
            g = bv._frame_traces(mesh, {"transforms": transforms(spec, [ang] + thetas[1:], psi), "field": None}, None, "Viridis", rot)[0]
            n1 = len(mesh.vertices)
            sel = g.i < n1
            traces.append(go.Mesh3d(x=g.x[:n1], y=g.y[:n1], z=g.z[:n1], i=g.i[sel], j=g.j[sel], k=g.k[sel], opacity=0.18,
                                    color="#6b7280" if "Açık" in name else "#f59e0b", name=name, hoverinfo="name", showlegend=True))
    traces += arrow_traces(row, spec, i, frame)
    P = bv._rot(np.atleast_2d(bs.pose_points(np.array([[0.0, spec.hinge_radius_m, 0.0]]), np.array([True]), spec.hinge_radius_m,
                                             thetas[0], psi, spec.distal_axial_offset_m)[0] * 1000.0), rot)[0]
    traces.append(go.Scatter3d(x=[P[0], P[0]], y=[P[1], P[1]], z=[P[2] - 40, P[2] + 40], mode="lines", line=dict(color="#9ca3af", width=5),
                               name="Pim ekseni (mile paralel)", hoverinfo="name"))
    fig = go.Figure(traces)
    R = spec.tip_radius_m * 1000.0
    if frame == "hinge":
        c = P
        rng = ((c[0] - 0.22 * R, c[0] + 0.22 * R), (c[1] - 0.22 * R, c[1] + 0.22 * R), (c[2] - 0.12 * R, c[2] + 0.12 * R))
    else:
        rng = ((-1.1 * R, 1.1 * R), (-1.1 * R, 1.1 * R), (-0.35 * R, 0.5 * R))
    span = rng[0][1] - rng[0][0]
    sF, sM = scales(row, spec)
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=-0.02),  # noqa: E501
                      title=dict(text=f"Ölçek: kuvvet 1 mm = {1 / sF:.2f} N · moment 1 mm = {1 / sM:.4f} N·m (kayıt boyunca sabit)",
                                 font=dict(size=12)),
                      scene=dict(aspectmode="manual", **{ax + "axis": dict(range=list(r), title=f"{ax.upper()} [mm]") for ax, r in zip("xyz", rng)},
                                 aspectratio={ax: (r[1] - r[0]) / span for ax, r in zip("xyz", rng)},
                                 camera=dict(eye=dict(x=0.9, y=-1.3, z=0.8))))
    return fig


def events_of(row, blade=0):
    """Events of one blade; with in-plane gravity every blade has its own list, otherwise blade 1 stands for all."""
    by = row.get("events_by_blade")
    return by[blade] if by else row["events"]


def event_clusters(events, span):
    """Events within 1 % of the time span of a cluster's first event share one numbered marker."""
    out = []
    for e in sorted(events, key=lambda e: e["time_s"]):
        if out and e["time_s"] - out[-1][0]["time_s"] <= 0.01 * span:
            out[-1].append(e)
        else:
            out.append([e])
    return out


def _vline(fig, x, line):
    # one line across every shared-x row (a shape per row and event made the figure slow to build and send)
    fig.add_shape(type="line", xref="x", yref="paper", x0=x, x1=x, y0=0, y1=1, line=line)


def timeline_figure(row, i, blade=0, height=900):
    """Built once per (record, blade); later calls move only the cursor (the last shape)."""
    a = arrays(row)
    t = a["time_s"]
    key = (row["result_sha256"], blade, height)
    if key not in _TIMELINE:
        _TIMELINE.clear()
        _TIMELINE[key] = _timeline(row, a, blade, height)
    fig = _TIMELINE[key]
    fig.layout.shapes[-1].update(x0=float(t[i]), x1=float(t[i]))
    return fig


def _timeline(row, a, blade, height):
    t = a["time_s"]
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.025,
                        specs=[[{"secondary_y": True}], [{"secondary_y": True}], [{}], [{}], [{"secondary_y": True}]],
                        subplot_titles=("Katlanma açısı θ ve mil devri", "Açısal hız θ̇ ve ivme θ̈", "Bağlantı kuvvetleri (dış parçaya)",
                                        "Bağlantı momentleri (dil orta düzlemi)", "Dış parça itkisi ve menteşe ekseni aero momenti"))
    th = a["theta_deg"][:, blade]
    fig.add_trace(go.Scatter(x=t, y=th, name="θ", line=dict(color=fs.SERIES[0])), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=a["rpm"], name="Devir", line=dict(color=fs.CONSTRUCTION, dash="dash")), 1, 1, secondary_y=True)
    fig.add_trace(go.Scatter(x=t, y=a["theta_rate_rad_s"][:, blade], name="θ̇"), 2, 1)
    fig.add_trace(go.Scatter(x=t, y=a["theta_acc_rad_s2"][:, blade], name="θ̈", line=dict(dash="dot")), 2, 1, secondary_y=True)
    for k in ("N_tension", "V_inplane", "V_axial"):
        fig.add_trace(go.Scatter(x=t, y=a[f"load_{k}"][:, blade], name=LOADS[k][0]), 3, 1)
    for k in ("M_pin", "M_bending", "M_torsion"):
        fig.add_trace(go.Scatter(x=t, y=a[f"load_{k}"][:, blade], name=LOADS[k][0]), 4, 1)
    fig.add_trace(go.Scatter(x=t, y=a["aero_thrust_n"][:, blade], name="Dış parça itkisi"), 5, 1)
    fig.add_trace(go.Scatter(x=t, y=a["aero_pin_torque_nm"][:, blade], name="Aero pim momenti", line=dict(dash="dot")),
                  5, 1, secondary_y=True)
    groups = event_clusters(events_of(row, blade), float(t[-1] - t[0]))
    for g in groups:
        _vline(fig, g[0]["time_s"], dict(color="rgba(154,167,180,.5)", width=1, dash="dot"))
    fig.add_trace(go.Scatter(x=[g[0]["time_s"] for g in groups], y=[float(th[g[0]["index"]]) for g in groups],
                             mode="markers+text", text=[str(n) for n in range(1, len(groups) + 1)], textposition="top center",
                             customdata=[len(g) for g in groups], marker=dict(size=8, color=fs.CONSTRUCTION), name="Olaylar",
                             hovertext=["<br>".join(f"{n}. {e['label']} · {e['time_s']:.4f} s" for e in g)
                                        for n, g in enumerate(groups, start=1)], hoverinfo="text"), 1, 1)
    _vline(fig, float(t[0]), dict(color="#d62728", width=2))          # cursor, moved by timeline_figure
    for r, sec, title in ((1, False, "θ [°]"), (1, True, "Devir [RPM]"), (2, False, "θ̇ [rad/s]"), (2, True, "θ̈ [rad/s²]"),
                          (3, False, "Kuvvet [N]"), (4, False, "Moment [N·m]"), (5, False, "İtki [N]"),
                          (5, True, "Aero pim momenti [N·m]")):
        fig.update_yaxes(title_text=title, row=r, col=1, secondary_y=sec)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified")
    fig.update_xaxes(title_text="Zaman [s]", row=5, col=1)
    return fig


def angle_figure(row, key, blade=0):
    a = arrays(row)
    th, rate, y = a["theta_deg"][:, blade], a["theta_rate_rad_s"][:, blade], a[f"load_{key}"][:, blade]
    fig = go.Figure()
    for sel, name, color in ((rate > 0.5, "Açılma (θ̇ > 0)", "#1f77b4"), (rate < -0.5, "Kapanma (θ̇ < 0)", "#ff7f0e"),
                             (np.abs(rate) <= 0.5, "Durağan / stopta", "#9ca3af")):
        fig.add_trace(go.Scatter(x=th[sel], y=y[sel], mode="markers", marker=dict(size=4, color=color), name=name))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Katlanma açısı θ [°]",
                      yaxis_title=f"{LOADS[key][0]} [{LOADS[key][1]}]", title=dict(text="Yük – katlanma açısı", font=dict(size=13)))
    return fig


def _parts_figure(row, a, parts, total, i, blade, focus, total_name):
    t = a["time_s"]
    parts = [(label, y) for label, y in parts if np.abs(y).max() > 0]
    fig = go.Figure()
    if len(parts) == 1:          # the only contribution is the total: one trace and a note instead of two identical lines
        fig.add_annotation(text=f"Tek katkı: {parts[0][0]} (toplamın kendisi)", xref="paper", yref="paper", x=0.01, y=0.99,
                           xanchor="left", yanchor="top", showarrow=False, font=dict(size=11))
    else:
        for label, y in parts:
            fig.add_trace(go.Scatter(x=t, y=y, name=label))
    fig.add_trace(_total(t, total, total_name))
    fig.add_vline(x=float(t[i]), line=dict(color="#d62728", width=2))
    if focus == "operating" and (rng := _operating_range(row, a, [total, *(y for _, y in parts)], blade)):
        fig.update_yaxes(range=rng)
    return fig


def contribution_figure(row, key, i, blade=0, focus="whole"):
    a = arrays(row)
    parts = [(label, _blade(a, f"contrib_{c}_{key}", blade)) for c, label in CONTRIB_LABEL.items() if f"contrib_{c}_{key}" in a]
    fig = _parts_figure(row, a, parts, a[f"load_{key}"][:, blade], i, blade, focus, "Toplam (bağlantıdan geçen)")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Zaman [s]",
                      yaxis_title=f"{LOADS[key][0]} [{LOADS[key][1]}]",
                      title=dict(text="Katkılar (açıklayıcı ayrıştırma; toplam bağlantı yüküdür)", font=dict(size=13)))
    return fig


def element_figure(row, i, blade=0, focus="whole"):
    a = arrays(row)
    parts = [(label, a[f"hinge_{k}_nm"][:, blade]) for k, label in ELEMENT_LABEL.items()]
    fig = _parts_figure(row, a, parts, a["load_M_pin"][:, blade], i, blade, focus, "Pim ekseni momenti (toplam)")
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Zaman [s]", yaxis_title="Moment [N·m]",
                      title=dict(text="Pim ekseni momentini taşıyan menteşe elemanları", font=dict(size=13)))
    return fig


def energy_figure(row, blade=0):
    a = arrays(row)
    t = a["time_s"]
    col = lambda k: _blade(a, k, blade)  # noqa: E731
    fig = go.Figure()
    for k, label in (("work_drive_j", "Mil işi (bağlantı üzerinden)"), ("work_aero_j", "Aerodinamik iş"), ("work_gravity_j", "Yerçekimi işi"),
                     ("work_actuator_j", "Aktüatör işi"), ("work_dissipated_j", "Sönümlenen enerji")):
        if k in a and np.abs(col(k)).max() > 0:
            fig.add_trace(go.Scatter(x=t, y=col(k), name=label))
    fig.add_trace(go.Scatter(x=t, y=col("kinetic_j") - col("kinetic_j")[0], name="Kinetik enerji değişimi"))
    fig.add_trace(go.Scatter(x=t, y=col("potential_j") - col("potential_j")[0], name="Yay/stop enerjisi değişimi"))
    fig.add_trace(go.Scatter(x=t, y=col("energy_residual_j"), name="Denge artığı", line=dict(color="#d62728", dash="dot")))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Zaman [s]",
                      yaxis_title=f"Enerji [J] (kanat {blade + 1} dış parça)")
    return fig


def playback(row, spec, frame="rotor", n_frames=80):
    """Built once per (record, frame, frame count)."""
    key = (row["result_sha256"], frame, n_frames, spec)
    if key not in _PLAYBACK:
        _PLAYBACK.clear()
        _PLAYBACK[key] = _playback(row, spec, frame, n_frames)
    return _PLAYBACK[key]


def _playback(row, spec, frame, n_frames):
    a = arrays(row)
    t = a["time_s"]
    mesh = mesh_for(spec)
    base = set(np.linspace(0, len(t) - 1, n_frames).round().astype(int).tolist())
    ev = {e["label"].split(" (")[0]: e["index"] for e in row["events"]}
    idx = sorted(base | set(ev.values()))
    frames = []
    for j in idx:
        psi = float(a["psi_rad"][j])
        thetas = [math.radians(x) for x in a["theta_deg"][j]]
        L = {k: float(a[f"load_{k}"][j][0]) for k in LOADS}
        frames.append({"name": str(j), "label": f"{t[j]:.3f} s".replace(".", ","), "psi": psi, "field": None, "mesh_opacity": 0.45,
                       "transforms": transforms(spec, thetas, psi), "extra": arrow_traces(row, spec, j, frame),
                       "text": (f"Öngörülen hareket (mekanik model) · t = {t[j]:.4f} s · {a['rpm'][j]:.0f} RPM · θ = {math.degrees(thetas[0]):.1f}° · "
                                f"θ̇ = {a['theta_rate_rad_s'][j][0]:.1f} rad/s · N = {L['N_tension']:.0f} N · V_t = {L['V_inplane']:.1f} N · "
                                f"M_z = {L['M_pin']:.2f} N·m · M_t = {L['M_bending']:.3f} N·m").replace(".", ",")})
    R = spec.tip_radius_m * 1000.0
    return bv.playback_figure(mesh, frames, frame_ms=120, events={k: str(v) for k, v in sorted(ev.items(), key=lambda kv: kv[1])},
                              view_rotation=(lambda f: -f["psi"]) if frame in ("rotor", "hinge") else None,
                              scene_ranges=((-1.1 * R, 1.1 * R), (-1.1 * R, 1.1 * R), (-0.35 * R, 0.5 * R)))


def series_csv(row) -> str:
    a = arrays(row)
    keys = ["time_s", "rpm", "omega_dot_rad_s2"]
    per_blade = ["theta_deg", "theta_rate_rad_s", "theta_acc_rad_s2", "aero_thrust_n", "aero_pin_torque_nm", "drive_torque_nm",
                 *(f"load_{k}" for k in LOADS), *(f"hinge_{k}_nm" for k in ELEMENT_LABEL)]
    blades = range(a["theta_deg"].shape[1])
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(keys + [f"{k}_blade{b + 1}" for k in per_blade for b in blades] + ["F_x_n", "F_y_n", "F_z_n", "M_x_nm", "M_y_nm", "M_z_nm"])
    for j in range(len(a["time_s"])):
        w.writerow([f"{a[k][j]:.7g}" for k in keys] + [f"{a[k][j][b]:.7g}" for k in per_blade for b in blades]
                   + [f"{x:.7g}" for x in a["F_global_n"][j]] + [f"{x:.7g}" for x in a["M_global_nm"][j]])
    return out.getvalue()


def compare_figure(rows, key):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("Katlanma açısı θ [°]", f"{LOADS[key][0]} [{LOADS[key][1]}]"))
    for n, r in enumerate(rows, start=1):
        a = _as_arrays(r)
        name = f"Ç{n}: {r['case']['schedule']['operating_rpm']:.0f} RPM · δ = {r['case']['mechanism']['axial_offset_m'] * 1000:.0f} mm"
        fig.add_trace(go.Scatter(x=a["time_s"], y=a["theta_deg"][:, 0], name=name), 1, 1)
        fig.add_trace(go.Scatter(x=a["time_s"], y=a[f"load_{key}"][:, 0], name=name, showlegend=False), 2, 1)
    fig.update_layout(height=520, margin=dict(l=10, r=10, t=40, b=10), xaxis2_title="Zaman [s]")
    return fig


def coupled_figure(comp, row, blade=0):
    t = comp["time_s"]
    b = comp["blades"][blade]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        subplot_titles=("Katlanma açısı θ [°]", "Bağlantı kuvvetleri [N]", "Bağlantı momentleri [N·m]"))
    fig.add_trace(go.Scatter(x=t, y=[x[blade] for x in comp["theta_deg"]], name="θ"), 1, 1)
    for k in ("N_tension", "V_inplane", "V_axial"):
        fig.add_trace(go.Scatter(x=t, y=b[k], name=LOADS[k][0]), 2, 1)
    for k in ("M_pin", "M_bending", "M_torsion"):
        fig.add_trace(go.Scatter(x=t, y=b[k], name=LOADS[k][0]), 3, 1)
    k0 = comp.get("startup_transient_windows", 0)
    if k0:
        for r in (1, 2, 3):
            fig.add_vrect(x0=t[0], x1=t[min(k0, len(t) - 1)], fillcolor="rgba(239,68,68,.12)", line_width=0, row=r, col=1)
    contact = [i for i, c in enumerate(comp["contact_active"]) if c[blade]]
    for i in contact:
        fig.add_vline(x=t[i], line=dict(color="rgba(245,158,11,.25)", width=2), row=2, col=1)
    fig.update_layout(height=720, margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified")
    fig.update_xaxes(title_text="Zaman [s]", row=3, col=1)
    return fig
