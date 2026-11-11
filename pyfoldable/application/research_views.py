"""Figures for the research workspace; all coordinates come from the active draft."""
from __future__ import annotations

import math

import plotly.graph_objects as go

from pyfoldable.visualization.propeller_25d import (
    PreviewBladeStation, PropellerPreviewSpec, build_propeller_preview_mesh,
)

_FIXED = "#008579"
_MOVABLE = "#DC671D"
_PROFILES = "#177D99"
_MARKS = (
    ("Mil", "cross", "#6D7E90"),
    ("Kök", "circle", "#177D99"),
    ("Menteşe", "diamond", "#A44AC2"),
    ("Uç", "square", "#CB4B66"),
)
CAMERAS = {
    "İzometrik": dict(eye=dict(x=.94, y=-1.15, z=.86), up=dict(x=0, y=0, z=1)),
    "Üst": dict(eye=dict(x=0, y=0, z=1.50), up=dict(x=0, y=1, z=0)),
    "Yan": dict(eye=dict(x=0, y=-1.50, z=0), up=dict(x=0, y=0, z=1)),
}


def _layout(fig, *, height, legend=True):
    fig.update_layout(height=height, autosize=True, showlegend=legend,
                      margin=dict(l=55, r=22, t=18, b=78 if legend else 53),
                      legend=dict(orientation="h", x=0, y=-.17, xanchor="left", yanchor="top"),
                      hovermode="closest")
    return fig


def airfoil_figure(foil):
    x, z = zip(*foil.coordinates)
    fig = go.Figure(go.Scatter(x=[100*a for a in x], y=[100*b for b in z], mode="lines",
                              line=dict(color=_PROFILES, width=2.5), name=foil.id,
                              hovertemplate="x/kord: %{x:.2f}%<br>z/kord: %{y:.2f}%<extra></extra>"))
    fig.update_xaxes(title="x / kord [%]", range=[-5, 105], constrain="domain", automargin=True)
    fig.update_yaxes(title="z / kord [%]", scaleanchor="x", scaleratio=1, range=[-19, 19], automargin=True)
    return _layout(fig, height=295, legend=False)


def _blade_point(azimuth, radial, hinge, angle=0.):
    if radial > hinge:
        x, y = hinge + (radial - hinge) * math.cos(angle), (radial - hinge) * math.sin(angle)
    else:
        x, y = radial, 0.
    c, s = math.cos(azimuth), math.sin(azimuth)
    return (1000*(c*x-s*y), 1000*(s*x+c*y), 0.)


def _datums(active):
    d = active.design
    b = d.blade
    h, r, hub = d.hinge.radius_m, b.radius_m, b.hub_radius_m
    angle = math.radians(active.inputs.fold_deg)
    root = None if active.root is None else active.root.value / 1000
    start, end = (b.stations[k].r_over_R * r for k in (0, -1))
    marks = {"Mil": [(0., 0., 0.)], "Kök": [], "Menteşe": [], "Uç": []}
    missing = []
    for index in range(b.blade_count):
        azimuth = index * math.tau / b.blade_count
        for key, value in (("Kök", root), ("Menteşe", h), ("Uç", r)):
            if value is not None:
                marks[key].append(_blade_point(azimuth, value, h, angle))
        # Construction lines only. No missing section surface is interpolated.
        lo = hub if root is None else root
        for a, z in ((lo, min(start, h)), (max(end, h), r)):
            if a < z:
                missing.extend((_blade_point(azimuth, a, h, angle), _blade_point(azimuth, z, h, angle), (None,)*3))
    ring = [(1000*hub*math.cos(k*math.tau/96), 1000*hub*math.sin(k*math.tau/96), 0.)
            for k in range(97)]
    return marks, ring, missing


def _add_datums(fig, active, *, is_3d):
    marks, ring, missing = _datums(active)
    trace = go.Scatter3d if is_3d else go.Scatter

    def points(coords):
        x, y, z = zip(*coords)
        return {"x": x, "y": y, **({"z": z} if is_3d else {})}

    fig.add_trace(trace(**points(ring), mode="lines", name="Göbek sınırı",
                        line=dict(color="#76889A", width=2), hoverinfo="name"))
    if missing:
        fig.add_trace(trace(**points(missing), mode="lines", name="Yüzey verisi yok",
                            line=dict(color="#76889A", width=2, dash="dot"), hoverinfo="name"))
    for label, symbol, color in _MARKS:
        if marks[label]:
            fig.add_trace(trace(**points(marks[label]), mode="markers", name=label,
                                marker=dict(color=color, symbol=symbol, size=5 if is_3d else 9),
                                hovertemplate=(label + ": %{x:.1f}, %{y:.1f} mm<extra></extra>")))
    return [p for p in ring] + [p for seq in marks.values() for p in seq]


