"""Shared figure colours, layout and Streamlit width arguments for the dark app theme.

Every token is checked in tests for at least 3:1 WCAG contrast against the
app background #07111F (.streamlit/config.toml); figures keep a transparent
background so Streamlit's theme shows through.
"""
from __future__ import annotations

import inspect
import math

import streamlit as st

ACCENT = "#22D3EE"  # selections and time cursors
CONSTRUCTION = "#9AA7B4"  # hinge axes, markers, strip lines
TEXT = "#E5EEF8"
SERIES = ("#14B8A6", "#DC671D", "#A44AC2", "#2E7D32")  # first entry replaces the dim #0b6170
# Greys trimmed to 0.60-0.95 so the low stop keeps 3:1 even at the 0.6 marker opacity particle traces use.
PARTICLE_SCALE = ((0.0, "rgb(153,153,153)"), (1.0, "rgb(242,242,242)"))

_AXIS_MARGIN_PX = 50
_LEGEND_ROW_PX = 22
# Plotly.js trace types whose showlegend defaults to false (checked in the bundled plotly.min.js).
_NO_DEFAULT_LEGEND = {"surface", "mesh3d", "cone", "streamtube", "isosurface", "volume", "heatmap", "histogram2d",
                      "choropleth"}


def apply(fig):
    """Show full trace names on hover and place the legend below the plot."""
    fig.update_layout(hoverlabel_namelength=-1)
    if fig.layout.updatemenus or fig.layout.sliders:   # playbacks size margin.b for their own controls
        return fig
    entries = [t for t in fig.data if t.visible is not False
               and (t.showlegend or (t.showlegend is None and t.type not in _NO_DEFAULT_LEGEND))]
    # Same rule as Plotly: one trace gets a legend only when asked for explicitly.
    shown = fig.layout.showlegend if fig.layout.showlegend is not None else (
        len(entries) > 1 or any(t.showlegend for t in entries))
    if entries and shown:
        longest = max(len(t.name or "trace 00") for t in entries)
        # shortcut: column count from name length, tuned for a ~400 px plot (half-width column); measure if it overflows.
        columns = 3 if longest <= 12 else 2 if longest <= 22 else 1
        fig.update_layout(
            # traceorder 'normal' keeps legendgroup traces in flat rows instead of Plotly's taller grouped layout.
            legend=dict(orientation="h", x=0, xanchor="left", yref="container", y=0, yanchor="bottom",
                        traceorder="normal", entrywidthmode="fraction", entrywidth=1 / columns),
            margin_b=_AXIS_MARGIN_PX + _LEGEND_ROW_PX * math.ceil(len(entries) / columns))
    return fig


def width_kwargs():
    """st.plotly_chart width: current API on new Streamlit, use_container_width on 1.40."""
    return {"width": "stretch"} if "width" in inspect.signature(st.plotly_chart).parameters else {"use_container_width": True}


def dataframe_width_kwargs():
    """st.dataframe width; 1.40 also has `width`, but only as pixels, so test for the string default."""
    width = inspect.signature(st.dataframe).parameters.get("width")
    return {"width": "stretch"} if width is not None and isinstance(width.default, str) else {"use_container_width": True}
