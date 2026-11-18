"""Aerodynamic screening of the printable 13-inch prototype: candidate E against the unmodified 13×5.5-class blade.

- **Blade-shape effect only.** Both blades fully deployed (fold 0), treated as continuous strip-theory blades with the
  same printable section family. The deployed joint step (distal 6 mm up the shaft at r_j, bosses, stop nose, 0.3 mm
  face gap) is outside strip theory and is not modelled: the joint-step effect is unresolved, not zero.
- **Section polars.** The printable section (catalog profile, trailing edge thickened to a fixed 0.8 mm) is a
  chord-dependent family: the normalised thickening is t_TE / c. XFOIL polars are generated at a few chords through
  the repository's provider route (``XfoilProvider``, the pinned 6.99 executable and the solver settings of
  ``DECLARATION``) and blended spanwise where the local chord equals each family chord (``SpanwisePolarSchedule``).
- **BEM.** ``solve_bem_rotor`` over the declared station span with ``bounds="error"``: a point whose queries leave the
  polar grid, or whose annulus does not converge, fails and stays in the table with its reason. A separate
  ``bounds="clamp"`` diagnostic (static, low J) counts a point only if no converged annulus state is clamped; it is
  not fail-closed. Speeds are owner what-if values (no maximum RPM supplied).

Unqualified numerical screening; physical qualification is false. Prototype inputs are mm/degrees, solver inputs SI;
field names carry units.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import numpy as np

from pyfoldable.core import BEMRotorSettings, PolarFamily, PolarTable, solve_bem_rotor
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.bem import BEMAnnulusSettings
from pyfoldable.core.bem_rotor import BEMRotorElementError, BEMRotorError
from pyfoldable.core.models import AirfoilDefinition, BladeGeometry, BladeStation, OperatingCondition
from pyfoldable.core.polar_spanwise import SpanwisePolarAnchor, SpanwisePolarSchedule

from . import cad

ATMOSPHERE = {"air_density_kg_m3": 1.225, "dynamic_viscosity_pa_s": 1.789e-5, "temperature_k": 288.15,
              "pressure_pa": 101325.0}           # ISA sea level: an assumption, not a measured test-day atmosphere
DECLARATION = "configs/polars/RESEARCH_AXIAL_800_DEPLOY_V3.json"   # pinned executable and solver settings reused
PREFLIGHT = Path.home() / "pyf-work/xfoil/preflight"                # operator bundle that holds the pinned executable
SCENARIO = "prototype_13in_printable_section_xfoil_v1"
# sized from envelope_rows at 3000–8000 RPM, J ≤ 0.5; dense so an isolated failed cell leaves a neighbour (attempt 2,
# six levels, and attempt 3, without 155k/185k, left the 16.5 mm Mach-0.30 row ending at 140k: 7000–8000 RPM failed)
REYNOLDS = (25e3, 33e3, 40e3, 50e3, 60e3, 75e3, 90e3, 115e3, 140e3, 155e3, 170e3, 185e3, 200e3, 250e3, 300e3)
MACH = (0.0, 0.15, 0.30, 0.45)
ALPHA_DEG = tuple(range(-6, 13, 2))                  # attempt 1 (−8…14°) lost cells at the −8° cold start and 12–14°
INTERIOR_CHORDS_MM = (30.0, 23.0, 16.5)              # plus the shared root and tip station chords
ADVANCE_RATIOS = (0.0, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5)
LOADING_RPM = 6000.0                                  # spanwise-loading figure (= explore.REFERENCE_RPM)
# signed_nonreversed: outer sections unload first as J rises; positive_only would fail the rotor there
SETTINGS = BEMRotorSettings(annulus_settings=BEMAnnulusSettings(loading_branch="signed_nonreversed"))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def designs(root) -> dict:
    """Candidate E and the reference (twist ×0.86, no hinge zone), built exactly as ``study.run_report`` builds them."""
    from . import explore, study
    from .design import default_design, with_changes
    root = Path(root)
    base = with_changes(default_design(root), **{"connection.axial_offset_mm": study.REPORT_OFFSET_MM})
    return {"E": explore.candidate_design(base, root, study.E_PARAMS),
            "reference": explore.candidate_design(base, root, {"planform.twist_scale": 0.86})}


def blade_geometry(d, airfoil_id=None) -> BladeGeometry:
    R = d.planform.tip_radius_mm
    return BladeGeometry(d.planform.diameter_mm / 1000.0, d.hub_radius_mm / 1000.0, d.planform.blade_count,
                         tuple(BladeStation(r / R, c / 1000.0, math.radians(t), airfoil_id or d.section_identity)
                               for r, c, t in d.planform.stations))


def section_airfoil(d, chord_mm: float) -> AirfoilDefinition:
    """The printable section at one chord (its own identity: the thickened trailing edge is t_TE / c)."""
    prof = cad.printable_profile(d, chord_mm)
    return AirfoilDefinition(
        f"{d.section_identity}@c{chord_mm:.2f}mm",
        f"pyfoldable.prototype.cad.printable_profile at chord {chord_mm:.4f} mm",
        tuple((float(x), float(z)) for x, z in prof),
        {"chord_mm": chord_mm, "section_identity": d.section_identity})


def envelope_rows(d, rpms, advance_ratios, radii_over_R=(0.2, 0.33, 0.5, 0.6, 0.75, 0.87, 0.98)) -> list[dict]:
    """Section Reynolds and Mach without induction, W = √((Ωr)² + V²), V = J·n·D (what-if speeds)."""
    a = math.sqrt(1.4 * 287.05 * ATMOSPHERE["temperature_k"])         # same dry-air constants as the BEM kernel
    R, D = d.planform.tip_radius_mm / 1000.0, d.planform.diameter_mm / 1000.0
    rows = []
    for rpm in rpms:
        for J in advance_ratios:
            for x in radii_over_R:
                chord_m = d.section(x * R * 1000.0)[0] / 1000.0
                W = math.hypot(2 * math.pi * rpm / 60.0 * x * R, J * rpm / 60.0 * D)
                rows.append({"rpm": rpm, "J": J, "r_over_R": x, "chord_mm": chord_m * 1000.0, "W_m_s": W,
                             "reynolds": ATMOSPHERE["air_density_kg_m3"] * W * chord_m / ATMOSPHERE["dynamic_viscosity_pa_s"],
                             "mach": W / a})
    return rows


def family_chords(ds) -> tuple:
    """Root station chord, the interior chords, tip station chord (descending): together they span every annulus."""
    ds = list(ds)
    roots, tips = {d.planform.stations[0][1] for d in ds}, {d.planform.stations[-1][1] for d in ds}
    if len(roots) != 1 or len(tips) != 1:
        raise ValueError("The compared blades must share their root and tip station chords.")
    return (roots.pop(), *INTERIOR_CHORDS_MM, tips.pop())


def radius_at_chord(d, chord_mm: float) -> float:
    r, c = np.array(d.planform.stations)[:, :2].T
    if np.any(np.diff(c) >= 0) or not c[-1] <= chord_mm <= c[0]:
        raise ValueError("Chord must fall strictly outward and the family chord must lie in the blade's chord range.")
    return float(np.interp(chord_mm, c[::-1], r[::-1]))


def check_family(d, chord_mm: float, family: PolarFamily) -> None:
    """A family belongs to one chord's section: matching identity and coordinate SHA-256 on every table."""
    foil = section_airfoil(d, chord_mm)
    sha = airfoil_coordinate_sha256(foil)
    if family.airfoil_id != foil.id or any(t.metadata.get("airfoil_coordinate_sha256") != sha for t in family.tables):
        raise ValueError(f"Polar family {family.airfoil_id} does not belong to {foil.id} (coordinates {sha[:12]}).")


