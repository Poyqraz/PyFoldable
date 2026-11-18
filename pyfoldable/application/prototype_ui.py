"""'Prototip': the normal workflow for the printable 13-inch folding-propeller prototype (``pyfoldable.prototype``).

Inputs edit one ``PrototypeDesign``; the build, the candidate exploration and the manufacturing export run only on
their own button. Each stored result carries the design identity it belongs to: changed inputs mark it stale and hide
its views and downloads, and a failed action replaces the previous result (fail closed). This is manufacturing
geometry (B-rep solids) for an assembly and mechanism prototype, separate from the display mesh and the mechanical
model; nothing here claims physical qualification.
"""
from __future__ import annotations

import copy
import io
import json
import math
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS
from pyfoldable.prototype import cad, checks, design, explore, export, fit, loads, strength, study

from . import figure_style
from . import research_ui as rui

_BUILD, _EXPLORE, _EXPORT, _OFFSETS = "_proto_build", "_proto_explore", "_proto_export", "_proto_offsets"
_FIT, _FIT_ERROR, _KITGEN = "_proto_fit_record", "_proto_fit_error", "_proto_kitgen"
KITS = {  # committed measurement kits (predictions, record template, printing set, protocol)
    "E": ("E · sonraki kompakt aday (kendi bağlantısı)", Path("reports/prototype_13in_20261118/fit_kit_E")),
    "B": ("B · referans", Path("reports/prototype_13in_20261118/fit_kit_B")),
}
KIT_FILES = ("README.md", "predictions.json", "fit_record_template.json", "design.json", "SHA256SUMS")
FOLD_STEP_DEG = 10.0
MESH_TOL_MM, MESH_ANGLE_RAD = 0.3, 0.5
PROXIMAL, DISTAL, HARDWARE = "#4C78A8", "#E45756", figure_style.CONSTRUCTION

# (design path, label, min, max); the widget key is "proto_" + path
_INPUTS = {
    "Planform": (
        ("planform.diameter_mm", "Çap [mm]", 150.0, 600.0),
        ("planform.chord_scale", "Kord çarpanı", 0.2, 3.0),
        ("planform.twist_scale", "Burulma çarpanı", 0.0, 3.0),
        ("connection.hinge_radius_mm", "Menteşe yarıçapı r_j [mm]", 20.0, 300.0),
        ("planform.hinge_zone_mm", "Menteşe bölgesi iç yarı genişliği [mm] (0: yok)", 0.0, 150.0),
        ("planform.hinge_zone_outboard_mm", "Menteşe bölgesi dış yarı genişliği [mm] (boş: iç ile aynı)", 1.0, 150.0),
        ("planform.hinge_chord_factor", "Menteşe bölgesi kord çarpanı", 0.2, 1.5),
        ("planform.hinge_twist_factor", "Menteşe bölgesi burulma çarpanı", 0.2, 1.5),
    ),
    "Bağlantı (tek lug, tek pim)": (
        ("connection.axial_offset_mm", "Eksenel ofset δ = z_B − z_A [mm]", -30.0, 30.0),
        ("connection.lug_interface_z_mm", "Lug arayüz düzlemi z_i [mm] (boş: δ/2)", -30.0, 30.0),
        ("connection.pin_x_mm", "Pim x, çeyrek veterden [mm]", -30.0, 30.0),
        ("connection.pin_diameter_mm", "Pim Ø [mm]", 1.0, 10.0),
        ("connection.hole_clearance_mm", "Delik boşluğu, çapsal [mm]", 0.0, 1.0),
        ("connection.lug_thickness_proximal_mm", "Proksimal lug kalınlığı [mm] (boş: tam derinlik)", 0.5, 30.0),
        ("connection.lug_thickness_distal_mm", "Distal lug kalınlığı [mm] (boş: tam derinlik)", 0.5, 30.0),
        ("connection.lug_gap_mm", "Lug aralığı g [mm]", 0.0, 3.0),
        ("connection.boss_radius_mm", "Lug yarıçapı R_b [mm]", 1.0, 20.0),
        ("connection.relief_clearance_mm", "Boşaltma payı [mm]", 0.0, 5.0),
        ("connection.face_gap_mm", "Uç yüz aralığı [mm]", 0.0, 5.0),
        ("connection.nose_depth_mm", "Stop burnu derinliği [mm]", 0.5, 20.0),
        ("connection.nose_extension_mm", "Burun uzantısı, hücum kenarı önü [mm]", 0.0, 20.0),
        ("connection.pad_depth_mm", "Stop pedi derinliği [mm]", 0.5, 20.0),
        ("connection.stowed_angle_deg", "Gerekli katlanma (kapalı açı) [°]", -180.0, -1.0),
        ("connection.body_clearance_mm", "Gerekli gövde boşluğu [mm]", 0.0, 5.0),
    ),
    "Baskı": (
        ("print_model.infill_fraction", "Doluluk oranı", 0.05, 1.0),
        ("print_model.wall_mm", "Çevre duvarı [mm]", 0.2, 5.0),
        ("print_model.bed_mm.0", "Tabla x [mm]", 50.0, 1000.0),
        ("print_model.bed_mm.1", "Tabla y [mm]", 50.0, 1000.0),
        ("print_model.bed_mm.2", "Tabla z [mm]", 50.0, 1000.0),
    ),
    "Çalışma (sahip girdileri)": (
        ("operating.max_rpm", "Azami devir [RPM] (boş: verilmedi)", 100.0, 50000.0),
        ("operating.distal_thrust_n", "Distal itki [N] (boş: yok)", -200.0, 200.0),
        ("operating.distal_drag_n", "Distal sürükleme [N] (boş: yok)", -200.0, 200.0),
        ("operating.distal_aero_radius_mm", "Aero kuvvet yarıçapı [mm]", 0.0, 1000.0),
        ("operating.safety_factor", "Güvenlik katsayısı", 1.0, 10.0),
    ),
    "Göbek (yer tutucu)": (
        ("hub_radius_mm", "Göbek yarıçapı [mm]", 2.0, 100.0),
        ("hub_height_mm", "Göbek yüksekliği [mm]", 1.0, 100.0),
        ("hub_bore_mm", "Göbek deliği Ø [mm]", 0.5, 100.0),
    ),
}
_AXES = (  # (design path, label, options, default) of the exploration grid; empty selection: axis not varied
    ("connection.axial_offset_mm", "Ofset δ [mm]", tuple(x / 2 for x in range(6, 25)), (5.0, 5.5, 6.0)),
    ("planform.twist_scale", "Burulma çarpanı", (1.0, 0.8, 0.6, 0.45, 0.35, 0.25), (1.0, 0.6, 0.35)),
    ("connection.lug_thickness_proximal_mm", "Proksimal lug kalınlığı [mm] (isteğe bağlı)", (3.0, 4.0, 5.0, 6.0), ()),
    ("connection.lug_thickness_distal_mm", "Distal lug kalınlığı [mm] (isteğe bağlı)", (3.0, 4.0, 5.0, 6.0), ()),
    ("connection.pin_diameter_mm", "Pim Ø [mm] (isteğe bağlı)", (2.5, 3.0, 4.0), ()),
)
_PROTRUSIONS = (
    ("proximal_boss_below_surface_mm", "Proksimal lug, alt yüzeyin altında"),
    ("distal_boss_above_surface_mm", "Distal lug, üst yüzeyin üstünde"),
    ("head_below_proximal_surface_mm", "Pim kafası, proksimal alt yüzeyin altında"),
    ("clip_above_distal_surface_mm", "Segman, distal üst yüzeyin üstünde"),
    ("lug_midplane_offset_mm", "Lug orta düzlem aralığı"),
    ("stack_thickness_mm", "Lug yığını"),
)
_f = rui._fmt


