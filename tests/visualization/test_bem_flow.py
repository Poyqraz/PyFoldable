"""Momentum-theory flow reconstruction from a retained BEM solution (labelled model, not a wake solution)."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from pyfoldable.visualization import bem_flow

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application"))
from test_figure_style import _contrast  # noqa: E402


def _row(a=(2.0, 3.0, 4.0), vt=(1.0, 0.8, 0.6), V=14.0):
    els = []
    edges = (0.144, 0.22, 0.30, 0.388)
    for i, (ai, vi) in enumerate(zip(a, vt)):
        r0, r1 = edges[i], edges[i + 1]
        els.append({"inner_radius_m": r0, "outer_radius_m": r1,
                    "solution": {"radius_m": 0.5 * (r0 + r1), "axial_induced_velocity_m_s": ai,
                                 "tangential_induced_velocity_m_s": vi}})
    return {"inputs": {"inflow_m_s": V, "diameter_mm": 800.0},
            "aerodynamics": {"status": "success", "radial_elements": els, "outer_radius_m": 0.388}}


def test_induction_grows_from_zero_upstream_to_twice_the_disk_value_downstream():
    s = bem_flow.slipstream(_row(), downstream_radii=6.0, upstream_radii=6.0, n_axial=241)
    z = s["z_m"]
    up, disk, far = np.argmax(z), np.argmin(np.abs(z)), np.argmin(z)      # free stream from +z (thrust +z)
    assert s["axial_m_s"][1][up] == pytest.approx(14.0 + 0.0, abs=0.2)
    assert s["axial_m_s"][1][disk] == pytest.approx(14.0 + 3.0, abs=1e-6)
    assert s["axial_m_s"][1][far] == pytest.approx(14.0 + 2 * 3.0, abs=0.15)


def test_stream_tubes_contract_with_continuity_and_swirl_follows_angular_momentum():
    s = bem_flow.slipstream(_row(), downstream_radii=6.0, n_axial=241)
    far = np.argmax(-s["z_m"])
    for k in range(len(s["tube_r_m"])):
        r_d, r_f = s["tube_r_m"][k][np.argmin(np.abs(s["z_m"]))], s["tube_r_m"][k][far]
        u_d, u_f = s["axial_m_s"][k][np.argmin(np.abs(s["z_m"]))], s["axial_m_s"][k][far]
        assert r_f < r_d and r_f ** 2 * u_f == pytest.approx(r_d ** 2 * u_d, rel=1e-9)
        # far-wake swirl: twice the disk value at the disk radius, carried to the contracted radius (r v_t const)
        assert s["swirl_m_s"][k][far] * r_f == pytest.approx(2 * s["swirl_disk_m_s"][k] * r_d, rel=0.03)


def test_figure_is_labelled_as_a_momentum_reconstruction():
    fig = bem_flow.slipstream_figure(_row())
    text = " ".join(str(a.text) for a in fig.layout.annotations) + str(fig.layout.title.text)
    assert "momentum" in text.lower() and "rekonstrüksiyon" in text.lower() and "CFD değildir" in text


def test_colour_bar_sits_outside_both_panels_with_a_dark_safe_scale():
    fig = bem_flow.slipstream_figure(_row())
    tube = next(t for t in fig.data if t.marker.showscale)
    assert tube.marker.colorbar.x > 1.0
    assert all(_contrast(c.replace(" ", "")) >= 3.0 for _, c in tube.marker.colorscale)