def schedule(d, families: dict) -> SpanwisePolarSchedule:
    """Anchor each chord family where the blade's local chord equals that chord; blended linearly in r between."""
    for c, f in families.items():
        check_family(d, c, f)
    R = d.planform.tip_radius_mm
    anchors = sorted(((radius_at_chord(d, c) / R, f) for c, f in families.items()), key=lambda a: a[0])
    return SpanwisePolarSchedule(f"{d.section_identity}:chord-schedule",
                                 tuple(SpanwisePolarAnchor(x, f) for x, f in anchors))


# ------------------------------------------------------------------------------------------------- XFOIL route
PINS = {"bin/xfoil": "executable_sha256", "runtime/osmapDP.dat": "osmap_sha256",
        "build/build-record.json": "build_record_sha256"}
SOURCES = {"declaration": DECLARATION, "adapter": "pyfoldable/providers/xfoil.py",
           "generator": "pyfoldable/prototype/aero.py", "profile": "pyfoldable/prototype/cad.py"}


def _verify_bundle(pre: Path, decl) -> None:
    from pyfoldable.core.providers import PolarProviderUnavailableError
    for name, key in PINS.items():
        if not (pre / name).is_file() or _sha((pre / name).read_bytes()) != decl[key]:
            raise PolarProviderUnavailableError(f"Pinned XFOIL bundle missing or changed: {pre / name}")


@contextmanager
def xfoil_provider(root, preflight=PREFLIGHT):
    """The pinned executable through ``XfoilProvider`` (the operator route's checks: pinned bytes, Linux x86_64, no
    loader overrides), re-verified after the block; OSMAP is set only while the block runs."""
    from pyfoldable.core.providers import PolarProviderUnavailableError
    from pyfoldable.providers.xfoil import XfoilProvider
    decl = json.loads((Path(root) / DECLARATION).read_bytes())
    pre = Path(preflight)
    _verify_bundle(pre, decl)
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise PolarProviderUnavailableError("The pinned XFOIL build runs on Linux x86_64 only.")
    if any(os.environ.get(k) for k in ("LD_PRELOAD", "LD_LIBRARY_PATH")):
        raise PolarProviderUnavailableError("Loader overrides are set; the pinned executable would not run as recorded.")
    previous = os.environ.get("OSMAP")
    os.environ["OSMAP"] = str(pre / "runtime/osmapDP.dat")         # as the operator launcher sets it
    try:
        yield XfoilProvider(pre / "bin/xfoil", backend_version=decl["provider"]["backend_version"]), decl
        _verify_bundle(pre, decl)                                  # bytes unchanged through the runs
    finally:
        if previous is None:
            os.environ.pop("OSMAP", None)
        else:
            os.environ["OSMAP"] = previous


