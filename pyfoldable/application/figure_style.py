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
# Greys trimmed to 0.40-0.95: the low end of plain Greys is black and vanishes on the page.
PARTICLE_SCALE = ((0.0, "rgb(102,102,102)"), (1.0, "rgb(242,242,242)"))

_LEGEND_COLUMNS = 3
_AXIS_MARGIN_PX = 50
_LEGEND_ROW_PX = 22


def apply(fig):
    """Show full trace names on hover and place the legend below the plot."""
    fig.update_layout(hoverlabel_namelength=-1)
    named = [trace for trace in fig.data if trace.showlegend is not False and trace.name]
    # Same rule as Plotly: one trace gets a legend only when asked for explicitly.
    shown = fig.layout.showlegend if fig.layout.showlegend is not None else (
        len(named) > 1 or any(trace.showlegend for trace in named))
    if named and shown:
        rows = math.ceil(len(named) / _LEGEND_COLUMNS)
        fig.update_layout(
            legend=dict(orientation="h", x=0, xanchor="left", yref="container", y=0, yanchor="bottom",
                        entrywidthmode="fraction", entrywidth=0.33),
            margin_b=_AXIS_MARGIN_PX + _LEGEND_ROW_PX * rows)
    return fig


def width_kwargs():
    """st.plotly_chart width: current API on new Streamlit, use_container_width on 1.40."""
    return {"width": "stretch"} if "width" in inspect.signature(st.plotly_chart).parameters else {"use_container_width": True}


def dataframe_width_kwargs():
    """st.dataframe width; 1.40 also has `width`, but only as pixels, so test for the string default."""
    width = inspect.signature(st.dataframe).parameters.get("width")
    return {"width": "stretch"} if width is not None and isinstance(width.default, str) else {"use_container_width": True}
