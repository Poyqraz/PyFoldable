"""Model-based flow view from a retained BEM solution (momentum theory; not a wake solution, not CFD).

The BEM stores, per annulus, the axial and tangential induced velocity at the rotor disk. Along each
annulus' stream tube the classic actuator-disk relation u(s) = a (1 + s / sqrt(s^2 + R^2)) carries the
axial induction from 0 far upstream through a at the disk to 2a far downstream (s = downstream distance,
the free stream comes from +z because thrust is +z). The tube radius follows continuity,
r(s)^2 (V + u(s)) = r_d^2 (V + a), and the swirl follows the same growth with r v_t conserved along the
tube. Assumptions: axisymmetric, inviscid, no tip-vortex roll-up or wake expansion effects, independent
annuli; a labelled reconstruction for orientation, not a computed flow field.
"""
from __future__ import annotations


import numpy as np

LABEL = ("BEM tabanlı akış rekonstrüksiyonu (momentum teorisi, aktüatör disk yasası): girdap izi çözümü veya CFD değildir")


def slipstream(row, *, downstream_radii: float = 4.0, upstream_radii: float = 1.5, n_axial: int = 161) -> dict:
    a_row = row["aerodynamics"]
    V = float(row["inputs"]["inflow_m_s"])
    R = float(row["inputs"]["diameter_mm"]) / 2000.0
    z = np.linspace(upstream_radii * R, -downstream_radii * R, n_axial)     # +z upstream, -z downstream
    s = -z
    growth = 1.0 + s / np.sqrt(s * s + R * R)
    tubes, axial, swirl, a_disk, vt_disk, r_disk = [], [], [], [], [], []
    for el in a_row["radial_elements"]:
        sol = el["solution"]
        r_d, a, vt = sol["radius_m"], sol["axial_induced_velocity_m_s"], sol["tangential_induced_velocity_m_s"]
        u = a * growth
        r = r_d * np.sqrt(np.divide(V + a, V + u, out=np.ones_like(u), where=(V + u) > 0))  # V = a = 0: no tube
        tubes.append(r)
        axial.append(V + u)
        swirl.append(vt * growth * r_d / r)
        a_disk.append(a); vt_disk.append(vt); r_disk.append(r_d)
    return {"z_m": z, "tube_r_m": tubes, "axial_m_s": axial, "swirl_m_s": swirl, "radius_disk_m": r_disk,
            "axial_induced_disk_m_s": a_disk, "swirl_disk_m_s": vt_disk, "free_stream_m_s": V, "tip_radius_m": R}


def slipstream_figure(row, height: int = 430):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    s = slipstream(row)
    z = s["z_m"] * 1000.0
    far = int(np.argmax(-s["z_m"]))
    disk = int(np.argmin(np.abs(s["z_m"])))
    fig = make_subplots(rows=1, cols=2, column_widths=(0.55, 0.45), horizontal_spacing=0.12,
                        subplot_titles=("Akım tüpleri (meridyen kesiti)", "Diskte ve uzak izde hızlar"))
    vmin = min(float(np.min(u)) for u in s["axial_m_s"])
    vmax = max(float(np.max(u)) for u in s["axial_m_s"])
    for k, (r, u) in enumerate(zip(s["tube_r_m"], s["axial_m_s"])):
        fig.add_trace(go.Scatter(x=r * 1000.0, y=z, mode="markers", showlegend=False,
                                 marker=dict(size=3, color=u, colorscale="Blues", cmin=vmin, cmax=vmax,
                                             colorbar=dict(title="V + u [m/s]", x=0.47, len=0.9) if k == 0 else None,
                                             showscale=k == 0),
                                 hovertemplate="r %{x:.0f} mm · z %{y:.0f} mm · V+u %{marker.color:.2f} m/s<extra>akım tüpü</extra>"),
                      row=1, col=1)
    R = s["tip_radius_m"] * 1000.0
    fig.add_trace(go.Scatter(x=[0, R], y=[0, 0], mode="lines", line=dict(color="#C0392B", width=3), name="Rotor diski"),
                  row=1, col=1)
    r_d = np.array(s["radius_disk_m"]) * 1000.0
    for name, y, dash in (("Eksenel V+u, disk", [u[disk] for u in s["axial_m_s"]], "solid"),
                          ("Eksenel V+u, uzak iz", [u[far] for u in s["axial_m_s"]], "dash"),
                          ("Dönme (swirl), disk", [v[disk] for v in s["swirl_m_s"]], "solid"),
                          ("Dönme (swirl), uzak iz", [v[far] for v in s["swirl_m_s"]], "dash")):
        x = r_d if "disk" in name else [r[far] * 1000.0 for r in s["tube_r_m"]]
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name=name, line=dict(dash=dash)), row=1, col=2)
    fig.update_xaxes(title_text="r [mm]", row=1, col=1)
    fig.update_yaxes(title_text="z [mm] (akış −z yönüne)", row=1, col=1)
    fig.update_xaxes(title_text="r [mm] (uzak izde daralmış yarıçap)", row=1, col=2)
    fig.update_yaxes(title_text="Hız [m/s]", row=1, col=2)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=90, b=10),
                      title=dict(text=f"BEM tabanlı akış rekonstrüksiyonu (momentum teorisi)<br><sup>{LABEL}</sup>",
                                 font=dict(size=14), y=0.97, yanchor="top"),
                      legend=dict(orientation="h", y=-0.2))
    return fig