def _key(path):
    return "proto_" + path


def _r(value, digits=2):
    return None if value is None else round(float(value), digits)


def _default(base, path):
    obj = base
    for part in path.split("."):
        obj = obj[int(part)] if part.isdigit() else getattr(obj, part)
    return obj


# ------------------------------------------------------------------------------------------------------ inputs
def _inputs(base) -> dict:
    values = {}
    for group, fields in _INPUTS.items():
        with st.expander(group, expanded=group.startswith("Bağlantı")):
            if group == "Planform":
                values["planform.profile_id"] = rui._choice(st.selectbox, "Katalog profili", PROJECT_AIRFOIL_IDS,
                                                            key=_key("planform.profile_id"), default=base.planform.profile_id)
            if group == "Baskı":
                values["print_model.material"] = rui._choice(st.radio, "Malzeme", tuple(design.MATERIALS), horizontal=True,
                                                             key=_key("print_model.material"), default=base.print_model.material)
            if group.startswith("Çalışma"):
                st.caption("Aero kuvvetleri mutlak değerlerdir ve yalnız sahibin azami devrinde uygulanır.")
            cols = st.columns(3)
            for i, (path, label, lo, hi) in enumerate(fields):
                values[path] = rui._field(cols[i % 3].number_input, label, _key(path), _default(base, path),
                                          min_value=lo, max_value=hi)
    return values


def _design(root, values):
    v = dict(values)
    plan = {k.split(".", 1)[1]: v.pop(k) for k in list(v) if k.startswith("planform.")}
    plan["hinge_zone_center_mm"] = v["connection.hinge_radius_mm"]          # the shaping zone follows the joint
    v["print_model.bed_mm"] = tuple(v.pop(f"print_model.bed_mm.{i}") for i in range(3))
    return design.with_changes(design.default_design(root, **plan), **v)


def _planes(d):
    (p0, p1), (q0, q1) = d.lug_bands_mm
    return (f"Düzlem A: z = 0 (proksimal kesitlerin çeyrek veter düzlemi) · Düzlem B: z = δ = {_f(d.connection.axial_offset_mm)} mm "
            f"(distal) · lug arayüzü z_i = {_f(d.interface_z_mm)} mm · proksimal lug [{_f(p0)}, {_f(p1)}] mm · distal lug "
            f"[{_f(q0)}, {_f(q1)}] mm · yığın {_f(d.stack_thickness_mm)} mm · lug orta düzlem aralığı "
            f"{_f(d.lug_midplane_offset_mm)} mm · delik Ø{_f(d.hole_diameter_mm)} mm · pim boyu {_f(d.pin_length_mm)} mm "
            "(kafa altından).")


def _load(params):
    """Exploration axes back into the editor: set the widget keys before they render (a button callback)."""
    from . import fold_cycle_ui
    for path, value in params.items():
        fold_cycle_ui._reset(_key(path), value)


# ------------------------------------------------------------------------------------------------ build action
def _mesh(shape):
    # OCC keeps the finer 0.05 mm sweep mesh on the shape, so a fresh copy is meshed coarser (~2k triangles per part)
    v, f = cad.tessellate(copy.deepcopy(shape), MESH_TOL_MM, MESH_ANGLE_RAD)
    return np.round(v, 2), f


def _printability(parts):
    outs = export.build_outputs(parts)
    return checks.printability(parts.design, {k: outs[k] for k in export.PRINTABLE})


def _build(d):
    """Explicit action: evaluate, printability (needs the printable solids) and the preview. Any failure is the result."""
    with st.spinner("Katılar kuruluyor, katlanma taranıyor, kütle/yük/basılabilirlik hesaplanıyor (≈ 20 s)…"):
        try:
            r = explore.evaluate(d)
            if "parts" in r and "sweep" in r:
                if "printability" not in r:
                    r["printability"] = _printability(r["parts"])
                r["figure"] = assembly_figure(r["parts"], r["sweep"])
        except Exception as exc:  # noqa: BLE001 - every core failure is shown; no stale success stays visible
            return {"identity": d.identity, "error": f"{type(exc).__name__}: {exc}"}
    return {"identity": d.identity, "result": r}


# ----------------------------------------------------------------------------------------------------- figures
def _rotate(v, pivot, deg):
    """The rotation of cad.Parts.distal_at: about the pin axis (parallel to +z), right-handed, in degrees."""
    t = math.radians(deg)
    x, y = v[:, 0] - pivot[0], v[:, 1] - pivot[1]
    return np.column_stack([pivot[0] + x * math.cos(t) - y * math.sin(t), pivot[1] + x * math.sin(t) + y * math.cos(t), v[:, 2]])


def _mesh_trace(v, f, color, name):
    return go.Mesh3d(x=v[:, 0], y=v[:, 1], z=v[:, 2], i=f[:, 0], j=f[:, 1], k=f[:, 2], color=color, name=name,
                     showlegend=True, flatshading=True, hoverinfo="name")


