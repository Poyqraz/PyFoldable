import inspect

import plotly.graph_objects as go
import pytest
import streamlit as st

from pyfoldable.application import figure_style as fs

BACKGROUND = "#07111F"  # .streamlit/config.toml theme.backgroundColor


def _luminance(colour):
    if colour.startswith("rgb"):
        channels = [int(v) / 255 for v in colour[colour.index("(") + 1:-1].split(",")]
    else:
        channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(colour):
    lighter, darker = sorted((_luminance(colour), _luminance(BACKGROUND)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_contrast_helper_matches_audited_ratios():
    assert _contrast("#0b6170") == pytest.approx(2.67, abs=0.01)
    assert _contrast("#000000") == pytest.approx(1.11, abs=0.01)


@pytest.mark.parametrize("colour", [fs.ACCENT, fs.CONSTRUCTION, fs.TEXT, *fs.SERIES,
                                    *(stop for _, stop in fs.PARTICLE_SCALE)])
def test_every_token_meets_wcag_graphics_contrast_on_app_background(colour):
    assert _contrast(colour) >= 3.0


def test_series_replaces_dim_primary_teal():
    assert "#0b6170" not in (c.lower() for c in fs.SERIES)


def test_apply_shows_full_hover_names_and_keeps_transparent_background():
    fig = fs.apply(go.Figure())
    assert fig.layout.hoverlabel.namelength == -1
    assert fig.layout.paper_bgcolor is None and fig.layout.plot_bgcolor is None


def test_apply_puts_legend_below_and_grows_bottom_margin_with_entries():
    def figure(n):
        return go.Figure([go.Scatter(x=[0], y=[0], name=f"İz {i} [N]") for i in range(n)])

    few, many = fs.apply(figure(2)), fs.apply(figure(9))
    legend = many.layout.legend
    assert legend.orientation == "h" and legend.yanchor == "bottom" and legend.yref == "container"
    assert legend.entrywidth is not None
    assert many.layout.margin.b > few.layout.margin.b


def test_apply_leaves_margin_alone_without_legend_entries():
    fig = fs.apply(go.Figure([go.Scatter(x=[0], y=[0], showlegend=False)]))
    assert fig.layout.margin.b is None


def test_apply_follows_plotly_single_trace_legend_rule():
    # Plotly draws no legend for one trace unless showlegend is set explicitly.
    assert fs.apply(go.Figure([go.Scatter(x=[0], y=[0], name="Tek iz")])).layout.margin.b is None
    assert fs.apply(go.Figure([go.Scatter(x=[0], y=[0], name="Tek iz", showlegend=True)])).layout.margin.b


@pytest.mark.parametrize("traces", [
    [go.Scatter3d(x=[0], y=[0], z=[0], name="Kuvvet"), go.Cone(x=[0], y=[0], z=[0], u=[1], v=[0], w=[0], name="Kuvvet")],
    [go.Surface(z=[[0, 1], [1, 0]], name="Kanat"), go.Scatter3d(x=[0], y=[0], z=[0], name="Seçili kesit")],
    [go.Mesh3d(x=[0, 1, 0], y=[0, 0, 1], z=[0, 0, 0], name="Kanatlar"), go.Heatmap(z=[[0]], name="Alan"),
     go.Scatter(x=[0], y=[0], name="Tek iz")],
    [go.Scatter(x=[0], y=[0], name="Gizli", visible=False), go.Scatter(x=[0], y=[0], name="Tek iz")],
])
def test_apply_counts_only_traces_plotly_puts_in_the_legend(traces):
    # Cone/Surface/Mesh3d/Heatmap default to showlegend=false and hidden traces are skipped, so one entry: no legend.
    assert fs.apply(go.Figure(traces)).layout.margin.b is None


def test_apply_lays_out_grouped_traces_flat_like_the_margin_assumes():
    fig = fs.apply(go.Figure([go.Scatter(x=[0], y=[0], name=f"İz {i}", legendgroup=f"g{i}") for i in range(6)]))
    assert fig.layout.legend.traceorder == "normal"


def test_apply_uses_fewer_columns_for_long_names():
    from pyfoldable.application.fold_cycle_views import CONTRIB_LABEL

    def margin_and_width(names):
        fig = fs.apply(go.Figure([go.Scatter(x=[0], y=[0], name=n) for n in names]))
        return fig.layout.margin.b, fig.layout.legend.entrywidth

    short_margin, short_width = margin_and_width(["A", "B", "C", "D", "E"])
    long_margin, long_width = margin_and_width(CONTRIB_LABEL.values())
    assert long_width > short_width and long_margin > short_margin


def test_particle_scale_meets_contrast_at_the_opacity_particle_traces_use():
    opacity = 0.6  # coupled_views particle markers; alpha-blend each stop onto the page
    bg = [int(BACKGROUND[i:i + 2], 16) for i in (1, 3, 5)]
    for _, stop in fs.PARTICLE_SCALE:
        rgb = [int(v) for v in stop[stop.index("(") + 1:-1].split(",")]
        blended = "rgb({},{},{})".format(*(round(opacity * c + (1 - opacity) * b) for c, b in zip(rgb, bg)))
        assert _contrast(blended) >= 3.0


@pytest.mark.parametrize("modern", [False, True])
def test_width_kwargs_follow_installed_plotly_chart_signature(monkeypatch, modern):
    def legacy(figure, use_container_width=False):
        pass

    def current(figure, width="stretch", use_container_width=None):
        pass

    real = inspect.signature
    monkeypatch.setattr(fs.inspect, "signature",
                        lambda f: real(current if modern else legacy) if f is st.plotly_chart else real(f))
    assert fs.width_kwargs() == ({"width": "stretch"} if modern else {"use_container_width": True})


@pytest.mark.parametrize("modern", [False, True])
def test_dataframe_width_kwargs_follow_installed_dataframe_signature(monkeypatch, modern):
    def legacy(data, width=None, use_container_width=False):  # 1.40: width is an int
        pass

    def current(data, width="stretch", use_container_width=None):
        pass

    real = inspect.signature
    monkeypatch.setattr(fs.inspect, "signature",
                        lambda f: real(current if modern else legacy) if f is st.dataframe else real(f))
    assert fs.dataframe_width_kwargs() == ({"width": "stretch"} if modern else {"use_container_width": True})


def test_width_kwargs_are_accepted_by_installed_streamlit():
    for element, kwargs in ((st.plotly_chart, fs.width_kwargs()), (st.dataframe, fs.dataframe_width_kwargs())):
        inspect.signature(element).bind_partial(None, **kwargs)
