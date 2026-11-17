"""Flow companion of a sealed coupled record (no solver, no h5py).

The fixture holds a genuine sealed record and a flow companion extracted from that run's
retained DUST outputs (see its README); these tests exercise binding, fail-closed loading,
event detection, figures and the ParaView export.
"""
import importlib.util
import io
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import pytest

from pyfoldable.application import coupled_analysis as svc
from pyfoldable.application import coupled_views as views
from pyfoldable.coupled import flow

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "coupled" / "flow_30w_rbf"
RUN_ID = "20261112T074237_2a6ad5bd14"


@pytest.fixture()
def run(tmp_path):
    dst = tmp_path / "runs" / RUN_ID
    shutil.copytree(FIXTURE, dst)
    return dst


def _row(run):
    return svc.read_saved_coupled_result((run / "result.json").read_bytes())


def _manifest(run):
    return json.loads((run / "flow" / "flow_companion.json").read_text())


def _write_manifest(run, m):
    (run / "flow" / "flow_companion.json").write_text(json.dumps(m))


def test_companion_is_bound_to_the_sealed_record_and_its_raw_files(run):
    row = _row(run)
    fc = flow.load(run, row)
    m = fc.manifest
    assert m["result_sha256"] == row["result_sha256"]
    for src in m["sources"]:
        assert row["raw_outputs"]["files"][src["file"]]["sha256"] == src["sha256"]
    assert fc.windows.tolist() == [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 29, 30]
    p, v, rad = fc.particles(30)
    assert len(p) == len(v) == len(rad) > 0 and np.all(rad > 0)
    assert fc.plane_velocity.shape == (12, 21, 21, 3)
    # free stream is −14 m/s along z; the vortex model only adds induced velocity to it
    assert -30 < float(np.median(fc.plane_velocity[..., 2])) < -10