def _settings(decl) -> dict:
    return {"scenario_id": SCENARIO, "alpha_deg": ALPHA_DEG, "reynolds": REYNOLDS, "mach": MACH,
            **{k: decl[k] for k in ("n_crit", "xtr_upper", "xtr_lower", "max_iterations", "timeout_s", "options")},
            "attempts_per_cell": 1, "batch_policy": "one plan per Mach level, collect_all / complete_axes"}


def generate_family(provider, decl, d, chord_mm, reynolds=REYNOLDS, mach=MACH) -> tuple:
    """One chord's grid as one plan per Mach level, one attempt per cell. A failed cell (XFOIL leaves isolated
    single-angle non-convergence) drops only itself from its Mach row; it is collected, never repaired."""
    from pyfoldable.core.polar_family_generation import (PolarFamilyBatchPolicy, PolarFamilyGenerationPlan,
                                                         generate_polar_family_batch)
    from pyfoldable.core.polar_orchestration import PolarRetryPolicy
    from pyfoldable.core.providers import PolarGenerationRequest
    template = PolarGenerationRequest(
        airfoil=section_airfoil(d, chord_mm), alpha_rad=tuple(math.radians(a) for a in ALPHA_DEG),
        reynolds=reynolds[0], mach=mach[0], n_crit=decl["n_crit"], xtr_upper=decl["xtr_upper"],
        xtr_lower=decl["xtr_lower"], max_iterations=decl["max_iterations"], timeout_s=decl["timeout_s"],
        scenario_id=SCENARIO, options=decl["options"])
    return tuple(generate_polar_family_batch(
        [provider], PolarFamilyGenerationPlan(replace(template, mach=m), tuple(reynolds), (m,)),
        policy=PolarFamilyBatchPolicy("collect_all", "complete_axes"), retry_policy=PolarRetryPolicy(max_attempts=1))
        for m in mach)


def merged_family(batches) -> PolarFamily | None:
    """Complete cells of every Mach row as one family (each Mach level keeps its own Reynolds grid)."""
    tables = tuple(t for b in batches if b.family is not None for t in b.family.tables)
    return PolarFamily(tables) if tables else None


def polar_record(root, d, provider, decl, batches: dict) -> dict:
    root = Path(root)
    fams = []
    for c, rows in batches.items():
        foil = section_airfoil(d, c)
        family = merged_family(rows)
        fams.append({
            "chord_mm": c, "airfoil_id": foil.id, "coordinate_sha256": airfoil_coordinate_sha256(foil),
            "te_thickness_over_chord": d.print_model.min_te_thickness_mm / c, "coordinates": foil.coordinates,
            "planned_cells": sum(b.plan.cell_count for b in rows), "complete_cells": sum(len(b.cells) for b in rows),
            "reynolds_by_mach": {str(b.plan.mach_grid[0]): b.family_reynolds_grid for b in rows},
            "failures": [{"reynolds": f.request.reynolds, "mach": f.request.mach, "error_type": f.error_type,
                          "error": f.error_message,
                          "unusable_alpha_deg": [round(math.degrees(p.alpha_rad), 6) for p in f.failed_result.points
                                                 if not p.usable] if f.failed_result else None}
                         for b in rows for f in b.failures],
            "tables": [] if family is None else [vars(t) for t in family.tables]})   # dumped with default=dict
    return {
        "schema_version": 1, "artifact_class": "prototype_printable_section_polars", "physical_qualification": False,
        "evidence": "XFOIL 6.99 numerical polars, unqualified; attached-flow validity only. Rows near and beyond stall "
                    "are solver output, not data.",
        "section_identity": d.section_identity, "te_thickness_mm": d.print_model.min_te_thickness_mm,
        "te_blend_start_x_over_c": d.print_model.te_blend_start, "provider": provider.identity.as_mapping(),
        "pinned": {k: decl[k] for k in PINS.values()},            # declared and checked before and after the runs
        "source_sha256": {k: _sha((root / p).read_bytes()) for k, p in SOURCES.items()}, "source_files": SOURCES,
        "settings": _settings(decl), "families": fams}


def check_record(root, record: dict) -> None:
    """A saved record must match the current route: declaration and adapter bytes, pinned hashes, provider, settings,
    and every table's source, scenario and grid. The section coordinates are checked per family on rebuild."""
    root = Path(root)
    decl = json.loads((root / DECLARATION).read_bytes())
    source = f"{decl['provider']['name']}:{decl['provider']['backend_version']}"
    alpha = [math.radians(a) for a in ALPHA_DEG]
    bad = [k for k, ok in (
        ("settings", record.get("settings") == json.loads(json.dumps(_settings(decl)))),
        ("pinned hashes", record.get("pinned") == {k: decl[k] for k in PINS.values()}),
        ("provider", record.get("provider") == decl["provider"]),
        *((f"{k} bytes", record.get("source_sha256", {}).get(k) == _sha((root / SOURCES[k]).read_bytes()))
          for k in ("declaration", "adapter"))) if not ok]
    bad += [f"table {f['chord_mm']} mm M{t['mach']} Re{t['reynolds']:.0f}" for f in record["families"]
            for t in f["tables"]
            if t["source"] != source or t["scenario_id"] != SCENARIO or t["reynolds"] not in REYNOLDS
            or t["mach"] not in MACH or len(t["alpha_rad"]) != len(alpha)
            or not all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(t["alpha_rad"], alpha))]
    if bad:
        raise ValueError(f"Polar record does not match the current XFOIL route ({', '.join(bad[:5])}); regenerate it.")