def assembly_figure(parts, sweep):
    """Deployed assembly and a client-side fold playback: the distal posed every FOLD_STEP_DEG to the stowed angle."""
    stowed = parts.design.connection.stowed_angle_deg
    angles = [float(a) for a in np.arange(0.0, stowed, -FOLD_STEP_DEG)] + [stowed]
    vd, fd = _mesh(parts.distal)
    meshes = [(_mesh(parts.proximal), PROXIMAL, "Proksimal + göbek")]
    meshes += [(_mesh(s), HARDWARE, f"Donanım: {name}") for name, s in parts.hardware.items()]
    static = [_mesh_trace(*m, color, name) for m, color, name in meshes]
    clear = sweep["clear_travel_deg"]
    # one fixed scene box over every pose, so the playback does not rescale from frame to frame
    pts = np.vstack([m[0] for m, _, _ in meshes] + [_rotate(vd, parts.pin_axis, a) for a in angles])
    lo, hi = pts.min(axis=0) - 2.0, pts.max(axis=0) + 2.0
    box = (hi - lo) / (hi - lo).max()

    def distal(a):
        return _mesh_trace(_rotate(vd, parts.pin_axis, a), fd, DISTAL, "Distal")

    def title(a):
        return f"θ = {a:g}° · " + ("açık katlanma içinde" if -a <= clear else f"açık katlanmanın ({clear:.0f}°) ötesinde: temas/çakışma")
    # frames named by index: a stowed angle off the 10° grid must not share a name with the last grid pose
    frames = [go.Frame(data=[distal(a)], traces=[0], name=str(k), layout=dict(title_text=title(a))) for k, a in enumerate(angles)]
    still = dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))
    play = dict(mode="immediate", frame=dict(duration=400, redraw=True), transition=dict(duration=0), fromcurrent=True)
    fig = go.Figure(data=[distal(0.0), *static], frames=frames)
    fig.update_layout(
        height=620, title_text=title(0.0), margin=dict(l=0, r=0, t=40, b=90),
        legend=dict(x=0, y=1, xanchor="left", yanchor="top"),
        scene=dict(aspectmode="manual", aspectratio=dict(x=float(box[0]), y=float(box[1]), z=float(box[2])),
                   camera=dict(eye=dict(x=0.55, y=-0.45, z=0.55)),
                   xaxis=dict(title="x [mm] (veter)", range=[float(lo[0]), float(hi[0])], autorange=False, nticks=5),
                   yaxis=dict(title="y [mm] (açıklık)", range=[float(lo[1]), float(hi[1])], autorange=False),
                   zaxis=dict(title="z [mm] (mil, itki +z)", range=[float(lo[2]), float(hi[2])], autorange=False,
                              nticks=4)),
        updatemenus=[dict(type="buttons", showactive=False, direction="left", x=0, y=0, xanchor="left", yanchor="top",
                          buttons=[dict(label="▶", method="animate", args=[None, play]),
                                   dict(label="❚❚", method="animate", args=[[None], still])])],
        sliders=[dict(x=0.12, len=0.88, y=0, yanchor="top", currentvalue=dict(prefix="θ = ", suffix="°"),
                      steps=[dict(method="animate", label=f"{a:g}", args=[[f.name], still]) for f, a in zip(frames, angles)])])
    return fig


def clearance_figure(sw):
    th = sw["angles_deg"]

    def finite(ys):
        return [y if math.isfinite(y) else None for y in ys]
    fig = go.Figure([
        go.Scatter(x=th, y=finite(sw["gap_mm"]), name="Nominal boşluk", line=dict(color=figure_style.SERIES[0])),
        go.Scatter(x=th, y=finite(sw["gap_play_mm"]), name="En kötü oynama ile", line=dict(color=figure_style.SERIES[1], dash="dash")),
        go.Scatter(x=th, y=finite(sw["nose_gap_mm"]), name="Stop burnu boşluğu", line=dict(color=figure_style.SERIES[2])),
    ])
    fig.add_hline(y=sw["body_clearance_mm"], line=dict(color=figure_style.CONSTRUCTION, dash="dot"),
                  annotation_text="gerekli boşluk", annotation_position="bottom left")
    fig.add_vline(x=-sw["required_travel_deg"], line=dict(color=figure_style.CONSTRUCTION, dash="dot"),
                  annotation_text="gerekli katlanma", annotation_position="bottom right")
    fig.add_vline(x=-sw["clear_travel_deg"], line=dict(color=figure_style.ACCENT),
                  annotation_text="açık katlanma", annotation_position="top right")
    if sw.get("folded_stop_deg") is not None:
        fig.add_vline(x=-sw["folded_stop_deg"], line=dict(color=figure_style.SERIES[3], dash="dash"),
                      annotation_text="katlanmış stop (burun teması)", annotation_position="top left")
    fig.update_layout(height=430, xaxis_title="Katlanma açısı θ [°] (geri katlanma −)",
                      yaxis_title="Düşey boşluk [mm] (− girişim)")
    return fig


# ------------------------------------------------------------------------------------------------ result views
def _clearance(sw):
    rui._plot(clearance_figure(sw), "proto_clearance")
    stop = "yok (180° içinde)" if sw.get("folded_stop_deg") is None else f"{_f(sw['folded_stop_deg'], 0)}°"
    st.markdown(
        f"**Açık katlanma:** {_f(sw['clear_travel_deg'], 0)}° / gerekli {_f(sw['required_travel_deg'], 0)}° · gövdeler "
        f"{_f(sw['body_clear_to_deg'], 0)}°’ye kadar açık · katlanmış stop (burun teması): {stop}  \n"
        f"**En küçük boşluk:** {_f(sw['min_gap_mm'])} mm @ {_f(sw['min_gap_angle_deg'], 0)}° · en kötü oynama ile "
        f"{_f(sw['min_gap_play_mm'])} mm @ {_f(sw['min_gap_play_angle_deg'], 0)}°  \n"
        f"**Gereken ofset:** nominal ≈ {_f(sw['required_offset_mm'], 1)} mm · oynama ile ≈ "
        f"{_f(sw['required_offset_with_play_mm'], 1)} mm (açıktan tahmin; o ofsette yeniden oluşturup doğrulayın)")
    k = sw["angles_deg"].index(sw["min_gap_angle_deg"]) if sw["min_gap_angle_deg"] in sw["angles_deg"] else None
    where = sw["where"][k] if k is not None else None
    if where:
        st.markdown(f"**Belirleyici nokta:** x {_f(where[0], 1)} mm, y {_f(where[1], 1)} mm (pimden {_f(where[2], 1)} mm), "
                    f"{_f(-sw['min_gap_angle_deg'], 0)}° katlanmada: distal alt yüzeyi proksimal üst yüzeyine en yakın.")
    p = sw["play"]
    if sw.get("min_gap_transferred_mm") is not None:
        st.markdown(f"**Aktarılmış ölçümle (yalnız keşif, karar değil):** en küçük boşluk "
                    f"{_f(sw['min_gap_transferred_mm'])} mm · gereken ofset ≈ {_f(sw['required_offset_transferred_mm'], 1)} mm "
                    f"({p['transferred']['source']}).")
    st.caption(f"Karar oynaması: {p.get('source', 'model')}. Eğilme {_f(p['tilt_deg'])}° ({p['tilt_limited_by']}), uç sarkması "
               f"{_f(p['tip_droop_mm'])} mm; radyal {_f(p['radial_play_mm'])} mm, eksenel {_f(p['axial_play_mm'])} mm. "
               f"Yöntem: {sw['method']}. En küçük boşluk ve gereken ofset yalnız gerekli katlanma aralığını kapsar.")


