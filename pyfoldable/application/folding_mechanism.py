"""UI-independent fold-mechanism geometry audit and screening fixture views."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from pyfoldable.dynamics.hinge_moments import compute_hinge_moments
from pyfoldable.models import load_config


MECHANISM_CLASSIFICATION = "kinematic_screening_only"
PHYSICS_FIXTURE_CLASSIFICATION = "software_fixture_screening_only"
V02_FIXTURE_SHA256 = "bc03ba4eb56a36206b39961a538eacc48a0886565d5b3d6fa0ecaaaebc582c0a"
MAX_FIXTURE_RPM = 12_000.0


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


@dataclass(frozen=True)
class MechanismGeometryInputs:
    """SI-bound dimensions for one planar rigid-tip hinge audit."""

    diameter_m: float
    hub_radius_m: float
    hinge_radius_m: float
    fold_angle_deg: float
    stowed_requirement_m: float

    def __post_init__(self) -> None:
        diameter = _finite("diameter_m", self.diameter_m)
        hub = _finite("hub_radius_m", self.hub_radius_m)
        hinge = _finite("hinge_radius_m", self.hinge_radius_m)
        angle = _finite("fold_angle_deg", self.fold_angle_deg)
        requirement = _finite("stowed_requirement_m", self.stowed_requirement_m)
        radius = diameter / 2.0
        if diameter <= 0.0:
            raise ValueError("diameter_m must be greater than zero.")
        if not 0.0 < hub < hinge < radius:
            raise ValueError(
                "hub_radius_m and hinge_radius_m must satisfy 0 < hub < hinge < radius."
            )
        if not -180.0 <= angle <= 0.0:
            raise ValueError("fold_angle_deg must lie between -180 and 0 degrees.")
        if requirement <= 0.0:
            raise ValueError("stowed_requirement_m must be greater than zero.")


@dataclass(frozen=True)
class MechanismGeometryAudit:
    """Exact planar kinematics plus explicit dimension-compatibility findings."""

    diameter_m: float
    hub_radius_m: float
    hinge_radius_m: float
    tip_segment_length_m: float
    fold_angle_deg: float
    fold_progress_01: float
    tip_center_x_m: float
    tip_center_y_m: float
    projected_effective_diameter_m: float
    centerline_envelope_diameter_m: float
    minimum_centerline_envelope_diameter_m: float
    collision_free_minimum_envelope_diameter_m: float
    hub_centerline_clearance_m: float
    full_stow_path_hub_clearance_m: float
    stowed_requirement_m: float
    stowed_requirement_margin_m: float
    current_requirement_margin_m: float
    minimum_requirement_reachable: bool
    current_envelope_requirement_met: bool
    root_surface_gap_m: float
    tip_surface_gap_m: float
    hinge_station_covered: bool
    station_span_complete: bool
    screening_checks_passed: bool
    compatibility_reasons: tuple[str, ...]
    classification: str = MECHANISM_CLASSIFICATION
    physical_qualification: bool = False


def _origin_to_segment_distance(
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    vx = end[0] - start[0]
    vy = end[1] - start[1]
    length_squared = vx * vx + vy * vy
    if length_squared <= 0.0:
        return math.hypot(*start)
    projection = -(start[0] * vx + start[1] * vy) / length_squared
    fraction = max(0.0, min(1.0, projection))
    return math.hypot(start[0] + fraction * vx, start[1] + fraction * vy)


def _collision_free_minimum_envelope_radius(
    *,
    hinge_radius_m: float,
    tip_length_m: float,
    hub_radius_m: float,
) -> float:
    """Return the smallest centerline envelope before first hub contact."""
    full_fold_tip = abs(hinge_radius_m - tip_length_m)
    full_fold_clearance = (
        max(0.0, hinge_radius_m - tip_length_m) - hub_radius_m
    )
    if full_fold_clearance >= 0.0:
        return max(hinge_radius_m, full_fold_tip)

    tangent_length = math.sqrt(
        max(0.0, hinge_radius_m**2 - hub_radius_m**2)
    )
    if tip_length_m >= tangent_length:
        contact_angle = -math.pi + math.asin(hub_radius_m / hinge_radius_m)
    else:
        cosine = (
            hub_radius_m**2 - hinge_radius_m**2 - tip_length_m**2
        ) / (2.0 * hinge_radius_m * tip_length_m)
        contact_angle = -math.acos(max(-1.0, min(1.0, cosine)))
    tip_x = hinge_radius_m + tip_length_m * math.cos(contact_angle)
    tip_y = tip_length_m * math.sin(contact_angle)
    return max(hinge_radius_m, math.hypot(tip_x, tip_y))


def build_mechanism_geometry_audit(
    inputs: MechanismGeometryInputs,
    station_r_over_r: Sequence[float],
) -> MechanismGeometryAudit:
    """Audit entered dimensions without inventing CAD, loads, or structural results."""
    if not isinstance(inputs, MechanismGeometryInputs):
        raise TypeError("inputs must be MechanismGeometryInputs.")
    stations = tuple(_finite("station_r_over_r", value) for value in station_r_over_r)
    if len(stations) < 2:
        raise ValueError("At least two blade stations are required.")
    if any(not 0.0 < value <= 1.0 for value in stations):
        raise ValueError("station_r_over_r values must lie in (0, 1].")
    if any(right <= left for left, right in zip(stations, stations[1:])):
        raise ValueError("station_r_over_r values must be strictly increasing.")

    radius = inputs.diameter_m / 2.0
    tip_length = radius - inputs.hinge_radius_m
    theta = math.radians(inputs.fold_angle_deg)
    tip_x = inputs.hinge_radius_m + tip_length * math.cos(theta)
    tip_y = tip_length * math.sin(theta)
    tip_axis_radius = math.hypot(tip_x, tip_y)
    centerline_radius = max(inputs.hinge_radius_m, tip_axis_radius)
    projected_radius = max(inputs.hinge_radius_m, tip_x)
    minimum_radius = max(inputs.hinge_radius_m, abs(inputs.hinge_radius_m - tip_length))
    segment_distance = _origin_to_segment_distance(
        (inputs.hinge_radius_m, 0.0),
        (tip_x, tip_y),
    )
    hub_clearance = segment_distance - inputs.hub_radius_m
    full_stow_clearance = (
        max(0.0, inputs.hinge_radius_m - tip_length) - inputs.hub_radius_m
    )
    collision_free_minimum_radius = _collision_free_minimum_envelope_radius(
        hinge_radius_m=inputs.hinge_radius_m,
        tip_length_m=tip_length,
        hub_radius_m=inputs.hub_radius_m,
    )

    root_gap = stations[0] * radius - inputs.hub_radius_m
    tip_gap = radius - stations[-1] * radius
    tolerance = max(1e-9, radius * 1e-9)
    first_station_radius = stations[0] * radius
    last_station_radius = stations[-1] * radius
    hinge_station_covered = (
        first_station_radius < inputs.hinge_radius_m < last_station_radius
    )
    station_span_complete = (
        abs(root_gap) <= tolerance
        and abs(tip_gap) <= tolerance
        and hinge_station_covered
    )
    minimum_diameter = 2.0 * minimum_radius
    collision_free_minimum_diameter = 2.0 * collision_free_minimum_radius
    minimum_margin = inputs.stowed_requirement_m - collision_free_minimum_diameter
    current_margin = inputs.stowed_requirement_m - 2.0 * centerline_radius
    minimum_reachable = minimum_margin >= -tolerance
    current_requirement_met = current_margin >= -tolerance

    reasons: list[str] = []
    if not minimum_reachable:
        reasons.append("stowed_requirement_unreachable")
    if not current_requirement_met:
        reasons.append("current_envelope_exceeds_requirement")
    if full_stow_clearance < -tolerance:
        reasons.append("full_stow_path_intersects_hub")
    if not station_span_complete:
        reasons.append("surface_stations_do_not_cover_hub_to_tip")
    if not hinge_station_covered:
        reasons.append("hinge_outside_surface_station_span")
    if hub_clearance < -tolerance:
        reasons.append("tip_centerline_intersects_hub")

    return MechanismGeometryAudit(
        diameter_m=inputs.diameter_m,
        hub_radius_m=inputs.hub_radius_m,
        hinge_radius_m=inputs.hinge_radius_m,
        tip_segment_length_m=tip_length,
        fold_angle_deg=inputs.fold_angle_deg,
        fold_progress_01=abs(inputs.fold_angle_deg) / 180.0,
        tip_center_x_m=tip_x,
        tip_center_y_m=tip_y,
        projected_effective_diameter_m=2.0 * projected_radius,
        centerline_envelope_diameter_m=2.0 * centerline_radius,
        minimum_centerline_envelope_diameter_m=minimum_diameter,
        collision_free_minimum_envelope_diameter_m=collision_free_minimum_diameter,
        hub_centerline_clearance_m=hub_clearance,
        full_stow_path_hub_clearance_m=full_stow_clearance,
        stowed_requirement_m=inputs.stowed_requirement_m,
        stowed_requirement_margin_m=minimum_margin,
        current_requirement_margin_m=current_margin,
        minimum_requirement_reachable=minimum_reachable,
        current_envelope_requirement_met=current_requirement_met,
        root_surface_gap_m=root_gap,
        tip_surface_gap_m=tip_gap,
        hinge_station_covered=hinge_station_covered,
        station_span_complete=station_span_complete,
        screening_checks_passed=not reasons,
        compatibility_reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class MechanismPhysicsPoint:
    """One prescribed-angle V02 software-fixture moment decomposition."""

    rpm: float
    theta_deg: float
    centrifugal_moment_nm: float
    aerodynamic_moment_nm: float
    stiffness_moment_nm: float
    damping_moment_nm: float
    friction_moment_nm: float
    stop_moment_nm: float
    net_moment_nm: float


@dataclass(frozen=True)
class MechanismPhysicsFixture:
    fixture_id: str
    source_sha256: str
    diameter_m: float
    hinge_radius_m: float
    blade_count: int
    selected: MechanismPhysicsPoint
    curve: tuple[MechanismPhysicsPoint, ...]
    aerodynamic_load_included: bool
    classification: str = PHYSICS_FIXTURE_CLASSIFICATION
    physical_qualification: bool = False


def _physics_point(config, *, rpm: float, theta_deg: float) -> MechanismPhysicsPoint:
    components = compute_hinge_moments(
        rpm=rpm,
        theta_deg=theta_deg,
        theta_dot_rad_s=0.0,
        tip_thrust_n=0.0,
        config=config,
    )
    return MechanismPhysicsPoint(
        rpm=rpm,
        theta_deg=theta_deg,
        centrifugal_moment_nm=components.M_centrifugal_nm,
        aerodynamic_moment_nm=components.M_aero_nm,
        stiffness_moment_nm=components.M_stiffness_nm,
        damping_moment_nm=components.M_damping_nm,
        friction_moment_nm=components.M_friction_nm,
        stop_moment_nm=components.M_stop_nm,
        net_moment_nm=components.M_net_nm,
    )


def build_mechanism_physics_fixture(
    config_path: str | Path,
    *,
    rpm: float,
    theta_deg: float,
) -> MechanismPhysicsFixture:
    """Load the versioned V02 fixture and expose prescribed-angle moment components."""
    speed = _finite("rpm", rpm)
    angle = _finite("theta_deg", theta_deg)
    if not 0.0 <= speed <= MAX_FIXTURE_RPM:
        raise ValueError(f"rpm must lie between 0 and {MAX_FIXTURE_RPM:.0f}.")
    path = Path(config_path)
    try:
        source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"Cannot read mechanism fixture: {exc}") from exc
    if source_sha256 != V02_FIXTURE_SHA256:
        raise ValueError("Mechanism fixture SHA-256 does not match TIP_HINGED_250_V02.")
    config = load_config(path)
    if config.id != "TIP_HINGED_250_V02":
        raise ValueError("Mechanism physics view only permits TIP_HINGED_250_V02.")
    if not config.hinge.theta_min_deg <= angle <= config.hinge.theta_max_deg:
        raise ValueError("theta_deg must remain inside the fixture hard-stop range.")
    span = config.hinge.theta_max_deg - config.hinge.theta_min_deg
    curve = tuple(
        _physics_point(
            config,
            rpm=speed,
            theta_deg=config.hinge.theta_min_deg + span * index / 36.0,
        )
        for index in range(37)
    )
    return MechanismPhysicsFixture(
        fixture_id=config.id,
        source_sha256=source_sha256,
        diameter_m=config.geometry.diameter_open_m,
        hinge_radius_m=config.geometry.hinge_position_m,
        blade_count=config.geometry.blade_count,
        selected=_physics_point(config, rpm=speed, theta_deg=angle),
        curve=curve,
        aerodynamic_load_included=False,
    )