def families_from_record(d, record: dict) -> dict:
    """Rebuild chord → PolarFamily from a saved record; stale coordinates (a changed section) are refused."""
    out = {}
    for f in record["families"]:
        if not f["tables"]:
            continue
        tables = tuple(PolarTable(**{**t, **{k: tuple(t[k]) for k in ("alpha_rad", "cl", "cd", "cm")}})
                       for t in f["tables"])
        family = PolarFamily(tables)
        check_family(d, f["chord_mm"], family)
        out[f["chord_mm"]] = family
    return out


# ------------------------------------------------------------------------------------------------- BEM
def run_point(d, polars, rpm: float, J: float, *, bounds="error", settings=SETTINGS, zone_mm=(0.0, 0.0)) -> dict:
    """One what-if point; any failure is a row with its reason and no totals. ``zone_mm``: radii whose annulus
    thrust is also summed (the reshaped span)."""
    blade = blade_geometry(d)
    n = rpm / 60.0
    cond = OperatingCondition(f"rpm{rpm:.0f}-J{J:.3f}", 2 * math.pi * n, J * n * blade.diameter_m, **ATMOSPHERE)
    row = {"rpm": rpm, "J": J, "forward_speed_m_s": cond.forward_speed_m_s, "bounds": bounds, "speed_basis": "what-if"}
    try:
        res = solve_bem_rotor(blade, cond, polars, bounds=bounds, settings=settings)
    except (BEMRotorError, BEMRotorElementError, ValueError, ArithmeticError) as exc:
        kind = next((k for k, s in (("alpha outside polar data", "Requested alpha_rad"),
                                    ("Reynolds outside polar data", "Requested reynolds"),
                                    ("Mach outside polar data", "Requested mach")) if s in str(exc)), "solver")
        return {**row, "status": "failed", "failure_kind": kind, "reason": f"{type(exc).__name__}: {exc}"}
    env = res.polar_query_envelope
    disk = math.pi * blade.radius_m ** 2
    hover = J == 0 and res.thrust_n > 0 and res.shaft_power_w > 0
    return {**row, "status": "ok", "reason": "", "thrust_n": res.thrust_n, "torque_nm": res.torque_nm,
            "power_w": res.shaft_power_w, "ct": res.thrust_coefficient, "cp": res.power_coefficient,
            # the kernel reports V·T/P whenever P > 0; with T ≤ 0 that is not a propulsive efficiency
            "eta": res.propulsive_efficiency if res.thrust_n > 0 else None,
            # full disk area although the BEM span is 0.20R–0.98R (as the usual FM definition)
            "figure_of_merit": res.thrust_n ** 1.5 / (res.shaft_power_w * math.sqrt(2 * cond.air_density_kg_m3 * disk))
            if hover else None,
            "zone_thrust_n": math.fsum(e.thrust_n for e in res.elements
                                       if zone_mm[0] <= e.solution.radius_m * 1000 <= zone_mm[1]),
            "clamped_dimensions": list(res.clamped_dimensions),
            # converged annulus states outside the polar data; with bounds="clamp" only the bracket scan may be
            "solution_clamped_elements": sum(bool(e.solution.clamped_dimensions) for e in res.elements),
            "alpha_query_deg": [math.degrees(env.alpha_rad_min), math.degrees(env.alpha_rad_max)],
            "reynolds_query": [env.reynolds_min, env.reynolds_max], "mach_query": [env.mach_min, env.mach_max],
            "elements": [{"r_mm": e.solution.radius_m * 1000, "width_mm": e.width_m * 1000,
                          "chord_mm": e.solution.chord_m * 1000,
                          "twist_deg": math.degrees(e.solution.twist_rad),
                          "alpha_deg": math.degrees(e.solution.angle_of_attack_rad), "reynolds": e.solution.reynolds,
                          "mach": e.solution.mach, "cl": e.solution.cl, "cd": e.solution.cd,
                          "dT_dr_n_per_m": e.solution.differential_thrust_n_m,
                          "dQ_dr_nm_per_m": e.solution.differential_torque_nm_m} for e in res.elements]}


def rpm_for_thrust(d, polars, thrust_n: float, speed_m_s: float, j_range=(0.15, 0.45), grid=12, tol_n=0.01, **kw):
    """Speed at which the blade gives ``thrust_n`` at forward speed V (equal thrust, equal inflow), fail-closed: the
    root is bracketed on a grid of usable points inside ``j_range`` and bisected; every evaluation used must be
    usable (no polar query or converged state outside the data). Otherwise the row says "not covered"."""
    D = d.planform.diameter_mm / 1000.0
    lo_rpm, hi_rpm = 60.0 * speed_m_s / (j_range[1] * D), 60.0 * speed_m_s / (j_range[0] * D)
    pts = [run_point(d, polars, r, speed_m_s / (r / 60.0 * D), **kw) for r in np.linspace(lo_rpm, hi_rpm, grid)]
    ok = [r for r in pts if usable(r)]
    base = {"speed_m_s": speed_m_s, "target_thrust_n": thrust_n}
    pair = next(((a, b) for a, b in zip(ok, ok[1:]) if (a["thrust_n"] - thrust_n) * (b["thrust_n"] - thrust_n) <= 0), None)
    if pair is None:
        return {**base, "status": "not covered", "reason": f"no usable bracket in J {j_range} "
                f"({len(ok)}/{grid} grid points usable)"}
    a, b = pair
    for _ in range(40):
        rpm = 0.5 * (a["rpm"] + b["rpm"])
        m = run_point(d, polars, rpm, speed_m_s / (rpm / 60.0 * D), **kw)
        if not usable(m):
            return {**base, "status": "not covered", "reason": f"midpoint {rpm:.0f} RPM not usable"}
        if abs(m["thrust_n"] - thrust_n) <= tol_n:
            break
        a, b = (a, m) if (a["thrust_n"] - thrust_n) * (m["thrust_n"] - thrust_n) <= 0 else (m, b)
    return {**base, "status": "ok", "rpm": m["rpm"], "J": m["J"], "thrust_n": m["thrust_n"], "power_w": m["power_w"],
            "eta": m.get("eta")}


