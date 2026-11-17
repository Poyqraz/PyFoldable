"""Figures no other view draws: stored polar families, retained convergence screenings, the no-induction data
envelope, the BEM mechanism history, BEM and coupled record overlays, one archived study chart and the legacy
example pipelines (matplotlib PNGs written in a temporary folder). Builders only read their inputs."""
from __future__ import annotations

import json
import math
import sys
import tempfile
import types
from dataclasses import replace
from pathlib import Path

import plotly.graph_objects as go
from plotly.colors import sample_colorscale
from plotly.subplots import make_subplots

from . import figure_style as fs

_OK, _FAIL = "#14B8A6", "#CB4B66"


def _colors(n):
    return sample_colorscale("Turbo", [0.1 + 0.85 * i / max(1, n - 1) for i in range(n)])


def _legend_rows(n, per_row=2):
    return 22 * math.ceil(n / per_row)


def polar_family_figure(family):
    """c_l, c_d and c_l/c_d against α, one line per stored Re/Mach cell; only the table points, nothing extended."""
    tables = family.tables
    colors = _colors(len(tables))
    fig = make_subplots(rows=1, cols=3, horizontal_spacing=.09)
    for t, color in zip(tables, colors):
        alpha = [math.degrees(a) for a in t.alpha_rad]
        name = f"Re {t.reynolds / 1000:.0f}k · Mach {t.mach:.2f}"
        for col, y in enumerate((list(t.cl), list(t.cd), [cl / cd for cl, cd in zip(t.cl, t.cd)]), start=1):
            fig.add_trace(go.Scatter(x=alpha, y=y, mode="lines+markers", name=name, legendgroup=name, showlegend=col == 1,
                                     line=dict(color=color, width=1.6), marker=dict(size=4)), row=1, col=col)
    fig.update_xaxes(title="α [°]")
    for col, title in enumerate(("c_l [-]", "c_d [-]", "c_l / c_d [-]"), start=1):
        fig.update_yaxes(title=title, row=1, col=col)
    fig.update_layout(height=330 + _legend_rows(len(tables)), margin=dict(l=55, r=20, t=24, b=45))
    return fig


def convergence_heatmap(rows):
    """Re × Mach cells of a retained XFOIL convergence screening (1 converged, 0 not; failed α on hover), one panel
    per profile or per angle-step / iteration setting."""
    groups = {}
    for r in rows:
        groups.setdefault(r.get("profile") or f"α adımı {r['seq']} · {r['iter']} iterasyon", []).append(r)
    fig = make_subplots(rows=len(groups), cols=1, subplot_titles=tuple(groups), vertical_spacing=min(.12, .45 / len(groups)))
    for n, cells in enumerate(groups.values(), start=1):
        res, machs = sorted({c["re"] for c in cells}), sorted({c["mach"] for c in cells})
        at = {(c["mach"], c["re"]): c for c in cells}
        if len(at) != len(cells):
            raise ValueError("Yakınsama dosyasında aynı Re/Mach hücresi birden çok kez var.")

        def text(c):
            if c is None:
                return "taranmadı"
            return "yakınsadı" if c["complete"] else "yakınsamadı · α " + ", ".join(f"{a:g}°" for a in c["failed_alpha"])
        fig.add_trace(go.Heatmap(
            x=[f"{re / 1000:.0f}k" for re in res], y=[f"{m:.2f}" for m in machs],
            z=[[None if (m, re) not in at else int(bool(at[m, re]["complete"])) for re in res] for m in machs],
            text=[[text(at.get((m, re))) for re in res] for m in machs], zmin=0, zmax=1, showscale=False,
            colorscale=((0, _FAIL), (1, _OK)), xgap=2, ygap=2,
            hovertemplate="Re %{x} · Mach %{y}<br>%{text}<extra></extra>"), row=n, col=1)
        fig.update_xaxes(title="Reynolds [-]", type="category", row=n, col=1)
        fig.update_yaxes(title="Mach [-]", type="category", row=n, col=1)
    fig.update_layout(height=60 + 240 * len(groups), margin=dict(l=55, r=20, t=30, b=45))
    return fig


