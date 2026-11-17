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


def _mesh(active, foil):
    d = active.design
    return build_propeller_preview_mesh(
        PropellerPreviewSpec(d.blade.diameter_m, d.blade.hub_radius_m, d.blade.blade_count,
                             d.hinge.radius_m, active.inputs.fold_deg, foil.id, airfoil_definition=foil),
        tuple(PreviewBladeStation(s.r_over_R, s.chord_m, math.degrees(s.twist_rad)) for s in d.blade.stations),
    )


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