def _alignment(al):
    a, b, c = st.columns(3)
    a.metric("Basamak δ [mm]", _f(al["step_mm"]))
    b.metric("Uç yüz aralığı [mm]", _f(al["face_gap_mm"]))
    c.metric("Burun, hücum kenarı önünde [mm]", _f(al["nose_ahead_of_le_mm"]))
    st.dataframe([{"Açık konumda": label, "Değer [mm]": _r(al[k], 3)} for k, label in _PROTRUSIONS],
                 hide_index=True, **figure_style.dataframe_width_kwargs())
    st.caption(f"Pim donanımı boşaltma yarıçapı (R {_f(al['relief_radius_mm'])} mm) içinde: "
               f"{'evet' if al['hardware_inside_relief'] else 'hayır'}.")


def envelope_figures(d, sw):
    """Deployed joint seen from the tip, folded plan envelope and the offset each required travel would need."""
    al, env, curve = study.alignment_sections(d), study.envelope(d, sw), study.required_by_travel(d, sw)
    side = go.Figure()
    for key, color, name in (("proximal", PROXIMAL, "Proksimal uç kesiti (z = 0)"),
                             ("distal", DISTAL, "Distal kök kesiti (z = δ)")):
        side.add_trace(go.Scatter(x=al[key][:, 0], y=al[key][:, 1], fill="toself", name=name, line=dict(color=color)))
    for key, color in (("lug_proximal", PROXIMAL), ("lug_distal", DISTAL)):
        x0, x1, z0, z1 = al[key]
        side.add_shape(type="rect", x0=x0, x1=x1, y0=z0, y1=z1, line=dict(color=color, dash="dash"))
    px, zb, zt = al["pin"]
    side.add_trace(go.Scatter(x=[px, px], y=[zb, zt], name="Pim seti", line=dict(color=HARDWARE, width=5)))
    for z, label in ((0.0, "düzlem A"), (al["delta_mm"], "düzlem B")):
        side.add_hline(y=z, line=dict(color=figure_style.CONSTRUCTION, dash="dot"), annotation_text=label)
    xs = np.concatenate([al["proximal"][:, 0], al["distal"][:, 0]])
    side.update_layout(height=420, xaxis_title="x, veter [mm] (hücum kenarı solda)", yaxis_title="z, şaft [mm]")
    side.update_xaxes(range=[float(xs.min()) - 3.0, float(xs.max()) + 6.0], constrain="domain")
    side.update_yaxes(scaleanchor="x")
    plan = go.Figure([
        go.Scatter(x=env["proximal"][:, 0], y=env["proximal"][:, 1], fill="toself", name="Proksimal", line=dict(color=PROXIMAL)),
        go.Scatter(x=env["distal"][:, 0], y=env["distal"][:, 1], name="Distal, açık", line=dict(color=DISTAL, dash="dot")),
        go.Scatter(x=env["folded"][:, 0], y=env["folded"][:, 1], fill="toself", name=f"Distal, {abs(env['fold_deg']):.0f}° katlı",
                   line=dict(color=DISTAL)),
    ])
    t = np.linspace(0.0, 2.0 * np.pi, 181)
    for r, dash, name in ((env["deployed_radius_mm"], "dot", "Açık uç dairesi"),
                          (env["folded_radius_mm"], "solid", f"Katlı zarf R {env['folded_radius_mm']:.0f} mm")):
        plan.add_trace(go.Scatter(x=r * np.cos(t), y=r * np.sin(t), name=name,
                                  line=dict(color=figure_style.CONSTRUCTION, dash=dash, width=1)))
    if env["critical"]:
        plan.add_trace(go.Scatter(x=[env["critical"][0]], y=[env["critical"][1]], mode="markers",
                                  name=f"Belirleyici temas ({abs(env['critical_angle_deg']):.0f}°)",
                                  marker=dict(symbol="star", size=13, color=figure_style.ACCENT)))
    plan.update_layout(height=680, xaxis_title="x [mm]", yaxis_title="y, açıklık [mm]")
    plan.update_xaxes(range=[-90, 90], constrain="domain")
    plan.update_yaxes(range=[-10, 175], scaleanchor="x")
    need = go.Figure([go.Scatter(x=[c["travel_deg"] for c in curve], y=[c["required_mm"] for c in curve], name="Nominal"),
                      go.Scatter(x=[c["travel_deg"] for c in curve], y=[c["required_with_play_mm"] for c in curve],
                                 name="Boşlukla", line=dict(dash="dash"))])
    need.add_hrect(y0=5.0, y1=6.0, fillcolor=figure_style.SERIES[0], opacity=0.15, line_width=0,
                   annotation_text="sahip hedefi 5–6 mm")
    need.update_layout(height=360, xaxis_title="Gerekli katlanma [°]", yaxis_title="Gereken ofset [mm]")
    return side, plan, need