def equal_thrust(ds: dict, polars: dict, reference: str, points) -> list[dict]:
    """For each (V, reference RPM): the reference's thrust there, then every design's RPM and power for that thrust
    at that V (fail-closed)."""
    rows = []
    for speed, ref_rpm in points:
        d0 = ds[reference]
        D = d0.planform.diameter_mm / 1000.0
        r0 = run_point(d0, polars[reference], ref_rpm, speed / (ref_rpm / 60.0 * D))
        if not usable(r0):
            rows.append({"design": reference, "speed_m_s": speed, "status": "not covered", "reason": "reference point"})
            continue
        for k, d in ds.items():
            r = rpm_for_thrust(d, polars[k], r0["thrust_n"], speed)
            if r["status"] == "ok":
                r.update(rpm_ratio=r["rpm"] / ref_rpm, power_ratio=r["power_w"] / r0["power_w"])
            rows.append({"design": k, "reference_rpm": ref_rpm, **r})
    return rows


def compare(ds: dict, polars: dict, rpms, advance_ratios, **kw) -> list[dict]:
    return [{"design": k, **run_point(d, polars[k], rpm, J, **kw)}
            for rpm in rpms for J in advance_ratios for k, d in ds.items()]


def usable(r) -> bool:
    """Solved with every converged annulus state inside the polar data."""
    return r["status"] == "ok" and r["solution_clamped_elements"] == 0


def deltas(rows) -> list[dict]:
    """E relative to the reference at the same RPM and J (only where both are usable)."""
    by = {(r["rpm"], r["J"], r["design"]): r for r in rows}
    out = []
    for (rpm, J, k), e in by.items():
        ref = by.get((rpm, J, "reference"))
        if k != "E" or ref is None:
            continue
        row = {"rpm": rpm, "J": J, "bounds": e["bounds"], "E": e["status"], "reference": ref["status"],
               "both_usable": usable(e) and usable(ref)}
        if row["both_usable"]:
            row.update({f"{q}_{s}": r[q] for q in ("thrust_n", "power_w", "eta", "figure_of_merit", "zone_thrust_n")
                        for s, r in (("E", e), ("ref", ref))})
            pct = lambda q: 100 * (e[q] / ref[q] - 1) if ref[q] > 0 else None    # no ratio to a non-positive base
            row.update({"d_thrust_pct": pct("thrust_n"), "d_power_pct": pct("power_w"),
                        "d_eta": None if None in (e["eta"], ref["eta"]) else e["eta"] - ref["eta"]})
        out.append(row)
    return out


