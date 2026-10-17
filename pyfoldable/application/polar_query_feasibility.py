"""Offline polar-query feasibility map for the fully-open 250 mm baseline.

The map reconstructs kinematic queries from the existing annulus solver. It
does not call a polar provider, publish rotor totals, or treat potential
search endpoints as observed solver queries.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pyfoldable.application.design_analysis import _load
from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.models import AirfoilDefinition
from pyfoldable.core.bem import (
    BEMAnnulusSettings,
    _AIR_GAMMA,
    _AIR_GAS_CONSTANT_J_KG_K,
)
from pyfoldable.core.bem_rotor import (
    BEMRotorElementError,
    BEMRotorSettings,
    _interpolate_station,
    _radial_limits,
    solve_bem_rotor,
)
from pyfoldable.core.polar import PolarInterpolationError, PolarQueryResult
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil
from pyfoldable.core.providers import (
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarProviderCapabilityError,
    ProviderIdentity,
)
from pyfoldable.providers.neuralfoil import _CAPABILITIES as NEURALFOIL_CAPABILITIES
from pyfoldable.providers.xfoil import _build_command_script


SOURCE_DESIGN = "configs/designs/TIP_HINGED_250_CANONICAL.toml"
PIN_DIRECTORY = "reports/retained_pins/two_profile_bem_screening"
PIN_SHA256 = {
    "declaration.json": "feaa6ac2a39147605cfb23b1fd9a516ca95ca1a96a25080bc14eb65e766d5d5c",
    "NACA0012.json": "0b07641a6d49f89d965871edfa1507e2ed237c76080c24e09c55f8c1590819eb",
    "NACA2412.json": "900298c707e56157e2e956b0de90bfa1b3a1984931b0548f70c734ed22499a61",
}
MATCHED_PAIR = ("NACA0012", "NACA2412")
REAL_CAPTURE_CASE = "tests/fixtures/polar_real_qualification/naca0012_re200k_real_v1"
REAL_CAPTURE_FILES = (
    "capture/manifest.json",
    "capture/benchmark.json",
    "capture/results/00-xfoil-subprocess.json",
    "capture/results/01-neuralfoil.json",
    "promotion.json",
    "golden.json",
    "comparison.json",
    "second_capture_manifest.json",
)
ANNULUS_COUNT = 40
ALPHA_STEP_RAD = math.radians(2.0)
SYNTHETIC_SOURCE = "synthetic feasibility trace; not a provider polar"


class PolarQueryFeasibilityError(ValueError):
    """The diagnostic cannot be built without inventing a query or a result."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha_text(value: object) -> str:
    return _sha_bytes(_canonical(value).encode("utf-8"))


def _inputs(airfoil_id: str) -> DesignDraftInputs:
    return DesignDraftInputs(
        diameter="250 mm", hub_radius="18 mm", hinge_radius="100 mm", blade_count=2,
        airfoil_id=airfoil_id, chord_scale=1.0, twist_scale=1.0, preview_fold_angle="0 deg",
        angular_speed="7100 rpm", forward_speed="0 m/s", air_density="1.225 kg/m^3",
        dynamic_viscosity="1.81e-5 Pa*s", temperature="288.15 K", pressure="101325 Pa",
    )


def _load_pins(repository_root: Path) -> dict[str, Any]:
    loaded = {}
    for name, expected in PIN_SHA256.items():
        path = repository_root / PIN_DIRECTORY / name
        payload = path.read_bytes()
        digest = _sha_bytes(payload)
        if digest != expected:
            raise PolarQueryFeasibilityError(f"Retained pin {name} hash does not match.")
        loaded[name] = json.loads(payload.decode("utf-8"))
    return loaded


def _query_state(condition, radius: float, chord: float, twist: float, psi: float) -> dict[str, float]:
    axial = condition.forward_speed_m_s
    tangential = condition.angular_speed_rad_s * radius
    external = math.hypot(axial, tangential)
    wa = 0.5 * axial + 0.5 * external * math.sin(psi)
    wt = 0.5 * tangential + 0.5 * external * math.cos(psi)
    relative = math.hypot(wa, wt)
    phi = math.atan2(wa, wt)
    return {
        "psi_rad": psi,
        "inflow_angle_rad": phi,
        "alpha_rad": twist - phi,
        "reynolds": condition.air_density_kg_m3 * relative * chord / condition.dynamic_viscosity_pa_s,
        "mach": relative / math.sqrt(_AIR_GAMMA * _AIR_GAS_CONSTANT_J_KG_K * condition.temperature_k),
        "relative_speed_m_s": relative,
    }


def _step_grid(lower: float, upper: float, step: float) -> tuple[float, ...]:
    start = math.floor(lower / step + 1.0e-12) * step
    if start > lower:
        start -= step
    end = math.ceil(upper / step - 1.0e-12) * step
    if end < upper:
        end += step
    count = int(round((end - start) / step))
    values = tuple(start + index * step for index in range(count + 1))
    if not values or values[0] > lower or values[-1] < upper:
        raise PolarQueryFeasibilityError("Alpha grid does not cover the requested interval.")
    return values


def _policy() -> dict[str, Any]:
    controls = BEMRotorSettings(annulus_count=ANNULUS_COUNT)
    return {
        **controls.as_mapping(),
        "bounds": "error",
        "solved_pose": "fully_open_zero_offset",
        "forward_speed_m_s": 0.0,
        "rotational_augmentation_kind": controls.annulus_settings.rotational_augmentation.kind,
    }


