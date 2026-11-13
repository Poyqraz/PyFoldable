"""Plotly views and exports of the lofted 3-D blade (design, BEM results, coupled playback).

Geometry is reconstructed from the catalog profile and the design stations (``visualization.blade_surface``);
analysis values are strips (``visualization.blade_results``) and are drawn only on the analysed surface.
Units in the figures are millimetres. Kept free of Streamlit so it can be tested directly.
"""
from __future__ import annotations

import io
import math

import numpy as np
import plotly.graph_objects as go

from pyfoldable.visualization import blade_surface as bs

FIXED, MOVABLE, JOINT, NODATA, PLACEHOLDER = "#008579", "#DC671D", "#9AA7B4", "#B9C2CB", "#76889A"
KIND_LABEL = {"per_span": "birim açıklık başına", "element_total": "eleman toplamı", "section_state": "kesit durumu"}
REGION_ID = {"aero": 0, "joint": 1, "undefined": 2}


def _per_blade(value, n):
    return list(value) if isinstance(value, (list, tuple)) else [value] * n


def _posed(mesh, fold_deg, azimuth):
    return mesh.posed(math.radians(fold_deg), azimuth) * 1000.0


def _mesh_trace(v, faces, name, *, color=None, intensity=None, crange=None, colorscale="Viridis", opacity=1.0,
                hover=None, showscale=False, colorbar=None, legendgroup=None, showlegend=True):
    if not len(faces):
        return None
    used, inv = np.unique(faces, return_inverse=True)
    f = inv.reshape(faces.shape)
    kw = dict(x=v[used, 0], y=v[used, 1], z=v[used, 2], i=f[:, 0], j=f[:, 1], k=f[:, 2], name=name, opacity=opacity,
              flatshading=False, lighting=dict(ambient=0.55, diffuse=0.75, specular=0.25, roughness=0.5, fresnel=0.1),
              lightposition=dict(x=2000, y=1500, z=3000), legendgroup=legendgroup or name, showlegend=showlegend)
    if intensity is not None:
        kw.update(intensity=intensity, intensitymode="cell", colorscale=colorscale, cmin=crange[0], cmax=crange[1],
                  showscale=showscale, colorbar=colorbar, hoverinfo="skip")
    else:
        kw.update(color=color, hovertemplate=(hover or name) + "<extra></extra>")
    return go.Mesh3d(**kw)


def _stack(parts):
    """Concatenate (vertices, faces[, values]) blocks into one vertex/face array."""
    vs, fs, vals, base = [], [], [], 0
    for item in parts:
        v, f = item[0], item[1]
        vs.append(v); fs.append(f + base); base += len(v)
        if len(item) > 2:
            vals.append(item[2])
    v = np.vstack(vs) if vs else np.zeros((0, 3))
    f = np.vstack(fs) if fs else np.zeros((0, 3), int)
    return v, f, (np.concatenate(vals) if vals else None)


def default_transforms(mesh, fold_deg=0.0, rotor_azimuth_rad: float = 0.0) -> list:
    """Per blade f(points_body_m, moving_mask) -> world [m]: rigid fold about the hinge axis, blade azimuth."""
    spec = mesh.spec
    folds = _per_blade(fold_deg, spec.blade_count)
    return [(lambda p, m, b=b: bs.pose_points(p, m, spec.hinge_radius_m, math.radians(folds[b]),
                                              rotor_azimuth_rad + 2.0 * math.pi * b / spec.blade_count))
            for b in range(spec.blade_count)]