def _mesh(active, foil):
    d = active.design
    return build_propeller_preview_mesh(
        PropellerPreviewSpec(d.blade.diameter_m, d.blade.hub_radius_m, d.blade.blade_count,
                             d.hinge.radius_m, active.inputs.fold_deg, foil.id, airfoil_definition=foil),
        tuple(PreviewBladeStation(s.r_over_R, s.chord_m, math.degrees(s.twist_rad)) for s in d.blade.stations),
    )


def _sections(mesh):
    return (("Sabit iç parça", _FIXED, 0, mesh.hinge_root_station_index + 1),
            ("Hareketli dış parça", _MOVABLE, mesh.hinge_tip_station_index, mesh.station_count))


def plan_figure(active, foil):
    mesh = _mesh(active, foil)
    fig = go.Figure()
    count = mesh.section_vertex_count
    for label, color, first, stop in _sections(mesh):
        outline = []
        for blade in range(mesh.blade_count):
            offset = blade * mesh.station_count * count
            theta = blade * math.tau / mesh.blade_count
            if first == mesh.hinge_tip_station_index:
                theta += math.radians(active.inputs.fold_deg)
            ax, ay = -math.sin(theta), math.cos(theta)
            ends = []
            for s in range(first, stop):
                ring = mesh.vertices[offset+s*count:offset+(s+1)*count]
                key = lambda p: ax*p[0]+ay*p[1]
                ends.append((min(ring, key=key), max(ring, key=key)))
            curve = [e[0] for e in ends] + [e[1] for e in reversed(ends)] + [ends[0][0]]
            outline.extend([(1000*x, 1000*y) for x, y, _ in curve] + [(None, None)])
        x, y = zip(*outline)
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=label,
                                 line=dict(color=color, width=3, dash="solid" if first == 0 else "dash"),
                                 hovertemplate="%{x:.1f}, %{y:.1f} mm<extra>" + label + "</extra>"))
    _add_datums(fig, active, is_3d=False)
    fig.update_xaxes(title="X [mm]", constrain="domain", automargin=True)
    fig.update_yaxes(title="Y [mm]", scaleanchor="x", scaleratio=1, automargin=True)
    return _layout(fig, height=405)


def surface_figure(active, foil, camera, revision):
    mesh = _mesh(active, foil)
    fig = go.Figure()
    xyz = [tuple(1000*value for value in p) for p in mesh.vertices]
    x, y, z = zip(*xyz)
    n = mesh.section_vertex_count
    open_te = math.dist(foil.coordinates[0], foil.coordinates[-1]) > 1e-12
    for label, color, first, stop in _sections(mesh):
        # Render only retained side faces. In particular, no cap or strip across
        # an open trailing edge is added to this view.
        faces = [f for f in mesh.faces if first <= (f[0]//n) % mesh.station_count < stop
                 and not (open_te and {0, n-1}.issubset({k % n for k in f}))]
        i, j, k = zip(*faces)
        fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, name=label, showlegend=True,
                               color=color, flatshading=True, hoverinfo="name",
                               lighting=dict(ambient=.82, diffuse=.58, specular=.12)))
    datums = _add_datums(fig, active, is_3d=True)
    ranges = []
    for dim in range(3):
        values = [p[dim] for p in xyz + datums]
        a, b = min(values), max(values)
        pad = max(.5, .08*(b-a))
        ranges.append([a-pad, b+pad])
    spans = [b-a for a, b in ranges]
    longest = max(spans)
    fig.update_layout(scene=dict(
        **{axis+"axis": dict(title=axis.upper()+" [mm]", range=bounds, nticks=2 if axis == "z" else 5)
           for axis, bounds in zip("xyz", ranges)},
        # Uniform viewport scale. All axes retain the same mm-to-scene ratio.
        aspectmode="manual", aspectratio={axis: 2.65*width/longest for axis, width in zip("xyz", spans)},
        camera={**CAMERAS[camera], "projection": {"type": "orthographic"}},
        uirevision=f"{active.identity}:{camera}:{revision}",
    ))
    return _layout(fig, height=455)


def radial_figure(rows, fields, unit):
    colors = (_FIXED, _MOVABLE)
    fig = go.Figure()
    for index, (field, label, digits) in enumerate(fields):
        fig.add_trace(go.Scatter(
            x=[1000*r["radius_m"] for r in rows], y=[r[field] for r in rows],
            mode="lines+markers", name=label, line=dict(color=colors[index % 2], width=2.5),
            marker=dict(size=5, symbol="circle" if index % 2 == 0 else "diamond"),
            hovertemplate=f"Yarıçap: %{{x:.1f}} mm<br>{label}: %{{y:.{digits}f}} {unit}<extra></extra>"))
    fig.update_xaxes(title="Eleman orta yarıçapı [mm]", automargin=True)
    fig.update_yaxes(title=unit, automargin=True)
    return _layout(fig, height=290, legend=len(fields) > 1)