def envelope_map(active, family, rpms, inflows):
    """Whether the no-induction start queries (α, Re, Mach at the station midpoints) fall inside the stored version's
    declared grid at each RPM × inflow point. Induction lowers α at inner stations: a covered point can still leave
    the data in BEM, an uncovered one is refused before solving."""
    from . import research_design as research
    c, rest = active.design.operating_conditions[0], active.design.operating_conditions[1:]

    def covered(rpm, inflow):
        condition = replace(c, angular_speed_rad_s=rpm * math.pi / 30, forward_speed_m_s=float(inflow))
        point = replace(active, design=replace(active.design, operating_conditions=(condition, *rest)))
        return int(research.declared_grid_covers_initial(family, research.initial_query_ranges(point)))
    z = [[covered(rpm, v) for v in inflows] for rpm in rpms]
    fig = go.Figure(go.Heatmap(
        x=list(inflows), y=list(rpms), z=z, zmin=0, zmax=1, showscale=False, colorscale=((0, _FAIL), (1, _OK)),
        xgap=1, ygap=1, text=[["veri ızgarası içinde" if v else "veri ızgarası dışında" for v in line] for line in z],
        hovertemplate="%{y:.0f} RPM · %{x:.1f} m/s<br>%{text}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[active.inputs.inflow_m_s], y=[active.inputs.rpm], mode="markers", name="Güncel tasarım",
                             marker=dict(symbol="x", size=12, color=fs.ACCENT)))
    fig.update_xaxes(title="Giriş hızı [m/s]")
    fig.update_yaxes(title="Devir [RPM]")
    static = 0 in inflows and not any(line[list(inflows).index(0)] for line in z)
    fig.update_layout(title=dict(text="Veri kapsamı · yalnız indüksiyonsuz başlangıç sorgusu"
                                 + (" · statik (0 m/s) itki bu sürümle hesaplanamaz" if static else ""), font=dict(size=13)),
                      height=420, margin=dict(l=55, r=20, t=40, b=45))
    return fig


def bem_mechanism_figure(row):
    """Opening angle and the torque terms of the single rigid distal part (prescribed RPM ramp, no aero feedback)."""
    samples = json.loads(row["mechanism"]["report_text"])["result"]["samples"]
    t = [s["time_s"] for s in samples]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.08)
    fig.add_trace(go.Scatter(x=t, y=[math.degrees(s["angle_rad"]) for s in samples], name="Katlanma açısı",
                             line=dict(color=fs.SERIES[0])), row=1, col=1)
    for color, (key, label) in zip(fs.SERIES[1:], (("centrifugal_torque_nm", "Merkezkaç momenti"),
                                                   ("euler_torque_nm", "Euler momenti"),
                                                   ("dry_friction_torque_nm", "Kuru sürtünme"))):
        fig.add_trace(go.Scatter(x=t, y=[s[key] for s in samples], name=label, line=dict(color=color)), row=2, col=1)
    fig.update_yaxes(title="Açı [°]", row=1, col=1)
    fig.update_yaxes(title="Moment [N·m]", row=2, col=1)
    fig.update_xaxes(title="Zaman [s]", row=2, col=1)
    fig.update_layout(height=470, margin=dict(l=55, r=20, t=24, b=45))
    return fig


_RADIAL = (("alpha_deg", "α [°]"), ("dthrust_n_per_m", "dT/dr [N/m]"), ("dtorque_nm_per_m", "dQ/dr [N·m/m]"))
_TOTALS = (("thrust_n", "İtki [N]"), ("torque_nm", "Şaft torku [N·m]"), ("shaft_power_w", "Şaft gücü [W]"))


def bem_name(row):
    i = row["inputs"]
    return f"{i['profile']} · {i['rpm']:.0f} RPM · {i['inflow_m_s']:g} m/s · {row['result_sha256'][:8]}"


def bem_overlay_figure(rows):
    """Radial α, dT/dr and dQ/dr of one or two successful BEM records against radius, and their totals as bars."""
    from . import research_design as research
    fig = make_subplots(rows=2, cols=3, vertical_spacing=.2, horizontal_spacing=.1)
    for n, row in enumerate(rows):
        name, radial = bem_name(row), research.radial_rows(row)
        if not radial:
            raise ValueError(f"{name}: tamamlanmış BEM çözümü yok; radyal dağılım çizilemez.")
        color = fs.SERIES[n]
        for col, (key, _) in enumerate(_RADIAL, start=1):
            fig.add_trace(go.Scatter(x=[1000 * r["radius_m"] for r in radial], y=[r[key] for r in radial], name=name,
                                     legendgroup=name, showlegend=col == 1, mode="lines+markers", line=dict(color=color),
                                     marker=dict(size=4, symbol=("circle", "diamond")[n % 2])), row=1, col=col)
        for col, (key, _) in enumerate(_TOTALS, start=1):
            fig.add_trace(go.Bar(x=[row["result_sha256"][:8]], y=[row["aerodynamics"][key]], name=name, legendgroup=name,
                                 showlegend=False, marker_color=color), row=2, col=col)
    for col, (_, label) in enumerate(_RADIAL, start=1):
        fig.update_xaxes(title="Yarıçap [mm]", row=1, col=col)
        fig.update_yaxes(title=label, row=1, col=col)
    for col, (_, label) in enumerate(_TOTALS, start=1):
        fig.update_yaxes(title=label, row=2, col=col)
    fig.update_layout(height=560, margin=dict(l=55, r=20, t=24, b=45), barmode="group")
    return fig


_ALIGNED = (("theta_deg", "θ, kanat 1 [°]"), ("thrust_n", "İtki [N]"),
            ("hinge_law_torque_nm", "Menteşe momenti (yay+sönüm+stop), kanat 1 [N·m]"))