@pytest.mark.parametrize("tamper, code", [
    ("source", "source_mismatch"), ("record", "other_record"), ("npz_bytes", "checksum"),
    ("schema", "unsupported"), ("windows", "malformed"), ("missing", "missing"),
])
def test_tampered_or_foreign_companions_fail_closed(run, tamper, code):
    row = _row(run)
    m = _manifest(run)
    npz = run / "flow" / "flow_companion.npz"
    if tamper == "source":
        m["sources"][3]["sha256"] = "0" * 64
    elif tamper == "record":
        m["result_sha256"] = "f" * 64
    elif tamper == "npz_bytes":
        b = bytearray(npz.read_bytes()); b[len(b) // 2] ^= 0xFF; npz.write_bytes(bytes(b))
    elif tamper == "schema":
        m["schema_version"] = 99
    elif tamper == "windows":
        with np.load(npz) as z:
            arrays = {k: z[k] for k in z.files}
        arrays["windows"] = arrays["windows"] + 1  # frames relabelled to other windows
        np.savez_compressed(npz, **arrays)
        import hashlib
        m["npz"]["sha256"] = hashlib.sha256(npz.read_bytes()).hexdigest()
    elif tamper == "missing":
        npz.unlink()
    _write_manifest(run, m)
    with pytest.raises(flow.FlowCompanionError) as err:
        flow.load(run, row)
    assert err.value.code == code


def test_companion_of_a_record_without_those_raw_files_is_refused(run):
    row = _row(run)
    row = json.loads(json.dumps(row))
    del row["raw_outputs"]["files"]["dust/Output/run_res_0013.h5"]
    with pytest.raises(flow.FlowCompanionError) as err:
        flow.load(run, row)
    assert err.value.code == "source_mismatch"


def test_events_and_frame_selection_follow_the_accepted_series(run):
    row = _row(run)
    ev = flow.events(row)
    assert ev == {"release": 4, "first_contact": 13, "largest_opening": 16, "second_swing_min": 29, "last": 30}
    s = {r["window"]: r for r in row["series"]}
    assert s[3]["latch_active"] and not s[4]["latch_active"] and any(s[13]["contact_active"])
    assert not any(s[12]["contact_active"])
    picked = flow.select_windows(row, max_frames=8)
    assert picked == sorted(set(picked)) and picked[-1] == 30 and set(ev.values()) <= set(picked)


def test_service_finds_the_run_folder_only_for_its_own_record(run, monkeypatch):
    root = run.parents[1]
    monkeypatch.setenv(svc.RUNS_ENV, str(run.parent))
    row = _row(run)
    assert svc.local_run_dir(root, row) == run.resolve()
    assert svc.load_flow(root, row).windows[-1] == 30
    other = json.loads(json.dumps(row)); other["raw_outputs"]["run_id"] = "../escape"
    assert svc.local_run_dir(root, other) is None
    with pytest.raises(flow.FlowCompanionError) as err:
        svc.load_flow(root, other)
    assert err.value.code == "no_run_folder"


def test_figures_and_paraview_export_use_the_same_accepted_windows(run):
    row = _row(run)
    fc = flow.load(run, row)
    ev = flow.events(row)
    scene = views.flow_scene_figure(row, fc, 13)
    names = [t.name or "" for t in scene.data]
    assert any("Girdap parçacıkları" in n for n in names) and any("Hız düzlemi" in n for n in names)
    views.flow_plane_figure(row, fc, 13)
    timeline = views.response_timeline_figure(row, 13, ev)
    assert len(timeline.data) >= 6
    r, total = flow.radial_wake_strength(fc, 30, row["run_definition"]["case"]["geometry"]["tip_radius_m"])
    assert len(r) == len(total) and np.all(total >= 0) and total.sum() > 0
    z = zipfile.ZipFile(io.BytesIO(views.flow_vtk_zip(row, fc)))
    names = set(z.namelist())
    assert {"particles.pvd", "plane.pvd", "rotor.pvd", "flow_companion.json", "README.txt"} <= names
    head = z.read("particles/particles_00013.vtk")[:200].decode("latin1")
    assert head.startswith("# vtk DataFile Version 3.0") and "BINARY" in head
    assert f"POINTS {len(fc.particles(13)[0])} float" in head
    pvd = z.read("rotor.pvd").decode()
    assert pvd.count("<DataSet") == len(fc.windows)


def test_coloured_blade_scene_is_synchronised_to_one_accepted_window(run):
    """Blades posed from the window's MBDyn states and coloured with the same window's element loads, with the
    same window's particles and plane; the rotor-relative view rotates all of them by minus the azimuth."""
    from pyfoldable.application import blade_geometry as bg
    from pyfoldable.application import blade_views as bv
    from pyfoldable.visualization import blade_results as br
    from pyfoldable.visualization import blade_surface as bs
    row = _row(run)
    fc = flow.load(run, row)
    w = 13
    mesh = bs.loft(bg.spec_from_coupled(row), n_side=20, dr=0.01, joint="relief")
    fields = [br.coupled_fields(row, w, b)["fz_per_span"] for b in range(2)]
    phys = views.flow_blade_scene(row, fc, w, mesh, fields=fields, crange=(0.0, 200.0))
    names = [t.name or "" for t in phys.data]
    assert any(n.startswith("Sonuç") for n in names) and any("Girdap parçacıkları" in n for n in names)
    assert any("Hız düzlemi" in n for n in names)
    p, _, _ = fc.particles(w)
    part = next(t for t in phys.data if "Girdap parçacıkları" in (t.name or ""))
    rel = views.flow_blade_scene(row, fc, w, mesh, fields=fields, crange=(0.0, 200.0), rotor_fixed=True)
    part_rel = next(t for t in rel.data if "Girdap parçacıkları" in (t.name or ""))
    psi = bg.rotor_azimuth(row, w)
    x, y = np.asarray(part.x), np.asarray(part.y)
    assert np.allclose(part_rel.x, x * np.cos(-psi) - y * np.sin(-psi), atol=1e-6)
    blade = next(t for t in rel.data if (t.name or "").startswith("Sonuç"))
    # rotor-relative: blade 1's tip quarter-chord sits on +Y (azimuth removed)
    assert np.max(np.asarray(blade.y)) > 0.9 * 1000 * mesh.spec.stations[-1][0] * np.cos(np.radians(bg.folds_deg(row, w)[0]))


def test_dust_post_flow_field_reader_parses_genuine_output():
    path = Path(__file__).resolve().parents[2] / "pyfoldable" / "coupled" / "participants" / "extract_flow.py"
    spec = importlib.util.spec_from_file_location("extract_flow", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # importable without h5py
    a = mod._read_vtr(str(FIXTURE / "dust_post_window30_9x7.vtr"))
    assert a["x"].shape == (9,) and a["z"].shape == (7,) and a["velocity"].shape == (63, 3)
    assert np.isclose(a["x"][0], -0.4) and np.isclose(a["x"][-1], 0.4)
    assert np.all(np.isfinite(a["velocity"]))
    assert -30 < float(np.median(a["velocity"][:, 2])) < -10



def _rewrite_npz(run, m, **changes):
    import hashlib
    npz = run / "flow" / "flow_companion.npz"
    with np.load(npz) as z:
        arrays = {k: z[k] for k in z.files}
    arrays.update(changes)
    np.savez_compressed(npz, **arrays)
    m["npz"]["sha256"] = hashlib.sha256(npz.read_bytes()).hexdigest()
    _write_manifest(run, m)
    return arrays


def test_frames_relabelled_inside_the_accepted_windows_are_refused(run):
    """Swapping two frames' labels while keeping every listed file genuine must not pass:
    each source must be its own window's file, and DUST's time label must match that window."""
    row = _row(run)
    m = _manifest(run)
    raw = row["raw_outputs"]["files"]
    # (a) label says window 10 but the listed (genuine) file is window 13's
    m10 = json.loads(json.dumps(m))
    m10["sources"][3]["file"] = flow.source_file(13)
    m10["sources"][3]["sha256"] = raw[flow.source_file(13)]["sha256"]
    _write_manifest(run, m10)
    with pytest.raises(flow.FlowCompanionError) as err:
        flow.load(run, row)
    assert err.value.code == "malformed"
    # (b) arrays and labels permuted consistently (frames of 10 and 13 swapped, files relabelled)
    m2 = json.loads(json.dumps(m))
    with np.load(run / "flow" / "flow_companion.npz") as z:
        t = z["time_label_s"].copy()
    t[3], t[4] = t[4], t[3]
    _rewrite_npz(run, m2, time_label_s=t)
    with pytest.raises(flow.FlowCompanionError) as err:
        flow.load(run, row)
    assert err.value.code == "malformed"


@pytest.mark.parametrize("mutate, code", [
    (lambda m: [1, 2, 3], "unsupported"),
    (lambda m: {k: v for k, v in m.items() if k != "sources"}, "malformed"),
    (lambda m: {**m, "windows": [], "sources": []}, "malformed"),
    (lambda m: {**m, "windows": m["windows"][:2] + m["windows"][1:]}, "malformed"),
    (lambda m: {**m, "sources": [None] + m["sources"][1:]}, "malformed"),
    (lambda m: {**m, "auxiliary_sources": [{"file": "dust/Output/run_geo.h5", "sha256": "0" * 64}]}, "source_mismatch"),
    (lambda m: {**m, "particles_total": m["particles_total"] + 1}, "malformed"),
])
def test_malformed_manifests_raise_flow_errors_not_crashes(run, mutate, code):
    row = _row(run)
    _write_manifest(run, mutate(_manifest(run)))
    with pytest.raises(flow.FlowCompanionError) as err:
        flow.load(run, row)
    assert err.value.code == code


def test_non_finite_plane_coordinates_are_refused(run):
    row = _row(run)
    with np.load(run / "flow" / "flow_companion.npz") as z:
        x = z["plane_x_m"].copy()
    x[0] = np.nan
    _rewrite_npz(run, _manifest(run), plane_x_m=x)
    with pytest.raises(flow.FlowCompanionError) as err:
        flow.load(run, row)
    assert err.value.code == "malformed"


def test_run_folder_must_hold_this_record_and_lie_inside_the_runs_root(run, tmp_path, monkeypatch):
    root = run.parents[1]
    monkeypatch.setenv(svc.RUNS_ENV, str(run.parent))
    row = _row(run)
    assert svc.local_run_dir(root, row) is not None
    for bad in ("/etc", "C:x", "a\x00b", "..", "x/../y"):
        other = json.loads(json.dumps(row)); other["raw_outputs"]["run_id"] = bad
        assert svc.local_run_dir(root, other) is None, bad
    forged = json.loads(json.dumps(row)); forged["result_sha256"] = "a" * 64  # same run_id, other record
    assert svc.local_run_dir(root, forged) is None
    outside = tmp_path / "elsewhere"
    shutil.copytree(run, outside)
    (run.parent / "linked").symlink_to(outside, target_is_directory=True)
    linked = json.loads(json.dumps(row)); linked["raw_outputs"]["run_id"] = "linked"
    assert svc.local_run_dir(root, linked) is None


def _series(latch, contact, theta):
    return {"execution": {"valid_prefix_windows": len(latch)},
            "series": [{"window": i + 1, "latch_active": l, "contact_active": [c], "theta_deg": [t]}
                       for i, (l, c, t) in enumerate(zip(latch, contact, theta))]}


def test_event_detection_edge_cases():
    # never latched: no release, opening or contact events
    assert flow.events(_series([False] * 5, [False] * 5, [0.0] * 5)) == {"last": 5}
    # released but never touching the stop: release and largest opening only
    ev = flow.events(_series([True, True, False, False, False], [False] * 5, [-5, -5, -3, -1, -2]))
    assert ev == {"last": 5, "release": 3, "largest_opening": 4}
    # contact chatter (one-window gaps) does not end the first contact early
    latch = [True, False] + [False] * 12
    contact = [False, False, True, False, True, False, False, False, False, False, True, False, False, False]
    theta = [-5, -4, 0.2, -0.1, 0.1, -1.0, -2.0, -2.5, -1.5, -0.5, 0.1, -0.8, -1.2, -1.0]
    ev = flow.events(_series(latch, contact, theta))
    assert ev["release"] == 2 and ev["first_contact"] == 3 and ev["second_swing_min"] == 8


def test_velocity_plane_components_vectors_and_streamlines(run):
    row = _row(run)
    fc = flow.load(run, row)
    vel = fc.plane_velocity[fc.index(13)]
    x = fc.plane_x
    swirl = views.flow_plane_figure(row, fc, 13, component="swirl")
    heat = swirl.data[0]
    # tangential (swirl) velocity for rotation +Omega about +z on the y = 0 plane: v_y sign(x)
    assert np.allclose(np.asarray(heat.z), vel[:, :, 1] * np.sign(x)[None, :])
    assert "Dönme" in heat.colorbar.title.text
    radial = views.flow_plane_figure(row, fc, 13, component="radial")
    assert np.allclose(np.asarray(radial.data[0].z), vel[:, :, 0] * np.sign(x)[None, :])
    extra = views.flow_plane_figure(row, fc, 13, vectors=True, streamlines=True)
    names = [t.name or "" for t in extra.data]
    assert any("Hız vektörleri" in n for n in names) and any("Akım çizgileri" in n for n in names)


def test_axial_plane_shows_induced_velocity_on_one_scale_for_every_window(run):
    row = _row(run)
    fc = flow.load(run, row)
    vinf = row["run_definition"]["case"]["inflow_m_s"]
    a, b = (views.flow_plane_figure(row, fc, w).data[0] for w in (13, 30))
    assert (a.zmin, a.zmax) == (b.zmin, b.zmax)
    assert a.zmin == -a.zmax > -50  # centred on zero induced velocity
    assert np.allclose(np.asarray(a.z), -fc.plane_velocity[fc.index(13)][:, :, 2] - vinf)
    for comp in ("swirl", "radial"):
        s13, s30 = (views.flow_plane_figure(row, fc, w, component=comp).data[0] for w in (13, 30))
        assert (s13.zmin, s13.zmax) == (s30.zmin, s30.zmax) and s13.zmin == -s13.zmax
    # the 3-D plane uses the 2-D axial scale
    surf = next(t for t in views.flow_traces(row, fc, 30) if t.type == "surface")
    assert (surf.cmin, surf.cmax) == (a.zmin, a.zmax)


def test_aero_and_drive_torque_get_their_own_axes(run):
    row = _row(run)
    fig = views.time_figure(row, (("aero_shaft_torque_nm", "Aerodinamik şaft torku"),
                                  ("drive_torque_nm", "Tahrik (tepki) torku")), "Tork [N·m]", split=True)
    axis = {t.name: t.yaxis for t in fig.data if t.x and t.x[0] is not None}
    assert axis["Aerodinamik şaft torku"] != axis["Tahrik (tepki) torku"]


def test_per_blade_time_figure_has_one_legend_entry_per_channel(run):
    row = json.loads(json.dumps(_row(run)))
    row["execution"]["valid_prefix_windows"] = 20  # an invalid tail must not duplicate legend entries
    channels = (("hinge_aero_torque_nm", "Aerodinamik"), ("hinge_law_torque_nm", "Yay+sönüm+stop"))
    fig = views.time_figure(row, channels, "M [N·m]", per_blade=True)
    shown = [t.name for t in fig.data if t.showlegend is not False]
    assert {"Aerodinamik", "Yay+sönüm+stop", "Kanat 1", "Kanat 2"} <= set(shown)
    assert not any("dışı" in n and "·" in n for n in shown)
    assert len(shown) == len(set(shown))


def test_radial_figure_draws_every_blade(run):
    row = _row(run)
    rows = views.radial_rows(row, 13)
    segments = {r["segment"] for r in rows}

    def data_traces(fig):
        return [t for t in fig.data if t.x and t.x[0] is not None]
    assert len(data_traces(views.radial_figure(rows, "alpha_deg", "α [°]"))) == 2 * len(segments)
    four = [{**r, "blade": b} for r in rows if r["blade"] == 0 for b in range(4)]
    assert len(data_traces(views.radial_figure(four, "alpha_deg", "α [°]"))) == 4 * len(segments)


def test_playback_and_vtk_mark_windows_outside_the_valid_prefix(run):
    row = json.loads(json.dumps(_row(run)))
    row["execution"]["valid_prefix_windows"] = 20
    z = zipfile.ZipFile(io.BytesIO(views.vtk_zip(row)))
    assert "valid prefix" in z.read("README.txt").decode()
    assert "outside valid prefix" in z.read("rotor_00025.vtk").decode()[:200]
    assert "outside valid prefix" not in z.read("rotor_00020.vtk").decode()[:200]
    fig = views.playback_figure(row)
    titles = {f.name: f.layout.title.text for f in fig.frames}
    assert "geçerli önek dışı" in titles["30"] and "geçerli önek dışı" not in titles["0"]


def _contrast(colour):
    def lum(c):
        ch = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        r, g, b = (x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in ch)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    hi, lo = sorted((lum(colour), lum("#07111F")), reverse=True)  # app background, .streamlit/config.toml
    return (hi + 0.05) / (lo + 0.05)


def test_every_hard_coded_trace_colour_meets_the_figure_style_contrast(run):
    row = _row(run)
    fc = flow.load(run, row)
    ev = flow.events(row)
    figs = [views.time_figure(row, (("theta_deg", "θ"), ("theta_rate_rad_s", "θ̇")), "x", per_blade=True),
            views.coverage_figure(row, "alpha"), views.iterations_figure(row),
            views.radial_figure(views.radial_rows(row, 13), "cl", "c_l [-]"),
            views.response_timeline_figure(row, 13, ev), views.wake_radial_figure(row, fc, 13, 4),
            views.flow_plane_figure(row, fc, 13, vectors=True, streamlines=True), views.flow_scene_figure(row, fc, 13),
            views.playback_figure(row), go.Figure(views.flow_traces(row, fc, 13))]
    colours = set()
    for fig in figs:
        for t in fig.data:
            for part in ("line", "marker"):
                c = getattr(getattr(t, part, None), "color", None)
                if isinstance(c, str):
                    colours.add(c)
            if isinstance(getattr(t, "color", None), str):
                colours.add(t.color)
            per_point = getattr(getattr(t, "marker", None), "color", None)
            if isinstance(per_point, (list, tuple)):
                colours |= {c for c in per_point if isinstance(c, str)}
        colours |= {s.line.color for s in fig.layout.shapes if isinstance(s.line.color, str)}
    hexes = {c for c in colours if c.startswith("#")}
    assert hexes and [c for c in sorted(hexes) if _contrast(c) < 3.0] == []