def build_annulus_query_map(design) -> dict[str, Any]:
    """Map each station-span midpoint without calling the annulus solver."""
    controls = BEMAnnulusSettings()
    if controls.loading_branch != "positive_only":
        raise PolarQueryFeasibilityError("The baseline policy is positive_only.")
    blade = design.blade
    condition = design.operating_conditions[0]
    if condition.forward_speed_m_s != 0.0:
        raise PolarQueryFeasibilityError("This map is for the zero forward-speed baseline.")
    inner, outer, _extended = _radial_limits(blade, "station_span")
    width = (outer - inner) / ANNULUS_COUNT
    rows = []
    for index in range(ANNULUS_COUNT):
        midpoint = inner + (index + 0.5) * width
        station, extrapolated = _interpolate_station(blade, midpoint)
        radius = station.r_over_R * blade.radius_m
        tangential = condition.angular_speed_rad_s * radius
        psi_start = math.atan2(condition.forward_speed_m_s, tangential)
        psi_end = math.pi / 2.0 - controls.angle_tolerance_rad
        start = _query_state(condition, radius, station.chord_m, station.twist_rad, psi_start)
        end = _query_state(condition, radius, station.chord_m, station.twist_rad, psi_end)
        if abs(start["inflow_angle_rad"] - 0.5 * psi_start) > 1.0e-12:
            raise PolarQueryFeasibilityError("Hover inflow angle is not half the QPROP psi.")
        if abs(end["inflow_angle_rad"] - 0.5 * psi_end) > 1.0e-9:
            raise PolarQueryFeasibilityError("Hover terminal inflow angle left the psi/2 identity.")
        rows.append({
            "annulus_index": index,
            "reached_by_genuine_run": False,
            "inner_radius_m": inner + index * width,
            "outer_radius_m": inner + (index + 1) * width,
            "midpoint_radius_m": radius,
            "r_over_R": station.r_over_R,
            "chord_m": station.chord_m,
            "twist_rad": station.twist_rad,
            "geometry_extrapolated": extrapolated,
            "first_no_induction_query": {
                "status": "conditional_on_reaching_this_annulus",
                "observed_solver_query": False,
                **start,
            },
            "potential_bracket_domain": {
                "status": "potential_search_image_not_an_observed_query",
                "psi_start_rad": psi_start,
                "psi_end_rad": psi_end,
                "bracket_samples": controls.bracket_samples,
                "max_iterations": controls.max_iterations,
                "query_count_not_determined_without_a_polar": True,
                "early_termination_possible": True,
                "start": start,
                "end": end,
            },
        })
    return {
        "annulus_count": ANNULUS_COUNT,
        "radial_domain": "station_span",
        "inner_radius_m": inner,
        "outer_radius_m": outer,
        "width_m": width,
        "rows": rows,
    }


def _extent(rows: list[dict[str, Any]], section: str, field: str) -> tuple[float, float]:
    values = [row[section][field] for row in rows]
    return min(values), max(values)