def blade_figure(mesh, *, fold_deg=0.0, field=None, crange=None, rotor_azimuth_rad: float = 0.0, contacts=None,
                 selected_radius_m: float | None = None, colorscale: str = "Viridis", extra_traces=(),
                 height: int = 560, uirevision: str | None = None, transforms=None, view_rotation_rad: float = 0.0,
                 scene_ranges=None, contact_angle_deg: float | None = None):
    """All blades of the rotor; ``fold_deg`` and ``field`` may be given per blade (lists). ``transforms`` (per
    blade, e.g. from accepted MBDyn states) override the fold/azimuth posing; ``view_rotation_rad`` rotates the
    whole scene about the shaft (a rotor-relative view uses minus the rotor azimuth)."""
    spec = mesh.spec
    B = spec.blade_count
    folds, fields = _per_blade(fold_deg, B), _per_blade(field, B)
    tf = transforms or default_transforms(mesh, folds, rotor_azimuth_rad)
    view = (lambda p: _rot(p, view_rotation_rad)) if view_rotation_rad else (lambda p: p)
    moving_v = mesh.vertex_part == "distal"
    fig = go.Figure()
    side = np.isin(mesh.region, ("aero", "joint"))
    blocks = {k: [] for k in ("fixed", "movable", "joint", "result", "nodata", "placeholder")}
    for b in range(B):
        v = view(tf[b](mesh.vertices, moving_v)) * 1000.0
        if fields[b] is not None:
            from pyfoldable.visualization import blade_results as br
            vals = br.face_values(mesh, fields[b])
            ok = side & np.isfinite(vals)
            blocks["result"].append((v, mesh.faces[ok], vals[ok]))
            blocks["nodata"].append((v, mesh.faces[side & ~ok]))
        else:
            blocks["fixed"].append((v, mesh.faces[(mesh.region == "aero") & (mesh.face_part == "proximal")]))
            blocks["movable"].append((v, mesh.faces[(mesh.region == "aero") & (mesh.face_part == "distal")]))
            blocks["joint"].append((v, mesh.faces[mesh.region == "joint"]))
        blocks["placeholder"].append((v, mesh.faces[mesh.region == "undefined"]))
    if fields[0] is not None:
        f0 = fields[0]
        v, f, vals = _stack(blocks["result"])
        lo, hi = crange if crange is not None else (float(np.nanmin(vals)), float(np.nanmax(vals)))
        title = f"{f0.label}<br>[{f0.unit}] · {KIND_LABEL[f0.kind]}"
        fig.add_trace(_mesh_trace(v, f, "Sonuç: " + f0.label, intensity=vals, crange=(lo, hi), colorscale=colorscale,
                                  showscale=True, colorbar=dict(title=dict(text=title, side="right"), len=0.75)))
        v, f, _ = _stack(blocks["nodata"])
        t = _mesh_trace(v, f, "Kesit sonu / menteşe kesimi (sonuç yok)", color=NODATA)
        if t is not None:
            fig.add_trace(t)
        _strip_markers(fig, mesh, fields, tf, view)
    else:
        for key, name, color, hover in (
                ("fixed", "Sabit iç parça", FIXED, "Sabit iç parça (katalog profili, beyan edilen istasyonlar)"),
                ("movable", "Hareketli dış parça", MOVABLE, "Hareketli dış parça (katalog profili, beyan edilen istasyonlar)"),
                ("joint", "Eklem bölgesi", JOINT, "Eklem bölgesi: aerodinamik yüzey, dış parçayla döner; eklem geometrisi "
                                                  "tanımlı değil (pivot çevresinde dairesel ayrım, gösterim)")):
            v, f, _ = _stack(blocks[key])
            t = _mesh_trace(v, f, name, color=color, hover=hover)
            if t is not None:
                fig.add_trace(t)
    v, f, _ = _stack(blocks["placeholder"])
    t = _mesh_trace(v, f, "Yüzey verisi yok (yer tutucu)", color=PLACEHOLDER, opacity=0.25,
                    hover="Yüzey verisi yok: en yakın beyan edilen kesitten uzatılmış yer tutucu, tasarım geometrisi değil")
    if t is not None:
        fig.add_trace(t)
    _hub_and_hinges(fig, mesh, tf, view)
    if selected_radius_m is not None:
        _selected_ring(fig, mesh, selected_radius_m, tf[0], view)
    if contacts is not None:
        _contact_marks(fig, contacts, view, contact_angle_deg)
    for t in extra_traces:
        fig.add_trace(t)
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=-0.02),
                      scene=dict(aspectmode="data", xaxis_title="X [mm]", yaxis_title="Y [mm]", zaxis_title="Z [mm]",
                                 camera=dict(eye=dict(x=0.9, y=-1.3, z=0.9))),
                      uirevision=uirevision)
    if scene_ranges is not None:
        span = scene_ranges[0][1] - scene_ranges[0][0]
        fig.update_layout(scene=dict(aspectmode="manual",
                                     **{a + "axis": dict(range=list(r)) for a, r in zip("xyz", scene_ranges)},
                                     aspectratio={a: (r[1] - r[0]) / span for a, r in zip("xyz", scene_ranges)}))
    return fig


def _rot(p, az):
    c, s = math.cos(az), math.sin(az)
    return np.column_stack([p[:, 0] * c - p[:, 1] * s, p[:, 0] * s + p[:, 1] * c, p[:, 2]])