def _envelope(d, sw):
    side, plan, need = envelope_figures(d, sw)
    b = study.offset_budget(d, sw)
    st.markdown(f"**Açık hizalama:** basamak δ {_f(d.connection.axial_offset_mm)} mm; menteşe kesitinin düşey yüksekliği "
                f"{_f(b['section_height_mm'])} mm (kord {_f(b['chord_mm'])} mm, burulma {_f(b['twist_deg'], 1)}°, yerel hatve "
                f"{_f(b['pitch_at_joint_in'])} in; 0,75R hatvesi {_f(b['pitch_075R_in'])} in).")
    rui._plot(side, "proto_alignment_side")
    rui._plot(plan, "proto_envelope_plan")
    st.markdown(f"**Gereken ofset bütçesi:** gereken {_f(b['required_mm'], 1)} mm = mekanizma tabanı "
                f"{_f(b['mechanism_floor_mm'], 1)} mm (kesit kalınlığı + gerekli boşluk; düz kanatta bile) + kanat payı "
                f"{_f(b['blade_term_mm'], 1)} mm (menteşe çevresindeki kesitlerin kord × sin β yüksekliği). Boşlukla "
                f"{_f(b['required_with_play_mm'], 1)} mm ({sw['play'].get('source', 'model')}).")
    rui._plot(need, "proto_offset_by_travel")
    dims = study.folded_dimensions(d, sw)
    st.markdown(f"**Katlı ölçüler** (tüm kanatlar, aerodinamik dış hatlar; stop burnu menteşede hücum kenarının ≈ "
                f"{_f(d.connection.nose_extension_mm, 0)} mm önüne çıkar). Açık çap {_f(2 * d.planform.tip_radius_mm, 1)} mm.")
    st.dataframe([{"Katlanma [°]": r["fold_deg"], "Katlanmış stop izin veriyor": "evet" if r["reachable"] else "hayır",
                   "Zarf çapı [mm]": _r(r["envelope_diameter_mm"], 1), "Boy, kanat ekseni [mm]": _r(r["length_mm"], 1),
                   "En [mm]": _r(r["width_mm"], 1),
                   "Çap küçülmesi": f"{max(0.0, 1 - r['envelope_diameter_mm'] / (2 * d.planform.tip_radius_mm)):.0%}",
                   "Gereken ofset [mm]": "—" if r["required_offset_mm"] is None else f"{r['required_offset_mm']:.1f}",
                   "Boşlukla [mm]": "—" if r["required_offset_with_play_mm"] is None
                   else f"{r['required_offset_with_play_mm']:.1f}"} for r in dims],
                 hide_index=True, **figure_style.dataframe_width_kwargs())
    st.caption("Belirleyici temas genellikle distal firar kenarı kökünün proksimal hücum kenarı bölgesinin üstünden "
               "geçtiği yerdir (pimden yaklaşık bir veter içeride). Pim konumu bunu az değiştirir; pimi geri almak "
               "merkezkaç oturmasını kaldırır.")


def _mass(mp):
    st.dataframe([{"Parça": label, "Kütle [g]": _r(mp[k].mass_g), **{f"CG {a} [mm]": _r(c) for a, c in zip("xyz", mp[k].cg_mm)},
                   "Yöntem": mp[k].method}
                  for k, label in (("proximal", "Proksimal + göbek sektörü"), ("distal", "Distal"), ("pin_set", "Pim seti"),
                                   ("blade", "Kanat (toplam)"))],
                 hide_index=True, **figure_style.dataframe_width_kwargs())
    st.markdown("**FoldMechanism eşdeğeri** (dynamics.fold_cycle: katı distal, pim etrafında)")
    st.json(mp["fold"], expanded=True)
    st.caption(f"Veter yönünde CG ofseti {_f(mp['fold']['chordwise_cg_offset_mm'])} mm (+: pimin arkasında); açık stop "
               "momentini belirler. fold_cycle v1 CG’yi pimden geçen açıklık çizgisine koyar ve bu ofseti temsil edemez. "
               "Basılı parçalar tartılana kadar tahmin.")


def _loads(r):
    d, parts, mp = r["design"], r["parts"], r["mass"]
    o = d.operating
    cases = {f"{rpm:.0f} RPM (varsayımsal)": loads.deployed(mp["distal"], d, parts.meta, rpm) for rpm in o.what_if_rpm}
    owner = loads.owner_case(mp["distal"], d, parts.meta)
    if owner is None:
        st.warning("Sahibin azami devri verilmedi: aşağıdaki devirler varsayımsal (what-if) değerlerdir, bir çalışma "
                   "noktası değildir.")
    else:
        cases[f"{o.max_rpm:.0f} RPM (sahibin azami devri{', aero dahil' if owner['aero_included'] else ''})"] = owner
    st.dataframe([{"Durum": k, "Merkezkaç [N]": _r(math.hypot(*L["centrifugal_force_n"][:2]), 1),
                   "Stop kuvveti [N]": _r(L["stop_force_n"], 1), "Pim kuvveti, düzlem içi [N]": _r(L["pin_force_inplane_n"], 1),
                   "Kuvvet çifti, düzlem içi [N·mm]": _r(L["pin_couple_inplane_nmm"], 0),
                   "Stopa oturuyor": "evet" if L["seated"] else "hayır", "Açma momenti [N·mm]": _r(L["deploy_moment_nmm"], 0)}
                  for k, L in cases.items()], hide_index=True, **figure_style.dataframe_width_kwargs())
    labels = tuple(cases)
    default = labels[-1] if owner is not None else next(
        (k for k in labels if k.startswith(f"{explore.REFERENCE_RPM:.0f} ")), labels[0])
    pick = rui._choice(st.selectbox, "Dayanım kontrolleri için devir", labels, key="proto_loads_rpm", default=default)
    rows = strength.checks(cases[pick], d, parts.meta)
    st.dataframe([{"Kontrol": x["label"], "Gerilme [MPa]": _r(x["stress_mpa"]), "İzin verilen [MPa]": _r(x["allowable_mpa"], 1),
                   f"Pay (GK {o.safety_factor:g})": _r(x["margin"]), "Devir sınırı [RPM]": _r(x["rpm_limit"], 0),
                   "Kaynak": x["source"]} for x in rows], hide_index=True, **figure_style.dataframe_width_kwargs())
    gov = strength.governing(rows)
    if gov is not None:
        st.markdown(f"**Belirleyici kontrol:** {gov['label']} · devir sınırı ≈ {gov['rpm_limit']:.0f} RPM "
                    f"(güvenlik katsayısı {o.safety_factor:g})")
    else:
        st.caption("Aero kuvvetleri dahil: kuvvetler mutlak verildiği için devirle ölçekleme ve devir sınırı yok.")
    st.caption(strength.SCOPE)


def _export(parts, evaluation=None):
    """Explicit action: every manufacturing output into a temporary folder, returned as one zip with its file sums."""
    d = parts.design
    name = f"{d.name}_{d.identity[:8]}"
    with st.spinner("Üretim dosyaları yazılıyor (≈ 30–60 s)…"):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / name
                out = export.export_candidate(parts, folder, evaluation)
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    for p in sorted(folder.rglob("*")):
                        if p.is_file():
                            z.write(p, f"{name}/{p.relative_to(folder).as_posix()}")
                summary = (folder / "summary.md").read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - a failed export is shown and no earlier package is offered
            return {"identity": d.identity, "error": f"{type(exc).__name__}: {exc}"}
    return {"identity": d.identity, "zip": buf.getvalue(), "name": name + ".zip", "files": out["files"], "summary": summary}