def reconstruct_pr97_rectangle(query_map: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the historical rectangular family from psi endpoints only."""
    endpoints = []
    for row in query_map["rows"]:
        domain = row["potential_bracket_domain"]
        endpoints.append(domain["start"])
        endpoints.append(domain["end"])
    alpha_min = min(item["alpha_rad"] for item in endpoints)
    alpha_max = max(item["alpha_rad"] for item in endpoints)
    reynolds_min = min(item["reynolds"] for item in endpoints)
    reynolds_max = max(item["reynolds"] for item in endpoints)
    mach_min = min(item["mach"] for item in endpoints)
    mach_max = max(item["mach"] for item in endpoints)
    alpha_grid = _step_grid(alpha_min, alpha_max, ALPHA_STEP_RAD)
    return {
        "role": "historical_sufficient_rectangle_for_the_potential_image",
        "observed_solver_queries": False,
        "derivation": (
            "positive_only psi endpoints at each station_span annulus midpoint; "
            "no induction solve and no post-failure expansion"
        ),
        "alpha_rad_min": alpha_min,
        "alpha_rad_max": alpha_max,
        "reynolds_min": reynolds_min,
        "reynolds_max": reynolds_max,
        "mach_min": mach_min,
        "mach_max": mach_max,
        "alpha_rad": list(alpha_grid),
        "reynolds_grid": [reynolds_min, reynolds_max],
        "mach_grid": [0.0, mach_max],
        "mach_zero_is_outside_the_potential_image": mach_min > 0.0,
    }


class _SyntheticFamily:
    """Inert coefficient source that records queries and enforces alpha bounds."""

    def __init__(self, airfoil_id: str, alpha_min: float, alpha_max: float) -> None:
        self.airfoil_id = airfoil_id
        self.scenario_id = "synthetic-feasibility-trace"
        self.alpha_min = alpha_min
        self.alpha_max = alpha_max
        self.queries: list[dict[str, float]] = []

    def query(self, *, alpha_rad: float, reynolds: float, mach: float, bounds: str = "error") -> PolarQueryResult:
        self.queries.append({"alpha_rad": alpha_rad, "reynolds": reynolds, "mach": mach, "bounds": bounds})
        if bounds == "error" and (alpha_rad < self.alpha_min or alpha_rad > self.alpha_max):
            raise PolarInterpolationError(
                f"Requested alpha_rad {alpha_rad:g} is outside [{self.alpha_min:g}, {self.alpha_max:g}]."
            )
        return PolarQueryResult(
            airfoil_id=self.airfoil_id,
            scenario_id=self.scenario_id,
            alpha_rad=alpha_rad,
            reynolds=reynolds,
            mach=mach,
            cl=0.8,
            cd=0.02,
            cm=0.0,
            sources=(SYNTHETIC_SOURCE,),
        )


def synthetic_trace(design, *, alpha_min: float, alpha_max: float, label: str) -> dict[str, Any]:
    """Run the existing rotor solver on an explicitly synthetic polar."""
    family = _SyntheticFamily(design.blade.stations[0].airfoil_id, alpha_min, alpha_max)
    outcome = "completed_without_publishing_totals"
    message = None
    try:
        solve_bem_rotor(
            design.blade,
            design.operating_conditions[0],
            {family.airfoil_id: family},
            settings=BEMRotorSettings(annulus_count=ANNULUS_COUNT),
        )
        annuli_failed_index = None
    except BEMRotorElementError as exc:
        outcome = "stopped_on_existing_bounds_or_convergence_error"
        message = str(exc)
        annuli_failed_index = int(message.split()[1])
    alphas = [item["alpha_rad"] for item in family.queries]
    return {
        "evidence_class": "synthetic_inert_trace",
        "label": label,
        "source": SYNTHETIC_SOURCE,
        "alpha_table_rad": [alpha_min, alpha_max],
        "cl": 0.8,
        "cd": 0.02,
        "outcome": outcome,
        "failure_message": message,
        "failed_annulus_index": annuli_failed_index,
        "query_count": len(family.queries),
        "first_query": family.queries[0] if family.queries else None,
        "min_alpha_rad": min(alphas) if alphas else None,
        "max_alpha_rad": max(alphas) if alphas else None,
        "performance_totals_published": False,
    }


def _real_capture_inventory(repository_root: Path, catalog_coordinate_sha256: str) -> dict[str, Any]:
    case = repository_root / REAL_CAPTURE_CASE
    files = []
    for relative in REAL_CAPTURE_FILES:
        path = case / relative
        payload = path.read_bytes()
        files.append({
            "path": f"{REAL_CAPTURE_CASE}/{relative}",
            "sha256": _sha_bytes(payload),
            "size_bytes": len(payload),
        })
    golden = json.loads((case / "golden.json").read_text(encoding="utf-8"))
    request = golden["request"]
    coordinates = tuple(tuple(point) for point in request["airfoil"]["coordinates"])
    airfoil = AirfoilDefinition(request["airfoil"]["id"], request["airfoil"]["source"], coordinates)
    coordinate_sha256 = airfoil_coordinate_sha256(airfoil)
    alphas = [float(value) for value in request["alpha_rad"]]
    xfoil = json.loads((case / "capture/results/00-xfoil-subprocess.json").read_text(encoding="utf-8"))
    neuralfoil = json.loads((case / "capture/results/01-neuralfoil.json").read_text(encoding="utf-8"))
    raw_manifest = json.loads((case / "capture/manifest.json").read_text(encoding="utf-8"))
    promotion = json.loads((case / "promotion.json").read_text(encoding="utf-8"))
    return {
        "classification": "existing_but_coverage_incompatible",
        "synthetic": False,
        "active_design_polar_bundle": False,
        "case_name": "naca0012_re200k_real_v1",
        "files": files,
        "coordinate_sha256": coordinate_sha256,
        "coordinate_source": request["airfoil"]["source"],
        "matches_baseline_catalog_coordinate": coordinate_sha256 == catalog_coordinate_sha256,
        "baseline_catalog_coordinate_sha256": catalog_coordinate_sha256,
        "coverage": {
            "alpha_rad_min": min(alphas),
            "alpha_rad_max": max(alphas),
            "alpha_deg_min": math.degrees(min(alphas)),
            "alpha_deg_max": math.degrees(max(alphas)),
            "point_count": len(alphas),
            "reynolds": request["reynolds"],
            "mach": request["mach"],
        },
        "raw_xfoil_capture": {
            "kind": xfoil["kind"],
            "provider": "xfoil-subprocess",
            "adapter_version": "2",
            "backend_version": "6.99",
            "returncode": xfoil["metadata"]["returncode"],
            "point_count": xfoil["metadata"]["polar_row_count"],
            "complete": xfoil["complete"],
            "statuses": sorted({point["status"] for point in xfoil["points"]}),
        },
        "raw_neuralfoil_capture": {
            "kind": neuralfoil["kind"],
            "provider": "neuralfoil",
            "adapter_version": "1",
            "backend_version": "0.3.3",
            "model_size": neuralfoil["metadata"]["model_size"],
            "point_count": len(neuralfoil["points"]),
            "complete": neuralfoil["complete"],
            "minimum_confidence": min(point["confidence"] for point in neuralfoil["points"]),
        },
        "raw_capture_status": {
            "review_state": raw_manifest["review_state"],
            "promotion_allowed": raw_manifest["promotion_allowed"],
            "source_revision": raw_manifest["source_revision"],
        },
        "later_promotion_status": {
            "review_state": promotion["review_state"],
            "promotion_allowed": promotion["promotion_allowed"],
            "physical_review_decision": promotion["physical_review"]["decision"],
            "source_revision": promotion["source_revision"],
        },
    }


def _angle_distinction(query_map: dict[str, Any], rectangle: dict[str, Any]) -> dict[str, Any]:
    grid = rectangle["alpha_rad"]
    first = query_map["rows"][0]["first_no_induction_query"]["alpha_rad"]
    return {
        "padded_grid_low_deg": math.degrees(grid[0]),
        "padded_grid_high_deg": math.degrees(grid[-1]),
        "image_minimum_deg": math.degrees(rectangle["alpha_rad_min"]),
        "image_maximum_deg": math.degrees(rectangle["alpha_rad_max"]),
        "conditional_first_query_deg": math.degrees(first),
        "descending_start_executes_the_conditional_first_query": False,
        "cartesian_corner": {
            "alpha_rad": grid[0],
            "reynolds": rectangle["reynolds_grid"][0],
            "mach": rectangle["mach_grid"][0],
            "is_a_correlated_annulus_state": False,
            "reason": "Mach 0 combined with an alpha/Reynolds endpoint is a grid corner, not one annulus state.",
        },
    }


def _provider_audit(
    repository_root: Path,
    declaration: dict[str, Any],
    failures: dict[str, Any],
    rectangle: dict[str, Any],
    query_map: dict[str, Any],
    catalog_coordinate_sha256: str,
) -> dict[str, Any]:
    foil = load_project_airfoil("NACA0012")
    request = PolarGenerationRequest(
        airfoil=foil,
        alpha_rad=(0.0, 0.1),
        reynolds=float(rectangle["reynolds_min"]),
        mach=float(rectangle["mach_max"]),
        scenario_id="neuralfoil-capability-check",
    )
    neuralfoil_rejection = None
    try:
        request.validate_capabilities(NEURALFOIL_CAPABILITIES)
    except PolarProviderCapabilityError as exc:
        neuralfoil_rejection = str(exc)
    if neuralfoil_rejection is None or NEURALFOIL_CAPABILITIES.supports_mach:
        raise PolarQueryFeasibilityError("NeuralFoil Mach capability did not fail closed.")
    return {
        "existing_real_captures": _real_capture_inventory(repository_root, catalog_coordinate_sha256),
        "angle_distinction": _angle_distinction(query_map, rectangle),
        "retained_bundle_note": (
            "The Re 200000 NACA0012 captures are real provider outputs with a later "
            "promotion record. Their alpha, Reynolds, and Mach coverage does not contain "
            "this baseline. They are not an active-design polar bundle."
        ),
        "historical_failures": {
            airfoil_id: {
                "status": document["status"],
                "bem_calls": document["bem_calls"],
                "coordinate_sha256": document["coordinate_sha256"],
                "failure": document["failure"],
                "polar_content_sha256": document["polar_content_sha256"],
            }
            for airfoil_id, document in failures.items()
        },
        "xfoil_request_order": {
            "cell_order": "Mach-major, Reynolds-minor",
            "historical_first_cell": "Mach 0, Reynolds minimum, alpha ascending from the most negative grid angle",
            "adapter_initialization": (
                "PLOP, G F, LOAD, PANE when repanel is true, OPER, TYPE 1, VISC, MACH, "
                "VPAR N, XTR, ITER, PACC, then one ALFA command per requested angle in "
                "the original order. The adapter does not send INIT."
            ),
            "alpha_order_is_part_of_the_request": True,
        },
        "observed_failures": [
            "NACA0012 cell 1/4 at Mach 0 and Reynolds 26030.6 was rejected. Usable fraction 0.756757 < 1. Point indices 0 through 8, angles -40 deg through -24 deg, are not_converged. No BEM call was made.",
            "NACA2412 cell 1/4 at the same Mach and Reynolds timed out after 90 s. The retained record has no per-angle disposition. No BEM call was made.",
        ],
        "hypotheses_not_observed": [
            "The XFOIL primer says a viscous Newton step starts from the previous solution and that a large alpha change can fail. That mechanism is consistent with starting at -40 deg, but the retained ledger does not isolate order from angle, Reynolds, or Mach.",
            "NACA2412's timeout is not evidence that a particular angle failed.",
            "A synthetic constant-coefficient solve that stops before the terminal psi does not locate the queries a real polar would issue.",
        ],
        "xfoil_primary_documentation": {
            "source": "https://web.mit.edu/drela/Public/web/xfoil/xfoil_doc.txt",
            "scope": "Subsonic isolated airfoils, viscous analysis with limited trailing-edge separation and a Karman-Tsien compressibility correction.",
            "numerical_behavior": "Viscous analysis can fail for excessive angle of attack or Reynolds number that is too low. Newton iteration resumes from the last solution; the primer recommends sequencing alpha gradually.",
            "physical_applicability": "The primer does not qualify this rotor, these coordinates, or the retained failed angles.",
        },
        "neuralfoil": {
            "adapter_supports_mach": NEURALFOIL_CAPABILITIES.supports_mach,
            "capability_rejection": neuralfoil_rejection,
            "primary_documentation": (
                "NeuralFoil 0.3.3 README: compressible aerodynamics are described as an "
                "AeroSandbox extension, not as the standalone coordinate API used by this adapter."
            ),
            "replacement_for_this_baseline": False,
            "reason": (
                "The potential Mach image is above zero, and the current adapter rejects "
                "a nonzero Mach request before evaluation."
            ),
        },
        "declaration_reference": declaration["shared_declaration_sha256"],
    }


def _experiment(
    query_map: dict[str, Any],
    rectangle: dict[str, Any],
    bindings: dict[str, dict[str, str]],
) -> dict[str, Any]:
    rows = query_map["rows"]
    first = [row["first_no_induction_query"] for row in rows]
    alpha_min = min(item["alpha_rad"] for item in first)
    alpha_max = max(item["alpha_rad"] for item in first)
    descending = list(reversed(rectangle["alpha_rad"]))
    mach_grid = [rectangle["mach_min"], rectangle["mach_max"]]
    reynolds_grid = [rectangle["reynolds_min"], rectangle["reynolds_max"]]
    requests = [
        {
            "profile": airfoil_id,
            "coordinate_sha256": bindings[airfoil_id]["coordinate_sha256"],
            "mach": mach,
            "reynolds": reynolds,
            "alpha_order": "descending_from_highest_positive_grid_angle",
            "alpha_count": len(descending),
            "alpha_rad_first": descending[0],
            "alpha_rad_last": descending[-1],
        }
        for airfoil_id in MATCHED_PAIR
        for mach in mach_grid
        for reynolds in reynolds_grid
    ]
    return {
        "experiment_id": "xfoil_positive_first_potential_image_probe_v1",
        "executed_by_this_diagnostic": False,
        "bem_calls": 0,
        "profiles": list(MATCHED_PAIR),
        "five_profile_workflow_unchanged": True,
        "provider": {
            "name": "xfoil-subprocess",
            "adapter_version": "2",
            "backend_name": "XFOIL",
            "backend_version": "6.99",
            "source_url": "https://web.mit.edu/drela/Public/web/xfoil/xfoil6.99.tgz",
            "repanel": True,
            "n_crit": 9.0,
            "xtr_upper": 1.0,
            "xtr_lower": 1.0,
            "max_iterations": 80,
            "initialization": (
                "Existing adapter script only: PLOP, G F, LOAD, PANE, OPER, TYPE 1, "
                "VISC, MACH, VPAR N 9, XTR 1 1, ITER 80, PACC, then ALFA in descending "
                "alpha order. No INIT command and no replay of the ascending -40 deg request."
            ),
        },
        "alpha_rad_descending": descending,
        "mach_grid": mach_grid,
        "reynolds_grid": reynolds_grid,
        "first_query_alpha_rad": [alpha_min, alpha_max],
        "requests": requests,
        "call_limit": len(requests),
        "attempt_limit_per_call": 1,
        "timeout_s": 90.0,
        "retry": False,
        "serial_order": "NACA0012 then NACA2412; within a profile, Mach ascending and Reynolds ascending.",
        "retained_raw_outputs": [
            "command script",
            "process stdout and stderr",
            "raw polar file",
            "per-angle status ledger",
            "airfoil coordinate sha256",
            "executable sha256",
        ],
        "acceptance": (
            "Every requested point is usable and the cell usable fraction is 1. "
            "No point is discarded, clamped, or replaced. Coordinate hashes match the catalog."
        ),
        "cell_execution": (
            "run_declared_probe is the enforcement point. It launches at most eight "
            "declared cells, one attempt each, and stops before the next cell after "
            "a failed cell. The adapter still submits each launched cell as one complete "
            "script and does not interrupt that script at the first bad angle. A returned "
            "result is admitted only when its canonical request and provider identity match "
            "the launched cell and the declared provider, including retained capture request "
            "identity. A manifest alone does not enforce these limits, and this diagnostic "
            "does not launch the probe."
        ),
        "capture": (
            "XfoilProvider.generate(capture_dir=...) writes raw stdout, stderr, and polar "
            "bytes before temporary-directory cleanup, including timeout, decode failure, "
            "and exception paths. Replacement-decoded diagnostic text is not those raw bytes. "
            "Executable identity is the file hash immediately before and after the subprocess "
            "call; a missing or changed hash blocks evidence readiness even when the parsed "
            "output is usable. Declared source and compiler flags remain an unverified build "
            "requirement. Omitting capture_dir preserves the default provider result."
        ),
        "stop_conditions": [
            "run_declared_probe stops before the next cell after not_converged, timeout, nonzero exit, malformed output, undecodable output, missing evidence, executable mismatch, persistence failure, or an unexpected exception.",
            "A partial ledger does not authorize continuation.",
            "Do not retry, change ITER, send INIT, clamp, substitute coefficients, or start a BEM call.",
            "The manifest does not launch cells and does not enforce the stop.",
        ],
        "can_establish": (
            "Whether this declared eight-cell grid, descending order, kinematic Mach and "
            "Reynolds endpoints, and one-script-per-cell execution produce a complete usable ledger."
        ),
        "cannot_establish": (
            "A genuine two-profile BEM comparison. A failure establishes failure of this "
            "grid, sequencing, and execution configuration only. It does not establish "
            "infeasibility of the correlated kinematic image, the actual solver path, "
            "either profile, or the project. Differences from PR #97 cannot be attributed "
            "only to sequencing because the Mach grid also changes. Starting at the padded "
            "+32 deg grid angle does not execute the +30.65875 deg conditional first query."
        ),
        "physical_qualification": False,
    }


def build_polar_query_feasibility(repository_root: str | Path) -> dict[str, Any]:
    """Build the diagnostic from the canonical design and the retained PR #97 pins."""
    root = Path(repository_root)
    pins = _load_pins(root)
    declaration = pins["declaration.json"]
    failures = {"NACA0012": pins["NACA0012.json"], "NACA2412": pins["NACA2412.json"]}
    source = root / SOURCE_DESIGN
    source_sha = _sha_bytes(source.read_bytes())
    if source_sha != declaration["source_design"]["sha256"]:
        raise PolarQueryFeasibilityError("Canonical design hash does not match the retained declaration.")
    bindings = {}
    designs = {}
    for airfoil_id in MATCHED_PAIR:
        foil = load_project_airfoil(airfoil_id)
        draft = build_design_draft(source, _inputs(airfoil_id), airfoil_definition=foil)
        design, angle = _load(draft)
        if abs(angle) > 1.0e-12:
            raise PolarQueryFeasibilityError("The baseline preview angle is not fully open.")
        bindings[airfoil_id] = {
            "draft_sha256": draft.draft_sha256,
            "coordinate_sha256": airfoil_coordinate_sha256(foil),
        }
        designs[airfoil_id] = design
        if bindings[airfoil_id]["draft_sha256"] != failures[airfoil_id]["draft_sha256"]:
            raise PolarQueryFeasibilityError(f"{airfoil_id} draft hash does not match the retained failure.")
        if bindings[airfoil_id]["coordinate_sha256"] != failures[airfoil_id]["coordinate_sha256"]:
            raise PolarQueryFeasibilityError(f"{airfoil_id} coordinate hash does not match the retained failure.")
    query_map = build_annulus_query_map(designs["NACA2412"])
    other = build_annulus_query_map(designs["NACA0012"])
    if _canonical(query_map) != _canonical(other):
        raise PolarQueryFeasibilityError("The matched pair does not share one kinematic query map.")
    rectangle = reconstruct_pr97_rectangle(query_map)
    historical = declaration["query_envelope"]
    for key in ("alpha_rad", "reynolds_grid", "mach_grid", "alpha_rad_min", "alpha_rad_max", "reynolds_min", "reynolds_max", "mach_min", "mach_max"):
        if rectangle[key] != historical[key]:
            raise PolarQueryFeasibilityError(f"Reconstructed rectangle field {key} does not match the retained declaration.")
    terminal_alpha = min(row["potential_bracket_domain"]["end"]["alpha_rad"] for row in query_map["rows"])
    wide = synthetic_trace(
        designs["NACA2412"], alpha_min=-2.0, alpha_max=1.2,
        label="wide_constant_coefficients_can_terminate_before_the_terminal_psi",
    )
    positive_gap = synthetic_trace(
        designs["NACA2412"], alpha_min=math.radians(-40.0), alpha_max=math.radians(10.0),
        label="negative_angles_without_the_first_positive_query",
    )
    if wide["min_alpha_rad"] is None or wide["min_alpha_rad"] <= terminal_alpha:
        raise PolarQueryFeasibilityError("Synthetic wide trace did not stay above the potential terminal alpha.")
    if positive_gap["failed_annulus_index"] != 0 or positive_gap["query_count"] != 1:
        raise PolarQueryFeasibilityError("The positive-alpha gap did not stop on the first query.")
    policy = _policy()
    manifest = _experiment(query_map, rectangle, bindings)
    report = {
        "schema_version": 1,
        "artifact_class": "polar_query_feasibility_diagnostic",
        "physical_qualification": False,
        "qualified_winner": None,
        "performance_totals_published": False,
        "genuine_bem_comparison": "UNESTABLISHED",
        "genuine_query_coverage": "unavailable",
        "software_workflow_baseline": {
            "pr": 103,
            "head": "fc545b1584d679951fd28db0767cd71c790a7b06",
            "role": "software-workflow baseline; Draft and unmerged; not a numerical comparison",
        },
        "historical_inputs": {
            "study_id": declaration["study_id"],
            "shared_declaration_sha256": declaration["shared_declaration_sha256"],
            "geometry_sha256": declaration["geometry_sha256"],
            "operating_condition_sha256": declaration["operating_condition_sha256"],
            "pin_sha256": dict(PIN_SHA256),
            "bem_calls": 0,
        },
        "baseline": {
            "source_design_sha256": source_sha,
            "profiles": bindings,
            "catalog_profile_ids": list(PROJECT_AIRFOIL_IDS),
            "solver_policy": policy,
            "policy_sha256": _sha_text(policy),
        },
        "query_map": query_map,
        "pr97_rectangle": rectangle,
        "synthetic_traces": [wide, positive_gap],
        "provider_audit": _provider_audit(
            root, declaration, failures, rectangle, query_map,
            bindings["NACA0012"]["coordinate_sha256"],
        ),
        "recommended_experiment": manifest,
    }
    return report


def declared_probe_requests(
    experiment: dict[str, Any],
    airfoils: dict[str, AirfoilDefinition],
) -> tuple[PolarGenerationRequest, ...]:
    """Build the eight declared cells without launching a solver."""
    if experiment.get("experiment_id") != "xfoil_positive_first_potential_image_probe_v1":
        raise PolarQueryFeasibilityError(
            "run_declared_probe only builds xfoil_positive_first_potential_image_probe_v1."
        )
    if experiment.get("bem_calls") != 0:
        raise PolarQueryFeasibilityError("The declared probe cannot include a BEM call.")
    if experiment.get("retry") is not False or experiment.get("attempt_limit_per_call") != 1:
        raise PolarQueryFeasibilityError("The declared probe allows one attempt per cell and no retry.")
    if experiment.get("timeout_s") != 90.0:
        raise PolarQueryFeasibilityError("The declared probe timeout is 90 seconds.")
    raw_requests = experiment.get("requests")
    if experiment.get("call_limit") != 8 or not isinstance(raw_requests, list) or len(raw_requests) != 8:
        raise PolarQueryFeasibilityError("The declared probe launches at most eight cells.")
    alphas = tuple(experiment["alpha_rad_descending"])
    if len(alphas) != 37 or any(alphas[index] <= alphas[index + 1] for index in range(36)):
        raise PolarQueryFeasibilityError("The declared probe uses 37 strictly descending angles.")
    provider = experiment["provider"]
    expected = [
        (profile, mach, reynolds)
        for profile in ("NACA0012", "NACA2412")
        for mach in experiment["mach_grid"]
        for reynolds in experiment["reynolds_grid"]
    ]
    actual = [(cell["profile"], cell["mach"], cell["reynolds"]) for cell in raw_requests]
    if actual != expected:
        raise PolarQueryFeasibilityError("Declared cell order is not the retained serial order.")
    requests: list[PolarGenerationRequest] = []
    for cell in raw_requests:
        if cell["mach"] <= 0.0:
            raise PolarQueryFeasibilityError("The declared probe does not request Mach 0.")
        try:
            airfoil = airfoils[cell["profile"]]
        except KeyError as error:
            raise PolarQueryFeasibilityError(
                f"Probe airfoil {cell['profile']} was not supplied."
            ) from error
        if airfoil_coordinate_sha256(airfoil) != cell["coordinate_sha256"]:
            raise PolarQueryFeasibilityError("Probe airfoil coordinates do not match the declared cell.")
        if cell["alpha_count"] != 37 or cell["alpha_rad_first"] != alphas[0] or cell["alpha_rad_last"] != alphas[-1]:
            raise PolarQueryFeasibilityError("A declared cell does not use the retained descending angle list.")
        request = PolarGenerationRequest(
            airfoil=airfoil,
            alpha_rad=alphas,
            reynolds=cell["reynolds"],
            mach=cell["mach"],
            n_crit=provider["n_crit"],
            xtr_upper=provider["xtr_upper"],
            xtr_lower=provider["xtr_lower"],
            max_iterations=provider["max_iterations"],
            timeout_s=experiment["timeout_s"],
            scenario_id=experiment["experiment_id"],
            options={"repanel": provider["repanel"]},
        )
        script = _build_command_script(request, {"repanel": bool(provider["repanel"])})
        if any(line.strip().upper() == "INIT" or line.strip().upper().startswith("INIT ") for line in script.splitlines()):
            raise PolarQueryFeasibilityError("The declared probe script contains INIT.")
        if sum(line.startswith("ALFA ") for line in script.splitlines()) != 37:
            raise PolarQueryFeasibilityError("The declared probe script does not contain 37 angles.")
        requests.append(request)
    return tuple(requests)


def _declared_provider(experiment: dict[str, Any]) -> ProviderIdentity:
    provider = experiment["provider"]
    return ProviderIdentity(
        name=str(provider["name"]),
        adapter_version=str(provider["adapter_version"]),
        backend_name=str(provider["backend_name"]),
        backend_version=str(provider["backend_version"]),
    )


def _bind_returned_result(
    launched: PolarGenerationRequest,
    result: PolarGenerationResult,
    declared: ProviderIdentity,
) -> dict[str, Any]:
    """Compare the launched cell with the returned result, not a self-derived cache key."""
    attempted = launched.cache_key(declared)
    returned = result.request.cache_key(declared)
    capture_key = result.metadata.get("capture_request_sha256")
    if not isinstance(capture_key, str):
        capture_key = None
    mismatch = None
    if result.provider != declared:
        mismatch = "Returned provider identity does not match the declared provider."
    elif returned != attempted:
        mismatch = "Returned request identity does not match the launched request."
    elif result.metadata.get("capture_evidence_ready") is True and capture_key != attempted:
        mismatch = "Retained capture request identity does not match the launched request."
    return {
        "attempted_request_sha256": attempted,
        "returned_request_sha256": returned,
        "attempted_profile": launched.airfoil.id,
        "returned_profile": result.request.airfoil.id,
        "returned_provider": result.provider.as_mapping(),
        "capture_request_sha256": capture_key,
        "identity_mismatch": mismatch,
    }


def run_declared_probe(
    experiment: dict[str, Any],
    airfoils: dict[str, AirfoilDefinition],
    launch: Callable[[PolarGenerationRequest], PolarGenerationResult],
) -> dict[str, Any]:
    """Launch the declared cells through an injected provider seam and stop on failure.

    The diagnostic builder does not call this function. A returned stop reason
    means no later cell was launched. Partial output does not authorize another cell.
    """
    requests = declared_probe_requests(experiment, airfoils)
    declared = _declared_provider(experiment)
    cells: list[dict[str, Any]] = []
    stop_reason: str | None = None
    for index, request in enumerate(requests):
        if len(cells) >= 8:
            stop_reason = "stopped at the eight-launch ceiling"
            break
        try:
            result = launch(request)
        except Exception as error:
            cells.append(_probe_cell(index, request, result=None, error=error, declared=declared))
            stop_reason = "launch failed before a complete evidence-ready cell"
            break
        if not isinstance(result, PolarGenerationResult):
            cells.append(
                _probe_cell(
                    index,
                    request,
                    result=None,
                    error=TypeError("launch did not return a polar result"),
                    declared=declared,
                )
            )
            stop_reason = "launch did not return a polar result"
            break
        binding = _bind_returned_result(request, result, declared)
        cells.append(_probe_cell(index, request, result=result, error=None, declared=declared, binding=binding))
        evidence_ready = (
            binding["identity_mismatch"] is None
            and result.complete
            and result.metadata.get("capture_evidence_ready") is True
        )
        if binding["identity_mismatch"]:
            stop_reason = "returned result does not match the launched request"
            break
        if not evidence_ready:
            stop_reason = "partial or evidence-incomplete cell does not authorize continuation"
            break
    return {
        "experiment_id": experiment["experiment_id"],
        "launch_count": len(cells),
        "bem_calls": 0,
        "bem_accounting": (
            "This driver does not call the rotor solver. bem_calls counts driver calls only "
            "and does not audit work hidden inside the injected launch."
        ),
        "timeout_accounting": (
            "Each launched request carries timeout_s 90. This driver does not start a second "
            "clock; XfoilProvider.generate enforces that timeout on its subprocess."
        ),
        "retries": 0,
        "attempt_limit_per_call": 1,
        "timeout_s": 90.0,
        "alpha_count": 37,
        "stop_reason": stop_reason,
        "manifest_enforces_execution": False,
        "cells": cells,
    }


def _probe_cell(
    index: int,
    request: PolarGenerationRequest,
    *,
    result: PolarGenerationResult | None,
    error: BaseException | None,
    declared: ProviderIdentity,
    binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    binding = binding or {}
    mismatch = binding.get("identity_mismatch")
    return {
        "index": index,
        "profile": request.airfoil.id,
        "mach": request.mach,
        "reynolds": request.reynolds,
        "timeout_s": request.timeout_s,
        "alpha_count": len(request.alpha_rad),
        "complete": None if result is None else result.complete,
        "evidence_ready": bool(
            result is not None
            and mismatch is None
            and result.metadata.get("capture_evidence_ready") is True
        ),
        "attempted_request_sha256": binding.get("attempted_request_sha256", request.cache_key(declared)),
        "returned_request_sha256": binding.get("returned_request_sha256"),
        "attempted_profile": binding.get("attempted_profile", request.airfoil.id),
        "returned_profile": binding.get("returned_profile"),
        "returned_provider": binding.get("returned_provider"),
        "capture_request_sha256": binding.get("capture_request_sha256"),
        "identity_mismatch": mismatch,
        "error_type": None if error is None else type(error).__name__,
        "error": None if error is None else str(error),
    }


def render_polar_query_feasibility(report: dict[str, Any]) -> str:
    """Render the cause map and the single recommended experiment."""
    rectangle = report["pr97_rectangle"]
    rows = report["query_map"]["rows"]
    first = rows[0]["first_no_induction_query"]
    last = rows[-1]["first_no_induction_query"]
    terminal = min(row["potential_bracket_domain"]["end"]["alpha_rad"] for row in rows)
    wide, gap = report["synthetic_traces"]
    experiment = report["recommended_experiment"]
    lines = [
        "# Polar-query feasibility",
        "",
        "This is an offline diagnostic. It is not a BEM comparison and not a qualification.",
        "physical_qualification: false",
        "Genuine query coverage: unavailable",
        "Genuine two-profile numerical comparison: UNESTABLISHED",
        "",
        "## Cause map",
        "",
        "The unchanged baseline is the 250 mm, 7100 rpm, fully-open, zero-offset rotor, "
        "40 station-span annuli, bounds error, and the default positive-only annulus policy.",
        "For this hover condition the inflow angle is half the QPROP psi, so alpha decreases "
        "as psi increases and Reynolds and Mach decrease along the same interval.",
        "",
        f"Conditional first query at annulus 0: alpha {first['alpha_rad']:.12g} rad, "
        f"Reynolds {first['reynolds']:.12g}, Mach {first['mach']:.12g}. "
        "It is issued only if the solver reaches that annulus. It is not an observed genuine query.",
        f"Conditional first query at annulus 39: alpha {last['alpha_rad']:.12g} rad, "
        f"Reynolds {last['reynolds']:.12g}, Mach {last['mach']:.12g}.",
        f"Potential terminal alpha, the far psi endpoint and not an observed query: {terminal:.12g} rad.",
        f"PR #97 rectangle reconstructed from those endpoints: alpha {rectangle['alpha_rad_min']:.12g} "
        f"to {rectangle['alpha_rad_max']:.12g} rad, Reynolds {rectangle['reynolds_min']:.12g} to "
        f"{rectangle['reynolds_max']:.12g}, Mach image {rectangle['mach_min']:.12g} to "
        f"{rectangle['mach_max']:.12g}. Its Mach grid also includes 0, which is outside that image. "
        f"Alpha samples: {len(rectangle['alpha_rad'])}.",
        "",
        "PR #97 retained two observed provider failures and zero BEM calls. NACA0012, Mach 0, "
        "Reynolds 26030.6: usable fraction 0.756757, angles -40 deg through -24 deg not_converged. "
        "NACA2412, same cell: 90 s timeout and no per-angle disposition. Those angles sit at the "
        "negative end of the rectangle. They are not the conditional first query, which is about +30.7 deg "
        "at annulus 0.",
        "",
        f"Synthetic wide constant-coefficient trace: {wide['query_count']} queries, minimum alpha "
        f"{wide['min_alpha_rad']:.12g} rad, totals withheld. The trace stopped above the potential "
        "terminal alpha. Synthetic coverage of -40 deg through +10 deg and not the first positive "
        f"query: failed at annulus {gap['failed_annulus_index']} after {gap['query_count']} query. "
        "A table that covers those negative angles and stops at +10 deg still fails on the "
        "conditional first query. That does not make the kinematic image, either profile, "
        "or the project infeasible.",
        "",
        "The retained NACA0012 Re 200000 captures are real XFOIL and NeuralFoil outputs at "
        "about -6 deg to +10 deg and Mach 0. Raw capture review is separate from the later "
        "promotion record. That coverage is incompatible with this baseline and is not an "
        "active-design bundle.",
        "",
        "The current NeuralFoil adapter rejects nonzero Mach. Its author documents compressible "
        "corrections as an AeroSandbox extension. It is not a replacement for this Mach image.",
        "",
        "## Recommended experiment",
        "",
        "The historical rectangle pads the image extrema to -40 deg and +32 deg. "
        "The image extrema are about -39.72917 deg and +30.65875 deg. "
        "A Mach 0 corner is not a correlated annulus state. "
        "Starting at +32 deg does not execute the +30.65875 deg conditional first query.",
        "",
        f"`{experiment['experiment_id']}` is not executed here. The driver `run_declared_probe` "
        f"enforces {experiment['call_limit']} XFOIL cells, 37 descending angles, one 90 s attempt, "
        "no retry, no INIT, and no BEM call. The adapter submits each launched cell as one script "
        "and does not interrupt that script at the first bad angle. The driver stops before the "
        "next cell after a failed, partial, or misattributed cell. Admission requires the "
        "returned request and provider to match the launched cell and the declared provider. "
        "A manifest alone does not enforce that stop; "
        "earlier text that attributed the stop to the adapter overstated what the manifest did. "
        "Mach 0 is not requested, so a difference from PR #97 is not evidence about sequencing alone.",
        "",
        "### Can establish",
        "",
        experiment["can_establish"],
        "",
        "### Cannot establish",
        "",
        experiment["cannot_establish"],
        "",
    ]
    return "\n".join(lines)