# ------------------------------------------------------------------------------------------------- report
def figure(ds, rows, diag, families, title=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 3, figsize=(16, 9.5))
    style = {"E": dict(color="#E45756"), "reference": dict(color="#4C78A8")}
    rpms = sorted({r["rpm"] for r in rows})
    shown = [rpms[0], LOADING_RPM, rpms[-1]] if LOADING_RPM in rpms else rpms[:3]
    for key, a in zip(("ct", "cp", "eta"), ax[0]):
        for k in ds:
            for rpm, ls in zip(shown, (":", "-", "--")):
                pts = [(r["J"], r[key]) for r in rows if r["design"] == k and r["rpm"] == rpm and usable(r)
                       and r[key] is not None]
                if pts:
                    a.plot(*zip(*pts), ls=ls, marker="o", ms=3, label=f"{k} {rpm:.0f} RPM", **style[k])
                extra = [(r["J"], r[key]) for r, s in zip(diag, rows) if r["design"] == k and r["rpm"] == rpm
                         and usable(r) and not usable(s) and r[key] is not None]
                if extra:
                    a.plot(*zip(*extra), ls="none", marker="o", mfc="none", ms=5, **style[k])
            bad = [r["J"] for r in rows if r["design"] == k and not usable(r) and r["rpm"] in shown]
            a.plot(bad, [0.0] * len(bad), "x", ms=7, **style[k])
        a.set(xlabel="J = V/(nD) [-]", ylabel={"ct": "C_T [-]", "cp": "C_P [-]", "eta": "η [-]"}[key],
              title=f"{key.upper()} vs J (x failed fail-closed; o clamp diagnostic)")
        a.grid(alpha=0.3)
    ax[0][0].legend(fontsize=7)
    a3, a4, a5 = ax[1]
    for J, ls, src in ((0.0, "-.", diag), (0.2, ":", rows), (0.3, "-", rows), (0.4, "--", rows)):
        for k in ds:
            r = next((r for r in src if r["design"] == k and r["rpm"] == LOADING_RPM and r["J"] == J
                      and usable(r)), None)
            if r:
                e = r["elements"]
                a3.plot([x["r_mm"] for x in e], [x["dT_dr_n_per_m"] for x in e], ls=ls,
                        label=f"{k} J={J}" + (" (clamp diag.)" if src is diag else ""), **style[k])
                if J == 0.3:
                    a4.plot([x["r_mm"] for x in e], [x["alpha_deg"] for x in e], label=f"{k} α, J=0.3", **style[k])
    R = next(iter(ds.values())).planform.tip_radius_mm
    for a in (a3, a4):
        a.axvline(99.0, color="0.3", lw=0.8, ls="-.")
        a.axvspan(0.33 * R, 0.87 * R, color="0.5", alpha=0.08)
        a.grid(alpha=0.3)
    a3.set(xlabel="r [mm] (joint 99 mm; shaded 0.33R–0.87R)", ylabel="dT/dr [N/m] (both blades)",
           title=f"Spanwise thrust loading, {LOADING_RPM:.0f} RPM what-if")
    a3.legend(fontsize=7)
    for k, d in ds.items():
        st = np.array(d.planform.stations)
        a4.plot(st[:, 0], st[:, 2], ls="--", lw=0.8, label=f"{k} twist", **style[k])
    a4.set(xlabel="r [mm]", ylabel="[°]", title="Section angle of attack (J = 0.3) and geometric twist")
    a4.legend(fontsize=7)
    for (c, fam), col in zip(sorted(families.items()), ("#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e")):
        for t in fam.tables:
            if t.mach == 0.15 and t.reynolds == 90e3:
                a5.plot([cd for cd in t.cd], t.cl, marker=".", color=col, label=f"c = {c:.1f} mm (t_TE/c {0.8 / c:.1%})")
    a5.set(xlabel="c_d [-]", ylabel="c_l [-]",
           title=f"Printable section, XFOIL, Re 90k, M 0.15 ({ALPHA_DEG[0]}…{ALPHA_DEG[-1]}°)")
    a5.legend(fontsize=7)
    a5.grid(alpha=0.3)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    return fig