def coupled_overlay_figure(rows, event):
    """θ, thrust and hinge-law moment of coupled records on one time axis, zero at each record's own ``event``
    (pyfoldable.coupled.flow.events); only the valid prefix is drawn."""
    from pyfoldable.coupled import flow
    from .coupled_views import EVENT_LABELS
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=.06)
    for n, row in enumerate(rows):
        i = row["request"]["research"]["inputs"]
        name = f"{row['result_sha256'][:8]} · {i['profile']} · {i['rpm']:.0f} RPM"
        ev = flow.events(row)
        if event not in ev:
            raise ValueError(f"{name}: geçerli önekte “{EVENT_LABELS[event]}” olayı yok; bu olaya hizalanamaz.")
        valid = row["series"][:row["execution"]["valid_prefix_windows"]]
        t0 = next(r["time_s"] for r in valid if r["window"] == ev[event])
        t = [r["time_s"] - t0 for r in valid]
        for k, (key, _) in enumerate(_ALIGNED, start=1):
            y = [r[key][0] if isinstance(r[key], list) else r[key] for r in valid]
            fig.add_trace(go.Scatter(x=t, y=y, name=name, legendgroup=name, showlegend=k == 1, mode="lines",
                                     line=dict(color=fs.SERIES[n], dash=("solid", "dash")[n % 2])), row=k, col=1)
    for k, (_, label) in enumerate(_ALIGNED, start=1):
        fig.update_yaxes(title=label, row=k, col=1)
    fig.update_xaxes(title=f"{EVENT_LABELS[event]} anına göre zaman [s]", row=3, col=1)
    fig.add_vline(x=0, line=dict(color=fs.CONSTRUCTION, dash="dot"))
    fig.update_layout(height=640, margin=dict(l=55, r=20, t=24, b=45), hovermode="x unified")
    return fig


def archived_json_figure(path):
    """Chart of an archived study whose schema is known (PR06D opening sensitivity); None: show it as a table."""
    if Path(path).name != "pr06d_opening_sensitivity.json":
        return None
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["angle_summaries"]
    x = [r["angle_from_deployed_deg"] for r in rows]
    fig = go.Figure()
    for color, (regime, key, label) in zip(fs.SERIES, (("static", "thrust_ratio_median", "Statik T/T₀"),
                                                       ("static", "torque_ratio_median", "Statik Q/Q₀"),
                                                       ("forward", "thrust_ratio_median", "İleri T/T₀"),
                                                       ("forward", "torque_ratio_median", "İleri Q/Q₀"))):
        fig.add_trace(go.Scatter(x=x, y=[r["regimes"][regime][key] for r in rows], mode="lines+markers",
                                 name=label + " (medyan)", line=dict(color=color)))
    fig.update_xaxes(title="Açılmış konumdan açı [°]")
    fig.update_yaxes(title="Açık konuma oran [-]")
    fig.update_layout(height=380, margin=dict(l=55, r=20, t=24, b=45))
    return fig


# Legacy example chains (pyfoldable.models V01/V02 + the synthetic APC fixture), each in its run order.
LEGACY = {
    "sweep": ("run_design_variant_sweep", "run_design_variant_summary", "run_design_variant_decision_matrix",
              "run_foldable_report_plots"),
    "visuals": ("run_design_variant_sweep", "run_moment_kinematics_validation", "run_foldable_visuals"),
    "spinup": ("run_dynamic_spinup",),
    "physics": ("run_prescribed_rpm_physics",),
}


def legacy_pngs(name, root):
    """Run one legacy example chain with its project root moved to a temporary folder and return the PNGs it wrote
    as (name, bytes); frame sequences are left out. The examples derive PROJECT_ROOT from ``__file__`` and only read
    configs/ and data/, which are linked read-only, so nothing is written inside the repository."""
    import matplotlib
    matplotlib.use("Agg")
    root = Path(root).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp).resolve()
        for part in ("configs", "data"):
            # shortcut: symlinks need POSIX (or Windows developer mode); copy the inputs if Windows hosts run this
            (base / part).symlink_to(root / part, target_is_directory=True)
        for script in LEGACY[name]:
            source = root / "examples" / f"{script}.py"
            module = types.ModuleType(f"_pyfoldable_legacy_{script}")
            module.__file__ = str(base / "examples" / source.name)
            saved_path = list(sys.path)
            sys.modules[module.__name__] = module  # dataclasses defined by an example look their module up
            try:
                exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), module.__dict__)
                module.main()
            except SystemExit as exc:  # the examples exit on missing inputs; callers catch ordinary errors
                raise RuntimeError(f"{script}: {exc}") from exc
            finally:
                sys.path[:] = saved_path
                sys.modules.pop(module.__name__, None)
        out = base / "outputs"
        return [(str(p.relative_to(out)), p.read_bytes()) for p in sorted(out.rglob("*.png"))
                if "frames" not in p.relative_to(out).parts]