def _export_section(parts, evaluation=None):
    st.markdown("**Üretim dosyaları**")
    st.caption("STEP/STL/3MF parçalar (mm), açık ve katlanmış montaj STEP’i, montaj resmi PDF/SVG, summary.md, "
               "assembly_instructions.md, hardware_list.csv, report.json, README.md ve SHA256SUMS; tek zip.")
    if st.button("Üretim dosyalarını hazırla", key="proto_export"):
        st.session_state[_EXPORT] = _export(parts, evaluation)
    ex = st.session_state.get(_EXPORT)
    if ex is None or ex["identity"] != parts.design.identity:
        return
    if "error" in ex:
        st.error("Üretim dosyaları hazırlanamadı: " + ex["error"])
        return
    st.download_button("Üretim paketini indir (.zip)", ex["zip"], ex["name"], "application/zip", key="proto_download")
    st.dataframe([{"Dosya": n, "SHA-256": h} for h, n in ex["files"]], hide_index=True,
                 **figure_style.dataframe_width_kwargs())
    with st.expander("summary.md"):
        st.markdown(ex["summary"])


def _results(r):
    d = r["design"]
    if "parts" not in r:
        st.error("Geometri kurulamadı: " + " · ".join(r["reasons"]))
        return
    if not {"sweep", "mass", "loads", "strength", "printability", "figure"} <= r.keys():
        st.error("Kontroller tamamlanamadı: " + (" · ".join(r["reasons"]) or "bilinmeyen hata"))
        return
    failed = [x["check"] for x in r["printability"] if not x["ok"]]
    st.markdown(f"**Kontrol sonucu:** {'uygun' if r['eligible'] and not failed else 'uygun değil'} · kimlik `{d.identity[:12]}`")
    for reason in r["reasons"]:
        st.warning(reason)
    if failed:
        st.warning("Basılabilirlik kontrolü geçmedi: " + " · ".join(failed))
    tabs = st.tabs(("3B montaj", "Katlanma açıklığı", "Açık hizalama ve katlı zarf", "Kütle", "Yükler ve dayanım",
                    "Basılabilirlik"))
    with tabs[0]:
        st.caption("Mavi proksimal (göbek ile), kırmızı distal, gri pim seti; oynatma distali pim etrafında "
                   f"{FOLD_STEP_DEG:.0f}°’lik adımlarla kapalı açıya kadar döndürür. Önizleme ağı kabadır; ölçüler katılardan.")
        rui._plot(r["figure"], "proto_assembly")
    with tabs[1]:
        _clearance(r["sweep"])
    with tabs[2]:
        _alignment(r["alignment"])
        _envelope(d, r["sweep"])
    with tabs[3]:
        _mass(r["mass"])
    with tabs[4]:
        _loads(r)
    with tabs[5]:
        st.dataframe([{"Kontrol": x["check"], "Değer": x["value"], "Sonuç": "uygun" if x["ok"] else "UYGUN DEĞİL",
                       "Not": x["note"]} for x in r["printability"]], hide_index=True, **figure_style.dataframe_width_kwargs())
    _export_section(r["parts"], r)