def _strip_markers(fig, mesh, fields, tf, view):
    spec = mesh.spec
    xs, text, rr = [], [], []
    for b, f in enumerate(fields):
        mids = np.array([0.5 * (s[0] + s[1]) for s in f.strips])
        p = np.column_stack([np.zeros(len(mids)), mids, np.zeros(len(mids))])
        moving = (mids > spec.hinge_radius_m) | (bs.in_joint_zone(p[:, 0], p[:, 1], spec, mesh.joint_radius_m)
                                                  if mesh.joint == "relief" else False)
        moving = np.broadcast_to(np.asarray(moving, bool), (len(mids),))
        xs.append(view(tf[b](p, moving)) * 1000.0)
        text += [f"kanat {b + 1} · {f.label}: {s[2]:.4g}" for s in f.strips]
        rr += list(mids * 1000.0)
    w = np.vstack(xs)
    unit = fields[0].unit
    fig.add_trace(go.Scatter3d(x=w[:, 0], y=w[:, 1], z=w[:, 2], mode="markers", name="Şerit değerleri",
                               marker=dict(size=2.5, color="#222"), text=text, customdata=rr,
                               hovertemplate="%{text} " + unit + "<br>r = %{customdata:.1f} mm (şerit merkezi, çeyrek kiriş)"
                                             "<extra></extra>"))


def _hub_and_hinges(fig, mesh, tf, view):
    spec = mesh.spec
    zext = 0.6 * max(s[1] for s in spec.stations) * 1000.0
    th = np.linspace(0.0, 2.0 * math.pi, 97)
    rh = spec.hub_radius_m * 1000.0
    x, y, z = [], [], []
    for zz in (-zext, zext):                           # two rings and eight generators: only the radius is declared
        x += list(rh * np.cos(th)) + [None]; y += list(rh * np.sin(th)) + [None]; z += [zz] * 97 + [None]
    for a in np.linspace(0.0, 2.0 * math.pi, 9)[:-1]:
        x += [rh * math.cos(a)] * 2 + [None]; y += [rh * math.sin(a)] * 2 + [None]; z += [-zext, zext, None]
    fig.add_trace(go.Scatter3d(x=x, y=y, z=z, mode="lines", name="Göbek (şematik)",
                               line=dict(color="#8A99A8", width=2, dash="dot"),
                               hovertemplate=f"Göbek: yalnız yarıçap tanımlı (r = {rh:.0f} mm); eksenel boy ve şekil tanımsız"
                                             "<extra></extra>"))
    hx, hy, hz = [], [], []
    for b in range(spec.blade_count):
        p = view(tf[b](np.array([[0.0, spec.hinge_radius_m, 0.0]]), np.array([False])))[0] * 1000.0
        hx += [p[0], p[0], None]; hy += [p[1], p[1], None]; hz += [-zext, zext, None]
    fig.add_trace(go.Scatter3d(x=hx, y=hy, z=hz, mode="lines", name="Menteşe ekseni",
                               line=dict(color="#333", width=4, dash="dash"),
                               hovertemplate="Menteşe ekseni: çeyrek kirişte, şafta paralel (r_h = "
                                             f"{spec.hinge_radius_m * 1000:.0f} mm); eklem geometrisi tanımlı değil<extra></extra>"))


def _selected_ring(fig, mesh, r, tf0, view):
    spec = mesh.spec
    prof = bs.resample_profile(spec.profile, 48)
    ring = bs._ring(prof, *bs.section_at(spec, r), r)
    moving = np.full(len(ring), r > spec.hinge_radius_m)
    w = view(tf0(ring, moving)) * 1000.0
    w = np.vstack([w, w[:1]])
    fig.add_trace(go.Scatter3d(x=w[:, 0], y=w[:, 1], z=w[:, 2], mode="lines", name=f"Seçilen kesit r = {r * 1000:.1f} mm",
                               line=dict(color="#000", width=6), hoverinfo="name"))


def _contact_marks(fig, rep, view, at_deg=None):
    """Contact points; with ``at_deg`` only those whose first contact is the shown pose (others would float)."""
    pts, text = [], []
    for c in rep.contacts:
        if c.point_a is None or (at_deg is not None and abs(c.first_contact_deg - at_deg) > 0.05):
            continue
        kind = "temas" if c.status == "contact" else "olası temas (yüzey verisi yok)"
        pts.append(c.point_a)
        text.append(f"{c.a} ↔ {c.b}: {kind}, ilk temas {c.first_contact_deg:.1f}°")
    if not pts:
        return
    w = view(np.asarray(pts)) * 1000.0
    fig.add_trace(go.Scatter3d(x=w[:, 0], y=w[:, 1], z=w[:, 2], mode="markers", name="Temas noktası",
                               marker=dict(size=7, color="#D62728", symbol="x"), hovertext=text, hoverinfo="text"))