def _csv(path, rows):
    import csv
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def run_report(root, folder, preflight=PREFLIGHT) -> dict:
    """Polars (generated once through the pinned XFOIL, then reloaded with identity checks), BEM comparison, figure."""
    root, folder = Path(root), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    ds = designs(root)
    E = ds["E"]
    chords = family_chords(ds.values())
    polar_path = folder / "polars_printable_section.json"
    if not polar_path.exists():
        with xfoil_provider(root, preflight) as (provider, decl):
            batches = {c: generate_family(provider, decl, E, c) for c in chords}
        polar_path.write_text(json.dumps(polar_record(root, E, provider, decl, batches), indent=1, default=dict),
                              encoding="utf-8")                   # default=dict: provider metadata holds mappingproxies
    record = json.loads(polar_path.read_text(encoding="utf-8"))
    check_record(root, record)
    missing = [f["chord_mm"] for f in record["families"] if not f["tables"]]
    if missing:
        raise RuntimeError(f"No complete polar family for chords {missing} mm; see {polar_path.name}.")
    sched = {k: schedule(d, families_from_record(d, record)) for k, d in ds.items()}
    families = families_from_record(E, record)
    rpms = E.operating.what_if_rpm
    p = E.planform                                                 # the reshaped span: r_j − w_in … r_j + w_out
    zone = (p.hinge_zone_center_mm - p.hinge_zone_mm, p.hinge_zone_center_mm + (p.hinge_zone_outboard_mm or p.hinge_zone_mm))
    rows = compare(ds, sched, rpms, ADVANCE_RATIOS, zone_mm=zone)
    # diagnostic, not fail-closed: bounds clamped, a point counts only if no converged annulus state is clamped
    # (the bracket scan starts at α = local twist − no-induction inflow, 26.4° at the first annulus when static)
    diag = compare(ds, sched, rpms, ADVANCE_RATIOS, bounds="clamp", zone_mm=zone)
    _csv(folder / "envelope_no_induction.csv",
         [{"design": k, **r} for k, d in ds.items() for r in envelope_rows(d, rpms, (0.0, 0.5))])
    for name, rr in (("bem_comparison", rows), ("bem_clamp_diagnostic", diag)):
        _csv(folder / f"{name}.csv", [{k: v for k, v in r.items() if k != "elements"} for r in rr])
        _csv(folder / f"{name}_deltas.csv", deltas(rr))
    _csv(folder / "spanwise_loading.csv", [{"design": r["design"], "rpm": r["rpm"], "J": r["J"], "bounds": r["bounds"], **e}
                                           for r in rows + diag if usable(r) for e in r["elements"]])
    figure(ds, rows, diag, families, "Candidate E vs reference (13×5.5-class, twist ×0.86): blade-shape effect only, "
                               "continuous blades, what-if speeds; joint step not modelled").savefig(
        folder / "aero_comparison.png", dpi=110)
    summary = {
        "schema_version": 1, "artifact_class": "prototype_aero_screening", "physical_qualification": False,
        "scope": "blade-shape effect (E vs reference) as continuous strip-theory blades, fold 0; joint step unresolved",
        "designs": {k: {"identity": d.identity, "section_identity": d.section_identity,
                        "stations_mm_mm_deg": d.planform.stations, "axial_offset_mm": d.connection.axial_offset_mm}
                    for k, d in ds.items()},
        "atmosphere": ATMOSPHERE, "bem_settings": SETTINGS.as_mapping(), "bounds": "error",
        "speeds_rpm": list(rpms), "speed_basis": "owner what-if (no maximum RPM supplied)",
        "advance_ratios": ADVANCE_RATIOS, "family_chords_mm": chords, "zone_mm": zone,
        "anchors_r_mm": {k: [a.r_over_R * d.planform.tip_radius_mm for a in sched[k].anchors] for k, d in ds.items()},
        "polars": {"file": polar_path.name, "sha256": _sha(polar_path.read_bytes()), "provider": record["provider"],
                   "pinned": record["pinned"]},
        "points": len(rows), "usable_points": sum(map(usable, rows)),
        "failure_kinds": {k: sum(r.get("failure_kind") == k for r in rows) for k in
                          sorted({r["failure_kind"] for r in rows if r["status"] != "ok"})},
        "clamp_diagnostic": {"points": len(diag), "usable_points": sum(map(usable, diag)),
                             "solution_outside_data": sum(r["status"] == "ok" and not usable(r) for r in diag),
                             "failed": sum(r["status"] != "ok" for r in diag)},
    }
    (folder / "aero_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"summary": summary, "rows": rows, "clamp_diagnostic": diag}


def distal_aero_loads(d, row) -> dict:
    """Aerodynamic forces on one blade's distal segment from a solved BEM row: the rotor densities include the blade
    count, so per blade thrust = Σ dT/dr·Δr / N along +z and in-plane drag = Σ (dQ/dr)/r·Δr / N toward +x (opposing
    rotation), both placed at the thrust-weighted radius. Annuli are assigned by their centre radius."""
    n = d.planform.blade_count
    r0 = d.connection.hinge_radius_mm + d.connection.face_gap_mm
    els = [e for e in row["elements"] if e["r_mm"] >= r0]
    t = [e["dT_dr_n_per_m"] * e["width_mm"] / 1000.0 for e in els]
    thrust = math.fsum(t) / n
    drag = math.fsum(e["dQ_dr_nm_per_m"] / (e["r_mm"] / 1000.0) * e["width_mm"] / 1000.0 for e in els) / n
    radius = (math.fsum(e["r_mm"] * ti for e, ti in zip(els, t)) / math.fsum(t)) if math.fsum(t) > 0 else \
        float(np.mean([e["r_mm"] for e in els]))
    return {"thrust_n": thrust, "drag_n": drag, "radius_mm": radius}


def max_rpm(feasible, lo=500.0, hi=12000.0, tol=10.0, bracket=False):
    """Largest speed in [lo, hi] for which ``feasible`` holds, assuming it fails above some speed; None if even
    ``lo`` fails. ``bracket``: return (last feasible, first infeasible tested) instead."""
    if not feasible(lo):
        return None
    if feasible(hi):
        return (hi, None) if bracket else hi
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if feasible(mid) else (lo, mid)
    return (lo, hi) if bracket else lo


def envelope_point(d, polars, parts, distal, rpm, J, bounds="error") -> dict:
    """Strength at one speed and advance ratio with the distal's own BEM thrust and drag added to the centrifugal
    load (``loads.deployed``); covered only if the BEM point is usable."""
    from . import loads, strength
    r = run_point(d, polars, rpm, J, bounds=bounds)
    out = {"rpm": rpm, "J": J, "bounds": bounds, "covered": usable(r)}
    if not out["covered"]:
        return {**out, "reason": r.get("failure_kind") or "polar data clamped"}
    aero_d = distal_aero_loads(d, r)
    ld = loads.deployed(distal, d, parts.meta, rpm, aero_d["thrust_n"], aero_d["drag_n"], aero_d["radius_mm"])
    rows = strength.checks(ld, d, parts.meta)
    worst = min(rows, key=lambda x: x["margin"] if x["margin"] is not None else math.inf)
    return {**out, "speed_m_s": r["forward_speed_m_s"], "thrust_n": r["thrust_n"], "power_w": r["power_w"],
            "eta": r.get("eta"), "distal_thrust_n": aero_d["thrust_n"], "distal_drag_n": aero_d["drag_n"],
            "distal_radius_mm": aero_d["radius_mm"], "seated": bool(ld["seated"]), "stop_force_n": ld["stop_force_n"],
            "min_margin": worst["margin"], "governing": worst["key"],
            "ok": bool(ld["seated"] and worst["margin"] is not None and worst["margin"] >= 0.0)}


def operating_envelope(d, polars, parts, distal, advance_ratios=(0.2, 0.25, 0.3), static=True,
                       grid=tuple(range(1000, 9001, 250)), tol=10.0) -> list[dict]:
    """Highest speed per advance ratio at which every single-lug check holds at the safety factor and the distal stays
    seated, with centrifugal plus the distal's BEM aerodynamic loads (fail-closed). Polar coverage is a band (low
    speeds fall below the Reynolds data), so a speed grid is scanned first; the upper edge of the first contiguous
    feasible run is then refined by bisection. The static row uses the clamp diagnostic and is labelled so. Each row
    says what limits it: strength (the governing check), seating, polar coverage or the end of the speed range."""
    out = []
    cases = [(J, "error") for J in advance_ratios] + ([(0.0, "clamp")] if static else [])
    for J, bounds in cases:
        basis = "fail-closed" if bounds == "error" else "clamp diagnostic (not supported)"
        cache = {}

        def point(rpm):
            if rpm not in cache:
                cache[rpm] = envelope_point(d, polars, parts, distal, float(rpm), J, bounds)
            return cache[rpm]

        def feasible(rpm):
            q = point(rpm)
            return q["covered"] and q["ok"]
        covered = [r for r in grid if point(r)["covered"]]
        first = next((i for i, r in enumerate(grid) if feasible(r)), None)
        if first is None:
            q = point(covered[0]) if covered else point(grid[0])
            out.append({"J": J, "basis": basis, "max_rpm": None, "covered_from_rpm": covered[0] if covered else None,
                        "limited_by": "polar coverage" if not covered else ("seating" if not q.get("seated")
                                                                            else q["governing"])})
            continue
        last = first
        while last + 1 < len(grid) and feasible(grid[last + 1]):
            last += 1
        if last + 1 == len(grid):
            top, above = float(grid[last]), None
        else:
            top, hi = max_rpm(feasible, lo=float(grid[last]), hi=float(grid[last + 1]), tol=tol, bracket=True)
            above = point(hi)                              # the infeasible speed the bisection actually tested
        limit = ("speed range end" if above is None else "polar coverage" if not above["covered"] else
                 "seating" if not above.get("seated") else above["governing"])
        at = point(top)
        out.append({"J": J, "basis": basis, "max_rpm": top, "covered_from_rpm": covered[0] if covered else None,
                    "limited_by": limit, **{k: at.get(k) for k in (
                        "speed_m_s", "thrust_n", "power_w", "eta", "distal_thrust_n", "distal_drag_n", "distal_radius_mm",
                        "stop_force_n", "min_margin")}})
    return out


COMPROMISE = {   # blade-shape options at the same joint radius (twist ×0.86 base = the 13×5.5-class reference)
    "reference": {"planform.twist_scale": 0.86},
    "F2": {"planform.twist_scale": 0.86, "planform.hinge_zone_mm": 45.0, "planform.hinge_twist_factor": 0.7},
    "F1": {"planform.twist_scale": 0.86, "planform.hinge_zone_mm": 45.0, "planform.hinge_chord_factor": 0.85,
           "planform.hinge_twist_factor": 0.6},
    "E": None,                                                    # study.E_PARAMS
}
EQUAL_THRUST_POINTS = ((4.0, 3000.0), (6.0, 4000.0), (6.0, 5000.0), (8.0, 5000.0), (8.0, 6000.0), (10.0, 6000.0))


def run_decision(root, folder) -> dict:
    """Decision table for the next design: per blade option the offset each fold travel needs (CAD sweep), the folded
    size, the structural speed limit at its own offset, and the speed and power for equal thrust at equal inflow
    against the reference (fail-closed BEM on the saved printable-section polars)."""
    from . import explore, study
    from .design import default_design, with_changes
    root, folder = Path(root), Path(folder)
    base = with_changes(default_design(root), **{"connection.axial_offset_mm": study.REPORT_OFFSET_MM})
    ds = {k: explore.candidate_design(base, root, study.E_PARAMS if v is None else v) for k, v in COMPROMISE.items()}
    record = json.loads((folder / "polars_printable_section.json").read_text(encoding="utf-8"))
    check_record(root, record)
    polars = {k: schedule(d, families_from_record(d, record)) for k, d in ds.items()}
    eq = equal_thrust(ds, polars, "reference", EQUAL_THRUST_POINTS)
    options = []
    for k, d in ds.items():
        row = study.study_row(k, d)                             # sweep at δ = 6 mm: offsets by travel, seating
        offset = math.ceil(row["req_140_mm"] * 2.0) / 2.0 if "req_140_mm" in row else None
        limit, dims = None, {}
        if offset is not None:
            r = explore.evaluate(with_changes(d, **{"connection.axial_offset_mm": offset}))
            limit = (r.get("governing") or {}).get("rpm_limit")
            if "sweep" in r:
                dims = {x["fold_deg"]: x["envelope_diameter_mm"] for x in study.folded_dimensions(r["parts"].design, r["sweep"])}
        options.append({**row, "offset_for_140_mm": offset, "rpm_limit_sf2": limit,
                        "envelope_110_mm": dims.get(110), "envelope_140_mm": dims.get(140)})
    for r in eq:                                                # structural consequence of the equal-thrust speed
        lim = next((o["rpm_limit_sf2"] for o in options if o["variant"] == r["design"]), None)
        if r.get("status") == "ok" and lim:
            r["rpm_over_limit"] = r["rpm"] / lim
            r["stress_vs_limit"] = (r["rpm"] / lim) ** 2               # centrifugal stresses scale with Ω²
    _csv(folder / "equal_thrust.csv", eq)
    _csv(folder / "compromise_options.csv", options)
    return {"equal_thrust": eq, "options": options}


if __name__ == "__main__":                                    # python -m pyfoldable.prototype.aero <report folder>
    import sys
    run_report(Path.cwd(), Path(sys.argv[1]))