# ------------------------------------------------------------------------------------------------- exploration
def _explore(d, root, axes):
    bar = st.progress(0.0, text="Adaylar değerlendiriliyor…")

    def progress(i, n, params):
        bar.progress(i / n, text=f"Aday {i + 1}/{n}: " + ", ".join(f"{k.split('.')[-1]} {v}" for k, v in params.items()))
    try:
        out = explore.run(d, root, axes, progress=progress)
        params = [p for p, _ in out["results"]]
        # the table stays current for its base and for any of its candidates loaded into the editor
        current = {d.identity} | {explore.candidate_design(d, root, p).identity for p in params}
    except Exception as exc:  # noqa: BLE001 - a failed exploration replaces the previous table
        return {"identity": d.identity, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        bar.empty()
    return {"identity": d.identity, "current": current, "rows": out["rows"], "alternatives": out["alternatives"],
            "params": params, "reference_rpm": out["reference_rpm"], "owner_rpm": d.operating.max_rpm is not None}


def _exploration(root, d, errors):
    st.subheader("Aday keşfi")
    st.caption("Ofset ve planform (isteğe bağlı lug ve pim) ızgarası: her aday için katılar, tam katlanma açıklığı, "
               "hizalama ve kütle; uygun adaylar için referans devirde yük ve dayanım. Elenen adaylar gerekçeleriyle "
               "tabloda kalır. Sonuç bir seçenek tablosudur, tek bir optimum değildir.")
    axes = {}
    cols = st.columns(len(_AXES))
    for col, (path, label, options, default) in zip(cols, _AXES):
        key = _key("axis_" + path)
        chosen = rui._remember(key, col.multiselect(label, options, default=list(rui._seed(key, list(default))), key=key))
        if chosen:
            axes[path] = list(chosen)
    n = math.prod(len(v) for v in axes.values()) if axes else 0
    st.caption(f"{n} aday · üst sınır {explore.MAX_CANDIDATES} · aday başına ≈ 15 s")
    if n > explore.MAX_CANDIDATES:
        st.warning("Aday sayısı üst sınırı aşıyor; eksenleri daraltın.")
    if st.button("Adayları değerlendir", key="proto_explore", disabled=bool(errors) or not 0 < n <= explore.MAX_CANDIDATES):
        st.session_state[_EXPLORE] = _explore(d, root, axes)
    ex = st.session_state.get(_EXPLORE)
    if ex is not None:
        _candidates(ex, d)
    if st.button("Gerekli ofset tablosunu hesapla (6 planform, ≈ 12 değerlendirme, birkaç dakika)", key="proto_offsets",
                 disabled=bool(errors)):
        with st.spinner("Her planform için gereken ofset hesaplanıp o ofsette yeniden kontrol ediliyor…"):
            try:
                st.session_state[_OFFSETS] = {"identity": d.identity, "rows": explore.required_offset_table(d, root)}
            except Exception as exc:  # noqa: BLE001
                st.session_state[_OFFSETS] = {"identity": d.identity, "error": f"{type(exc).__name__}: {exc}"}
    off = st.session_state.get(_OFFSETS)
    if off is not None and off["identity"] == d.identity:
        if "error" in off:
            st.error("Gerekli ofset tablosu hesaplanamadı: " + off["error"])
        else:
            st.dataframe([{**x, "error": " · ".join(x["error"])} if "error" in x else x for x in off["rows"]],
                         hide_index=True, **figure_style.dataframe_width_kwargs())


def _candidates(ex, d):
    if "error" in ex:
        st.error("Keşif çalıştırılamadı: " + ex["error"])
        return
    if d.identity not in ex["current"]:
        st.warning(f"Girdiler değişti: aday tablosu (taban kimlik {ex['identity'][:8]}) güncel değil ve gizlendi; "
                   "adayları yeniden değerlendirin.")
        return
    st.caption(f"Yük ve dayanım sütunları referans devirde: {ex['reference_rpm']:.0f} RPM"
               + ("" if ex["owner_rpm"] else " (varsayımsal; sahibin azami devri verilmedi)")
               + "; aero kuvvetleri dahil değil (yalnız merkezkaç).")
    st.dataframe([{"#": i + 1, **row} for i, row in enumerate(ex["rows"])], hide_index=True,
                 **figure_style.dataframe_width_kwargs())
    params = ex["params"]

    def show(i):
        if not isinstance(i, int) or not 0 <= i < len(params):
            return str(i)       # Streamlit 1.40 AppTest passes the formatted label back
        return (f"#{i + 1} · " + ", ".join(f"{k.split('.')[-1]} {v}" for k, v in params[i].items())
                + (" · uygun" if ex["rows"][i]["uygun"] else " · elendi"))
    if ex["alternatives"]:
        st.markdown("**Seçenekler (uygun adaylar arasından)**")
        st.dataframe([{"Seçenek": a["label"], "Aday": show(params.index(a["params"])) if a["params"] in params else str(a["params"]),
                       "Kimlik": a["identity"], "Tekrar": "evet" if a["duplicate"] else "hayır"} for a in ex["alternatives"]],
                     hide_index=True, **figure_style.dataframe_width_kwargs())
    else:
        st.info("Uygun aday yok: gerekçeler tabloda.")
    pick = rui._choice(st.selectbox, "Düzenleyiciye yüklenecek aday", tuple(range(len(params))), key="proto_candidate",
                       default=0, display=show)
    st.button("Seçili adayın parametrelerini düzenleyiciye yükle", key="proto_load", on_click=_load, args=(params[pick],),
              help="Yalnız keşif eksenlerinin değerleri yüklenir; sonra geometriyi yeniden oluşturun.")


# ------------------------------------------------------------------------------------------- measurement record
@st.cache_data(show_spinner=False, max_entries=4)
def _kit_zip(folder: str, sums: str) -> bytes:
    """Printing set and protocol of a kit (3MF, README, predictions, record template, design, SHA-256 sums); STEP and
    STL copies stay out (large, regenerable). ``sums`` keys the cache to the kit's content."""
    return _zip_kit(Path(folder))


def _zip_kit(base: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in [*(base / n for n in KIT_FILES), *sorted((base / "3mf").glob("*.3mf"))]:
            if f.is_file():
                z.write(f, f"{base.name}/{f.relative_to(base).as_posix()}")
    return buf.getvalue()


def _measurement(root: Path, d):
    st.subheader("Ölçüm prototipi (delik kuponu ve kısa uyum çifti)")
    st.caption("Kupon ve uyum çifti pim geçmesi, eksenel/eğilme boşluğu, sürtünme ve stop oturması için basılıp ölçülür; "
               "bir kiti seçmek o adayı güçlü pervane olarak seçmez. Bir kitin ölçümü yalnız kendi tasarımı için doğrudan "
               "kanıttır; başka tasarıma uygulanınca aktarılmış sayılır (yalnız keşif, karar en kötü durum modelinde).")
    st.caption("Düzenleyicideki tasarım kitlerden farklıysa (ör. başka bir δ), ölçüm ancak kendi uyum çiftiyle doğrudan "
               "kanıt olur:")
    if st.button("Bu tasarımın ölçüm kitini oluştur (≈ 1–2 dk)", key="proto_kitgen", disabled=bool(design.validate(d))):
        st.session_state[_KITGEN] = _make_kit(d)
    gen = st.session_state.get(_KITGEN)
    if gen is not None:
        if gen["identity"] != d.identity:
            st.warning("Girdiler değişti: oluşturulan ölçüm kiti bu tasarıma ait değil ve gizlendi; yeniden oluşturun.")
        elif "error" in gen:
            st.error("Ölçüm kiti oluşturulamadı: " + gen["error"])
        else:
            st.download_button(f"{gen['name']}.zip indir", gen["zip"], f"{gen['name']}.zip", "application/zip",
                               key="proto_kitgen_zip")
    generated = gen is not None and gen["identity"] == d.identity and "pred" in gen
    options = {**{k: v[0] for k, v in KITS.items()}, **({"G": "Bu tasarım için oluşturulan kit"} if generated else {})}
    choice = rui._choice(st.radio, "Ölçüm kiti", tuple(options), horizontal=True, key="proto_fit_kit", default="E",
                         display=lambda k: options.get(k, str(k)))
    if choice == "G":
        pred, tpl, kit = gen["pred"], fit.template(gen["pred"]), Path(gen["name"])
    else:
        kit = Path(root) / KITS[choice][1]
        try:
            pred = json.loads((kit / "predictions.json").read_text(encoding="utf-8"))
            tpl = (kit / "fit_record_template.json").read_text(encoding="utf-8")
            sums = (kit / "SHA256SUMS").read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            st.info(f"Ölçüm kiti bulunamadı ({type(exc).__name__}).")
            return
    tp, td = pred["lug_thicknesses_mm"]
    st.caption(f"Kit {pred['kit_design_name']} (kimlik {pred['kit_design_sha256'][:12]}): lug {_f(tp)} / {_f(td)} mm, "
               f"uyum çifti delik boşlukları {', '.join(_f(c) for c in pred['fit_pair_clearances_mm'])} mm, yük kolu "
               f"{_f(pred['lever_mm'])} mm, katlanmış stop {_f(pred['folded_stop_deg'], 0)}°. Protokol: kitin README.md "
               "dosyası.")
    a, b = st.columns(2)
    if choice != "G":                                    # the generated kit's zip is offered by its own button above
        a.download_button("Ölçüm kitini indir (3MF + protokol, zip)", _kit_zip(str(kit), sums), f"{kit.name}.zip",
                          "application/zip", key="proto_fit_kit_zip")
    b.download_button("Ölçüm kaydı şablonunu indir (JSON)", tpl.encode("utf-8"), f"{kit.name}_record.json",
                      "application/json", key="proto_fit_template")
    text = st.text_area("Doldurulmuş ölçüm kaydı (JSON yapıştırın)", key="proto_fit_text", height=140)
    st.button("Kaydı doğrula ve tasarıma uygula", key="proto_fit_apply", disabled=not text.strip(),
              on_click=_apply_record, args=(pred,))      # a callback: the whole run below sees the new state
    if st.session_state.get(_FIT_ERROR):
        st.error("Ölçüm kaydı kullanılamadı (hiçbir şey uygulanmadı): " + st.session_state[_FIT_ERROR])
    held = st.session_state.get(_FIT)
    if held is not None and not design.validate(d):
        out = fit.apply(d, held["record"], held["pred"])
        st.dataframe([{"Büyüklük": r["quantity"], "Model": r["model"], "Ölçüm": r["measured"], "Birim": r["unit"],
                       "Not": r["note"]} for r in out["rows"]], hide_index=True, **figure_style.dataframe_width_kwargs())
        for w in out["warnings"]:
            st.warning(w)
        st.button("Ölçüm kaydını kaldır", key="proto_fit_clear", on_click=lambda: st.session_state.pop(_FIT, None))


def _make_kit(d):
    """Explicit action: the measurement kit of the editor's design (coupon, fit pairs, protocol, record template)."""
    name = f"fit_kit_{d.name}_{d.identity[:8]}"
    with st.spinner("Ölçüm kiti kuruluyor (kupon, üç uyum çifti, protokol)…"):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = fit.export_kit(d, Path(tmp) / name)
                return {"identity": d.identity, "name": name, "zip": _zip_kit(Path(tmp) / name),
                        "pred": out["predictions"]}
        except Exception as exc:  # noqa: BLE001 - a failed kit is a visible result, never a stale success
            return {"identity": d.identity, "error": f"{type(exc).__name__}: {exc}"}


def _apply_record(pred):
    st.session_state.pop(_FIT, None)                     # fail closed: a failed paste never leaves an older record
    st.session_state.pop(_FIT_ERROR, None)
    try:
        st.session_state[_FIT] = {"record": fit.parse(st.session_state.get("proto_fit_text", ""), pred), "pred": pred}
    except fit.RecordError as exc:
        st.session_state[_FIT_ERROR] = str(exc)


def _with_record(d):
    """The design with an applied fit record (measured clearance and play); its identity changes with the record."""
    held = st.session_state.get(_FIT)
    if held is None:
        return d
    try:
        out = fit.apply(d, held["record"], held["pred"])
    except ValueError as exc:                      # e.g. a pin outside the hinge section: the editor shows the error
        st.error(f"Ölçüm kaydı bu tasarıma uygulanamadı: {exc}")
        return d
    c = out["design"].connection
    verdict = ("boşluklu açıklık kararı bu ölçümü k = 2 genişletilmiş belirsizlikle kullanır" if out["basis"] == "direct"
               else "aktarılmış ölçüm (başka tasarımın kiti): yalnız keşifte gösterilir, boşluklu açıklık kararı en kötü "
                    "durum modelinde kalır")
    st.info(f"Ölçüm kaydı uygulanıyor (kit {held['pred']['kit_design_name']} {held['pred']['kit_design_sha256'][:8]}, "
            f"özet {out['record_sha256'][:12]}, "
            f"{'doğrudan' if out['basis'] == 'direct' else 'aktarılmış'}): delik boşluğu {_f(c.hole_clearance_mm)} mm, "
            f"eksenel boşluk {_f(c.measured_axial_play_mm)} ± {_f(c.measured_axial_play_u_mm, 3)} mm, eğilme "
            f"{_f(c.measured_tilt_deg)} ± {_f(c.measured_tilt_u_deg, 3)}° (standart belirsizlik); {verdict}.")
    return out["design"]


# ---------------------------------------------------------------------------------------------------------- page
def render_prototype(root: Path):
    head = st.container()
    base = design.default_design(root)
    values = _inputs(base)
    try:
        d, problem = _design(root, values), None
    except (TypeError, ValueError, OSError) as exc:
        d, problem = None, str(exc)
    with head:
        st.subheader("Prototip · basılabilir 13 inç katlanır pervane")
        st.caption("Montaj ve mekanizma prototipi için üretim geometrisi: B-rep katılar (build123d/OpenCASCADE), "
                   "STEP/STL/3MF. Tasarım ve Görseller’deki görüntüleme ağından ve açılma–kapanma çevrimindeki mekanik "
                   "modelden ayrıdır. Ağır hesaplar yalnız kendi düğmesiyle başlar. Fiziksel yeterlilik: yok.")
        st.warning("**Eksik sahip girdileri**\n\n" + "\n".join(f"- {m}" for m in (d or base).missing_owner_inputs()))
    if d is None:
        st.error("Tasarım kurulamadı: " + problem)
        return
    d0, d = d, _with_record(d)
    errors = design.validate(d)
    if not errors:
        st.caption(_planes(d))
    o = d.operating
    aero = o.distal_thrust_n is not None or o.distal_drag_n is not None
    if aero and o.distal_aero_radius_mm is None:
        errors.append("Distal itki veya sürükleme verildiğinde aero kuvvet yarıçapı da girilmeli.")
    for e in errors:
        st.error(e)
    if aero and o.max_rpm is None:
        st.warning("Aero kuvvetleri azami devir girilmeden hiçbir hesaba girmez.")
    st.caption(f"Tasarım kimliği {d.identity[:12]} (içerik özeti; doğruluk göstermez).")
    if st.button("Geometriyi oluştur ve kontrol et", key="proto_build", type="primary", disabled=bool(errors),
                 help="Katılar, tam katlanma açıklığı, hizalama, kütle, yükler ve basılabilirlik (≈ 20 s)."):
        st.session_state[_BUILD] = _build(d)
    res = st.session_state.get(_BUILD)
    if res is None:
        st.info("Henüz geometri oluşturulmadı: girdileri ayarlayıp düğmeyle başlatın.")
    elif res["identity"] != d.identity:
        st.warning(f"Girdiler değişti: son oluşturulan geometri (kimlik {res['identity'][:8]}) güncel değil. Görünümler ve "
                   "indirmeler gizlendi; yeniden oluşturun.")
    elif "error" in res:
        st.error("Geometri oluşturulamadı veya kontrol edilemedi: " + res["error"])
    else:
        _results(res["result"])
    _exploration(root, d, errors)
    _measurement(root, d0)
