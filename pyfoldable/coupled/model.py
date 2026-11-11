"""Declared coupled case: geometry from the canonical draft, explicit mechanics.

Structural representation (minimum useful, see ADR in docs):

* rotor hub: rigid, driven by a *prescribed constant shaft speed* (MBDyn
  ``axial rotation`` joint). Torque-driven shaft dynamics are a different
  boundary condition and are not offered here; the drive reaction torque is an
  output, never an input.
* per blade: rigid proximal segment rigidly attached to the hub; rigid distal
  segment connected at the declared hinge by an ideal revolute joint whose axis
  is parallel to the shaft (in-plane fold, docs/foldable_conventions.md).
* hinge law: linear spring about a rest angle, linear viscous damping, and a
  unilateral linear spring–dashpot stop at the open stop angle (MBDyn
  ``double linear viscoelastic`` on the hinge axis). Optional release latch
  holds the declared initial fold angle until ``release_time_s``.
* centrifugal, Coriolis and Euler effects are *not* added as loads: they arise
  from the multibody inertia of the distal body. Aerodynamic loads come only
  from DUST through preCICE.

Missing hardware properties may be entered as demonstration assumptions; they
are labelled as such in every record and never presented as measurements.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math

from pyfoldable.core.bem_rotor import _interpolate_station

SUPPORTED_DRIVE = "prescribed_constant_speed"
DECLARATION_KINDS = ("demonstration_assumption", "declared_hardware_property")


@dataclass(frozen=True)
class CoupledMechanics:
    """Distal-segment and hinge properties, SI units.

    distal_mass_kg: mass of one distal (hinged) segment including its share of the joint.
    distal_cg_from_hinge_m: distance from hinge axis to the distal CG along the open span line.
    distal_inertia_cg_kg_m2: moment of inertia about an axis through the CG parallel to the hinge axis.
    spring_nm_per_rad / spring_rest_rad: torsion spring M = -k (theta - theta_rest).
    hinge_damping_nm_s_per_rad: linear viscous hinge damping.
    stop_angle_rad: open stop (0 = radial open); motion beyond it is penetration.
    stop_stiffness_nm_per_rad / stop_restitution: unilateral penalty stop; the
        dashpot coefficient follows from the restitution for a linear oscillator
        with the hinge-axis inertia (declared contact law, not a measured impact).
    fold_limit_rad: folded-side limit using the same contact law.
    initial_fold_rad / initial_rate_rad_s: distal pose and hinge rate at t = 0.
    release_time_s: a latch holds the initial pose until this time (0 = free).
    proximal_mass_kg / hub_mass_kg: carrier masses of prescribed-motion bodies;
        they cannot change the hinge or aerodynamic response at constant shaft
        speed and only enter constraint reactions.
    """
    distal_mass_kg: float
    distal_cg_from_hinge_m: float
    distal_inertia_cg_kg_m2: float
    spring_nm_per_rad: float = 0.0
    spring_rest_rad: float = 0.0
    hinge_damping_nm_s_per_rad: float = 0.0
    stop_angle_rad: float = 0.0
    stop_stiffness_nm_per_rad: float = 200.0
    stop_restitution: float = 0.5
    fold_limit_rad: float = -math.radians(170.0)
    initial_fold_rad: float = -math.radians(10.0)
    initial_rate_rad_s: float = 0.0
    release_time_s: float = 0.0
    proximal_mass_kg: float = 0.05
    hub_mass_kg: float = 0.10
    source: str = ""
    declaration_kind: str = "demonstration_assumption"

    @property
    def hinge_inertia_kg_m2(self) -> float:
        return self.distal_inertia_cg_kg_m2 + self.distal_mass_kg * self.distal_cg_from_hinge_m ** 2

    @property
    def stop_damping_nm_s_per_rad(self) -> float:
        """Linear Kelvin–Voigt dashpot giving the declared restitution for J_h, k_c."""
        e = self.stop_restitution
        if e >= 1.0:
            return 0.0
        ln_e = math.log(e)
        zeta = -ln_e / math.sqrt(math.pi ** 2 + ln_e ** 2)
        return 2.0 * zeta * math.sqrt(self.stop_stiffness_nm_per_rad * self.hinge_inertia_kg_m2)


@dataclass(frozen=True)
class CoupledControls:
    """Advanced numerical controls; defaults are the reviewed demonstration set."""
    azimuth_step_deg: float = 5.0
    duration_s: float = 0.15
    elements_per_segment: int = 8
    n_wake_panels: int = 1
    max_wake_particles: int = 60000
    wake_box_axial_m: float = 1.6
    wake_box_radial_factor: float = 1.6
    coupling_max_iterations: int = 30
    coupling_position_tol_m: float = 1.0e-6
    coupling_rotation_tol_rad: float = 1.0e-6
    coupling_velocity_tol_m_s: float = 1.0e-3
    coupling_angular_velocity_tol_rad_s: float = 1.0e-3
    aitken_initial_relaxation: float = 0.5
    mbdyn_tolerance: float = 1.0e-6
    mbdyn_max_iterations: int = 50
    mbdyn_spectral_radius: float = 0.6
    ll_tol: float = 1.0e-6
    ll_max_iter: int = 200
    ll_damp: float = 25.0
    fmm: bool = False
    vortex_stretching: bool = True
    wall_timeout_s: float = 3600.0


@dataclass(frozen=True)
class SegmentSection:
    radius_m: float
    chord_m: float
    twist_rad: float
    source: str  # "station" or "hinge_interpolated"


@dataclass(frozen=True)
class CaseGeometry:
    blade_count: int
    tip_radius_m: float
    hub_radius_m: float
    root_radius_m: float
    hinge_radius_m: float
    first_aero_radius_m: float
    last_aero_radius_m: float
    proximal_sections: tuple[SegmentSection, ...]
    distal_sections: tuple[SegmentSection, ...]
    profile: str


@dataclass(frozen=True)
class CoupledCase:
    geometry: CaseGeometry
    mechanics: CoupledMechanics
    controls: CoupledControls
    rpm: float
    omega_rad_s: float
    inflow_m_s: float
    density_kg_m3: float
    viscosity_pa_s: float
    temperature_k: float
    speed_of_sound_m_s: float
    drive: str = SUPPORTED_DRIVE
    meta: dict = field(default_factory=dict)

    @property
    def dt_s(self) -> float:
        return math.radians(self.controls.azimuth_step_deg) / self.omega_rad_s

    @property
    def n_steps(self) -> int:
        return max(1, int(round(self.controls.duration_s / self.dt_s)))

    @property
    def final_time_s(self) -> float:
        return self.n_steps * self.dt_s

    def as_dict(self) -> dict:
        return {"geometry": asdict(self.geometry), "mechanics": asdict(self.mechanics),
                "controls": asdict(self.controls), "rpm": self.rpm, "omega_rad_s": self.omega_rad_s,
                "inflow_m_s": self.inflow_m_s, "density_kg_m3": self.density_kg_m3,
                "viscosity_pa_s": self.viscosity_pa_s, "temperature_k": self.temperature_k,
                "speed_of_sound_m_s": self.speed_of_sound_m_s, "drive": self.drive,
                "dt_s": self.dt_s, "n_steps": self.n_steps, "final_time_s": self.final_time_s,
                "derived": {"hinge_inertia_kg_m2": self.mechanics.hinge_inertia_kg_m2,
                            "stop_damping_nm_s_per_rad": self.mechanics.stop_damping_nm_s_per_rad},
                "meta": self.meta}


class CoupledCaseError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def _finite(name, value, *, lo=None, hi=None, strict_lo=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise CoupledCaseError("invalid_input", f"{name} must be a finite number")
    if lo is not None and (value <= lo if strict_lo else value < lo):
        raise CoupledCaseError("invalid_input", f"{name} out of range")
    if hi is not None and value > hi:
        raise CoupledCaseError("invalid_input", f"{name} out of range")
    return float(value)


def validate_mechanics(m: CoupledMechanics) -> None:
    _finite("distal_mass_kg", m.distal_mass_kg, lo=0.0, hi=50.0, strict_lo=True)
    _finite("distal_cg_from_hinge_m", m.distal_cg_from_hinge_m, lo=0.0, hi=2.0)
    _finite("distal_inertia_cg_kg_m2", m.distal_inertia_cg_kg_m2, lo=0.0, hi=10.0)
    _finite("spring_nm_per_rad", m.spring_nm_per_rad, lo=0.0, hi=1e4)
    _finite("spring_rest_rad", m.spring_rest_rad, lo=-math.pi, hi=math.pi)
    _finite("hinge_damping_nm_s_per_rad", m.hinge_damping_nm_s_per_rad, lo=0.0, hi=1e3)
    _finite("stop_stiffness_nm_per_rad", m.stop_stiffness_nm_per_rad, lo=0.0, hi=1e7, strict_lo=True)
    _finite("stop_restitution", m.stop_restitution, lo=0.0, hi=1.0, strict_lo=True)
    _finite("release_time_s", m.release_time_s, lo=0.0, hi=10.0)
    _finite("initial_rate_rad_s", m.initial_rate_rad_s, lo=-1e3, hi=1e3)
    _finite("proximal_mass_kg", m.proximal_mass_kg, lo=0.0, hi=50.0, strict_lo=True)
    _finite("hub_mass_kg", m.hub_mass_kg, lo=0.0, hi=50.0, strict_lo=True)
    if m.stop_angle_rad != 0.0:
        raise CoupledCaseError("unsupported_stop", "Only the declared open stop at 0 deg is supported in v1")
    if not -math.radians(175.0) <= m.fold_limit_rad < m.initial_fold_rad <= m.stop_angle_rad:
        raise CoupledCaseError("invalid_pose", "Require -175 deg <= fold limit < initial fold <= open stop")
    if m.hinge_inertia_kg_m2 <= 0.0:
        raise CoupledCaseError("invalid_input", "Hinge-axis inertia must be positive")
    if not m.source.strip() or m.declaration_kind not in DECLARATION_KINDS:
        raise CoupledCaseError("missing_source", "Declare the mechanical source and whether values are demonstration assumptions")


def validate_controls(c: CoupledControls) -> None:
    _finite("azimuth_step_deg", c.azimuth_step_deg, lo=0.1, hi=30.0)
    _finite("duration_s", c.duration_s, lo=0.0, hi=2.0, strict_lo=True)
    if type(c.elements_per_segment) is not int or not 2 <= c.elements_per_segment <= 40:
        raise CoupledCaseError("invalid_controls", "elements_per_segment must be 2..40")
    if type(c.coupling_max_iterations) is not int or not 2 <= c.coupling_max_iterations <= 200:
        raise CoupledCaseError("invalid_controls", "coupling_max_iterations must be 2..200")
    if type(c.max_wake_particles) is not int or not 1000 <= c.max_wake_particles <= 500000:
        raise CoupledCaseError("invalid_controls", "max_wake_particles must be 1000..500000")
    for name in ("coupling_position_tol_m", "coupling_rotation_tol_rad", "coupling_velocity_tol_m_s",
                 "coupling_angular_velocity_tol_rad_s", "mbdyn_tolerance", "ll_tol"):
        _finite(name, getattr(c, name), lo=0.0, hi=1.0, strict_lo=True)
    _finite("aitken_initial_relaxation", c.aitken_initial_relaxation, lo=0.0, hi=1.0, strict_lo=True)
    _finite("wall_timeout_s", c.wall_timeout_s, lo=10.0, hi=6 * 3600.0)


def _segment_sections(blade, lo: float, hi: float) -> tuple[SegmentSection, ...]:
    radius = blade.radius_m
    out = []
    station_radii = [s.r_over_R * radius for s in blade.stations]
    first, _ = _interpolate_station(blade, lo)
    out.append(SegmentSection(lo, first.chord_m, first.twist_rad,
                              "station" if any(math.isclose(lo, r, rel_tol=0, abs_tol=1e-12) for r in station_radii) else "hinge_interpolated"))
    for s, r in zip(blade.stations, station_radii):
        if lo + 1e-9 < r < hi - 1e-9:
            out.append(SegmentSection(r, s.chord_m, s.twist_rad, "station"))
    last, _ = _interpolate_station(blade, hi)
    out.append(SegmentSection(hi, last.chord_m, last.twist_rad,
                              "station" if any(math.isclose(hi, r, rel_tol=0, abs_tol=1e-12) for r in station_radii) else "hinge_interpolated"))
    return tuple(out)


def case_geometry(active) -> CaseGeometry:
    """Derive the segmented lifting-line geometry from a ResearchDesign."""
    d = active.design
    b, h = d.blade, d.hinge
    if active.root is None:
        raise CoupledCaseError("missing_root_declaration", "Declare the physical blade root")
    if (h.axial_offset_m, h.tangential_offset_m, h.axis_azimuth_rad) != (0.0, 0.0, 0.0) or not math.isclose(h.axis_elevation_rad, math.pi / 2):
        raise CoupledCaseError("unsupported_hinge_axis", "v1 supports a hinge axis parallel to the shaft through the span line")
    if len({s.airfoil_id for s in b.stations}) != 1:
        raise CoupledCaseError("catalog_profile_required", "A single catalog profile is required")
    radius = b.radius_m
    first = b.stations[0].r_over_R * radius
    last = b.stations[-1].r_over_R * radius
    root = active.root.value / 1000.0
    if active.length_order_policy == "proximal_longer" and not h.radius_m - root > radius - h.radius_m:
        raise CoupledCaseError("longer_proximal_required", "This template requires the proximal segment to be longer")
    if not b.hub_radius_m <= root <= first:
        raise CoupledCaseError("aerodynamic_station_before_physical_root", "Require hub <= root <= first aerodynamic station")
    if not first < h.radius_m < last:
        raise CoupledCaseError("hinge_outside_aero_span", "The hinge must lie strictly inside the declared aerodynamic station span")
    return CaseGeometry(b.blade_count, radius, b.hub_radius_m, root, h.radius_m, first, last,
                        _segment_sections(b, first, h.radius_m), _segment_sections(b, h.radius_m, last),
                        b.stations[0].airfoil_id)


def build_case(active, mechanics: CoupledMechanics, controls: CoupledControls) -> CoupledCase:
    validate_mechanics(mechanics)
    validate_controls(controls)
    geometry = case_geometry(active)
    if geometry.blade_count < 1 or geometry.blade_count > 4:
        raise CoupledCaseError("unsupported_blade_count", "v1 supports 1..4 blades")
    if mechanics.distal_cg_from_hinge_m > geometry.tip_radius_m - geometry.hinge_radius_m + 1e-9:
        raise CoupledCaseError("invalid_input", "Distal CG must lie on the distal segment")
    cond = active.design.operating_conditions[0]
    speed_of_sound = math.sqrt(1.4 * 287.05 * cond.temperature_k)
    return CoupledCase(geometry, mechanics, controls, active.inputs.rpm, cond.angular_speed_rad_s,
                       cond.forward_speed_m_s, cond.air_density_kg_m3, cond.dynamic_viscosity_pa_s,
                       cond.temperature_k, speed_of_sound,
                       meta={"speed_of_sound_model": "sqrt(1.4*287.05*T), matching research initial_query_ranges"})