def radial_link_figure(field, *, selected_radius_m=None, crange=None, hinge_radius_m=None, colorscale="Viridis",
                       height: int = 300):
    xs, ys, mx, my = [], [], [], []
    for a, b, v in field.strips:
        xs += [a * 1000.0, b * 1000.0, None]; ys += [v, v, None]
        mx.append(500.0 * (a + b)); my.append(v)
    lo, hi = crange if crange is not None else (min(my), max(my))
    fig = go.Figure([go.Scatter(x=xs, y=ys, mode="lines", name="Şerit değeri", line=dict(color="#555", width=2),
                                hoverinfo="skip"),
                     go.Scatter(x=mx, y=my, mode="markers", name="Şerit merkezi",
                                marker=dict(size=8, color=my, colorscale=colorscale, cmin=lo, cmax=hi,
                                            line=dict(color="#333", width=0.5)),
                                hovertemplate="r = %{x:.1f} mm<br>%{y:.4g} " + field.unit + "<extra></extra>")])
    shapes = []
    if hinge_radius_m is not None:
        shapes.append(dict(type="line", x0=hinge_radius_m * 1000, x1=hinge_radius_m * 1000, y0=0, y1=1, yref="paper",
                           line=dict(color="#888", dash="dash")))
    if selected_radius_m is not None:
        shapes.append(dict(type="line", x0=selected_radius_m * 1000, x1=selected_radius_m * 1000, y0=0, y1=1,
                           yref="paper", line=dict(color="#000", width=2)))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), shapes=shapes, showlegend=False,
                      xaxis_title="r [mm] (kesikli: menteşe)", yaxis_title=f"{field.label} [{field.unit}]")
    return fig


def _all_blades(mesh, fold_deg, rotor_azimuth_rad=0.0):
    B = mesh.spec.blade_count
    folds = _per_blade(fold_deg, B)
    return [_posed(mesh, folds[b], rotor_azimuth_rad + 2 * math.pi * b / B) for b in range(B)]


def stl_bytes(mesh, *, fold_deg=0.0, rotor_azimuth_rad: float = 0.0) -> bytes:
    """Analysed blade surfaces (aero and joint regions) of every blade, ASCII STL in millimetres."""
    out = io.StringIO()
    out.write(f"solid pyfoldable_{mesh.spec.profile_id}_reconstructed_mm\n")
    sel = mesh.faces[np.isin(mesh.region, ("aero", "joint"))]
    for v in _all_blades(mesh, fold_deg, rotor_azimuth_rad):
        tri = v[sel]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
        for t, nn in zip(tri, n):
            out.write(f"facet normal {nn[0]:.6e} {nn[1]:.6e} {nn[2]:.6e}\n outer loop\n")
            for p in t:
                out.write(f"  vertex {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
            out.write(" endloop\nendfacet\n")
    out.write(f"endsolid pyfoldable_{mesh.spec.profile_id}_reconstructed_mm\n")
    return out.getvalue().encode()


def vtk_bytes(mesh, *, fold_deg=0.0, field=None, rotor_azimuth_rad: float = 0.0) -> bytes:
    """Legacy VTK polydata (mm) with region, part and blade ids and the selected field per cell (NaN: no data)."""
    from pyfoldable.visualization import blade_results as br
    B = mesh.spec.blade_count
    fields = _per_blade(field, B)
    blades = _all_blades(mesh, fold_deg, rotor_azimuth_rad)
    n_v, n_f = len(mesh.vertices), len(mesh.faces)
    out = io.StringIO()
    out.write("# vtk DataFile Version 3.0\nPyFoldable reconstructed blade (catalog profile, declared stations; mm)\n"
              f"ASCII\nDATASET POLYDATA\nPOINTS {n_v * B} float\n")
    for v in blades:
        for p in v:
            out.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
    out.write(f"POLYGONS {n_f * B} {4 * n_f * B}\n")
    for b in range(B):
        for f in mesh.faces + b * n_v:
            out.write(f"3 {f[0]} {f[1]} {f[2]}\n")
    out.write(f"CELL_DATA {n_f * B}\nSCALARS region_id int 1\nLOOKUP_TABLE default\n")
    out.write("".join(f"{REGION_ID[r]}\n" for _ in range(B) for r in mesh.region))
    out.write("SCALARS part_id int 1\nLOOKUP_TABLE default\n")
    out.write("".join(f"{0 if p == 'proximal' else 1}\n" for _ in range(B) for p in mesh.face_part))
    out.write("SCALARS blade_id int 1\nLOOKUP_TABLE default\n")
    out.write("".join(f"{b}\n" for b in range(B) for _ in range(n_f)))
    if fields[0] is not None:
        out.write(f"SCALARS {fields[0].key} float 1\nLOOKUP_TABLE default\n")
        for f in fields:
            vals = br.face_values(mesh, f)
            out.write("".join(("nan" if not np.isfinite(x) else f"{x:.6e}") + "\n" for x in vals))
    return out.getvalue().encode()
