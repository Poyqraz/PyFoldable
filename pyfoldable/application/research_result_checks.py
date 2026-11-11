"""Semantic checks for saved research v1's BEM v5 and PY-05 v2 payloads.

These are read-only checks of reported values. Only deterministic arithmetic
and the retained final polar lookups are replayed, never a solver or a trace.
"""
from bisect import bisect_left, bisect_right
from contextlib import contextmanager
import math

from pyfoldable.core.bem import (
    BEMAnnulusSettings, BEMPolarQueryEnvelope, _AIR_GAMMA, _AIR_GAS_CONSTANT_J_KG_K,
)
from pyfoldable.core.bem_rotor import _interpolate_station, _radial_limits
from pyfoldable.core.rotational_augmentation import RotationalAugmentationModel
from pyfoldable.dynamics.mechanism_transient import RPM_TO_RAD_S

_MESSAGES = {
    "policy": "BEM raporunun sürümü, hesap ayarları veya çalışma koşulu saklanan istekle uyuşmuyor.",
    "geometry": "Radyal elemanların konumu veya geometrisi saklanan kanat istasyonlarıyla uyuşmuyor.",
    "convergence": "BEM elemanlarının yakınsama durumu veya sayısal sınırları tutarsız.",
    "queries": "Polar sorgu kapsamı veya son sorgu, saklanan polar verileriyle uyuşmuyor.",
    "loads": "Radyal yükler, toplam yükler veya şaft gücü birbiriyle uyuşmuyor.",
    "mechanism": "Mekanizmanın örnek zamanları, devir rampası veya durma kaydı saklanan istekle uyuşmuyor.",
}
_AXES = ("alpha_rad", "reynolds", "mach")
_ANNULUS_NUMBERS = (
    "psi_rad", "inflow_angle_rad", "angle_of_attack_rad", "axial_induced_velocity_m_s",
    "tangential_induced_velocity_m_s", "relative_speed_m_s", "reynolds", "mach",
    "cl", "cd", "raw_polar_cl", "raw_polar_cd", "circulation_m2_s", "residual_m2_s",
    "tip_loss_factor", "root_loss_factor", "combined_loss_factor",
    "differential_thrust_n_m", "differential_torque_nm_m",
)
_MECHANISM_CHANNELS = (
    "time_s", "angle_rad", "angular_velocity_rad_s", "angular_acceleration_rad_s2",
    "rpm", "omega_rad_s", "omega_dot_rad_s2", "applied_torque_nm", "spring_torque_nm",
    "damping_torque_nm", "dry_friction_torque_nm", "centrifugal_torque_nm", "euler_torque_nm",
    "effective_energy_j", "applied_power_w", "damping_power_w", "dry_friction_power_w",
    "total_dissipation_power_w", "applied_work_j", "viscous_dissipated_energy_j",
    "dry_friction_dissipated_energy_j", "total_dissipated_energy_j",
)


class SavedResultSemanticError(ValueError):
    """A localized, fixed description with technical details kept separate."""

    def __init__(self, group, detail):
        self.user_message = _MESSAGES[group]
        super().__init__(f"Saved {group}: {detail}")


@contextmanager
def _checking(group):
    try:
        yield
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError) as exc:
        raise SavedResultSemanticError(group, str(exc)) from exc


def _require(predicate, detail):
    if not predicate:
        raise ValueError(detail)


def _finite(value):
    _require(type(value) in (int, float) and math.isfinite(value), "expected a finite number")
    return value


def _close(value, expected, field):
    # Repeat the original operations on JSON-round-tripped doubles. This is
    # arithmetic rounding allowance, never a fit or a physical error tolerance.
    a, b = _finite(value), _finite(expected)
    _require(abs(a-b) <= 4 * max(math.ulp(a), math.ulp(b)), f"{field} contradicts retained values")


def _policy(doc, blade, condition, family):
    request, rotor = doc["request"], doc["rotor"]
    _require(type(doc["schema_version"]) is int and doc["schema_version"] == 1
             and doc["artifact_class"] == "active_design_bem_screening"
             and doc["qualification"] == "screening_only_until_pr06c_passes"
             and request["polar_evidence_status"] == "caller_supplied_unqualified"
             and type(request["bem_rotor_schema_version"]) is int and request["bem_rotor_schema_version"] == 5
             and type(rotor["schema_version"]) is int and rotor["schema_version"] == 5,
             "unsupported saved BEM report schema")
    settings = rotor["settings"]
    _require(request["ui_request"]["settings"] == settings
             and request["policy"] == {**settings, "bounds": "error", "solved_pose": "fully_open"}
             and settings["radial_domain"] == rotor["radial_domain"] == "station_span"
             and rotor["polar_bounds"] == "error" and rotor["geometry_extended"] is False
             and rotor["integration_method"] == "midpoint" and rotor["geometry_interpolation"] == "linear_chord_twist",
             "BEM geometry or query policy contradicts the retained request")
    _require(rotor["airfoil_id"] == family.airfoil_id == blade.stations[0].airfoil_id
             and rotor["operating_condition_id"] == condition.id and rotor["scenario_id"] == family.scenario_id,
             "rotor profile, condition or polar scenario contradicts the retained request")
    local = dict(settings["annulus_settings"])
    aug = dict(local.pop("rotational_augmentation"))
    model_id, source = aug.pop("model_id"), aug.pop("source")
    model = RotationalAugmentationModel(**aug)
    _require(model_id == model.model_id and source == model.as_mapping()["source"],
             "rotational augmentation identity contradicts its retained policy")
    for key in ("angle_tolerance_rad", "residual_tolerance_m2_s",
                "relative_residual_tolerance", "minimum_tip_loss_factor"):
        _finite(local[key])
    controls = BEMAnnulusSettings(**local, rotational_augmentation=model)
    _require(controls.loading_branch == "positive_only" and controls.bracket_samples <= 512
             and controls.max_iterations <= 300, "unsupported BEM loading branch or solve budget")
    return controls


def _envelope(raw, domain, sources):
    count = raw["query_count"]
    _require(type(count) is int and count > 0, "query count must be a positive integer")
    for name, (domain_lo, domain_hi) in zip(_AXES, domain):
        lo, hi = _finite(raw[name+"_min"]), _finite(raw[name+"_max"])
        _require(lo <= hi, f"{name} query bounds are not ordered")
        # With bounds=error the solver rejects strict excursions; the retained
        # float endpoints need no extrapolation allowance or synthetic queries.
        _require(domain_lo <= lo <= hi <= domain_hi, f"{name} outside retained polar domain")
    declared_sources = raw["sources"]
    dims = raw["interpolated_dimensions"]
    _require(isinstance(declared_sources, list) and declared_sources
             and len(set(declared_sources)) == len(declared_sources)
             and set(declared_sources) <= sources, "query sources contradict the retained polar family")
    _require(isinstance(dims, list) and dims == sorted(set(dims)) and set(dims) <= set(_AXES)
             and raw["clamped_dimensions"] == [], "invalid interpolation or clamping summary")
    return BEMPolarQueryEnvelope(**{**raw, "sources": tuple(declared_sources),
                                   "interpolated_dimensions": tuple(dims), "clamped_dimensions": ()})


def _annulus_status(solution, controls, condition, family, settings):
    _require(type(solution["schema_version"]) is int and solution["schema_version"] == 5
             and solution["operating_condition_id"] == condition.id
             and solution["airfoil_id"] == family.airfoil_id and solution["scenario_id"] == family.scenario_id
             and solution["settings"] == settings and solution["polar_bounds"] == "error",
             "annulus identity or policy contradicts the retained request")
    _require(solution["converged"] is True and type(solution["iterations"]) is int
             and 0 <= solution["iterations"] <= controls.max_iterations, "annulus convergence or iteration count invalid")
    for field in _ANNULUS_NUMBERS:
        _finite(solution[field])
    gamma, residual = solution["circulation_m2_s"], solution["residual_m2_s"]
    # Kernel residual = swirl circulation minus blade circulation.
    limit = controls.residual_tolerance_m2_s + controls.relative_residual_tolerance * max(
        abs(gamma), abs(gamma+residual), 1e-30)
    speed = solution["relative_speed_m_s"]
    flow_tol = controls.angle_tolerance_rad * max(speed, 1.)
    _require(speed > 0 and abs(residual) <= limit and gamma >= -limit
             and solution["loading_regime"] == ("positive" if gamma > limit else "zero")
             and min(solution["axial_induced_velocity_m_s"], solution["tangential_induced_velocity_m_s"]) >= -flow_tol,
             "annulus convergence contradicts the retained residual limit or positive-loading branch")
    for enabled, field in ((controls.include_tip_loss, "tip_loss_factor"),
                           (controls.include_root_loss, "root_loss_factor")):
        factor = solution[field]
        _require((controls.minimum_tip_loss_factor <= factor <= 1.) if enabled else factor == 1.,
                 f"{field} contradicts the retained loss policy")
    _close(solution["combined_loss_factor"], solution["tip_loss_factor"] * solution["root_loss_factor"], "combined loss")


def _final_query(solution, envelope, condition, family, controls):
    iters = solution["iterations"]
    # One initial query, at most bracket_samples scan queries; when Brent runs,
    # allow both endpoint evaluations, up to iters evaluations, and final replay.
    limit = 1 + controls.bracket_samples + (iters + 3 if iters else 0)
    _require(envelope.query_count <= limit and (not iters or envelope.query_count >= 5),
             "annulus query count contradicts the retained solve budget or iteration count")
    if envelope.query_count == 1:
        _require(all(getattr(envelope, axis+"_min") == getattr(envelope, axis+"_max") for axis in _AXES),
                 "one query cannot have distinct query bounds")
    alpha, re, mach = (solution[k] for k in ("angle_of_attack_rad", "reynolds", "mach"))
    for key, value in zip(_AXES, (alpha, re, mach)):
        _require(getattr(envelope, key+"_min") <= value <= getattr(envelope, key+"_max"),
                 f"final query {key} lies outside the annulus envelope")
    speed, chord = solution["relative_speed_m_s"], solution["chord_m"]
    _close(alpha, solution["twist_rad"] - solution["inflow_angle_rad"], "final query alpha")
    _close(re, condition.air_density_kg_m3 * speed * chord / condition.dynamic_viscosity_pa_s, "final query Reynolds")
    sound = math.sqrt(_AIR_GAMMA * _AIR_GAS_CONSTANT_J_KG_K * condition.temperature_k)
    _close(mach, speed / sound, "final query Mach")
    # Within one annulus both coordinates increase with the same relative
    # speed. Check paired extrema without reconstructing the query sequence.
    for edge in ("min", "max"):
        speed_at_edge = getattr(envelope, "mach_"+edge) * sound
        _close(getattr(envelope, "reynolds_"+edge),
               condition.air_density_kg_m3 * speed_at_edge * chord / condition.dynamic_viscosity_pa_s,
               f"query {edge} Reynolds/Mach correspondence")
    query = family.query(alpha_rad=alpha, reynolds=re, mach=mach, bounds="error")
    _require(solution["polar_sources"] == list(query.sources) and set(query.sources) <= set(envelope.sources)
             and solution["interpolated_dimensions"] == list(query.interpolated_dimensions)
             and set(query.interpolated_dimensions) <= set(envelope.interpolated_dimensions)
             and solution["clamped_dimensions"] == [], "final query metadata contradicts the retained polar family")
    if envelope.query_count == 1:
        _require(envelope.sources == query.sources and envelope.interpolated_dimensions == query.interpolated_dimensions,
                 "one query must have the same provenance as the final query")
    for field, expected in (("raw_polar_cl", query.cl), ("raw_polar_cd", query.cd)):
        # The logarithmic Reynolds weights and chained blends can differ by a
        # few last bits across libm builds, especially near a zero crossing.
        value = solution[field]
        _require(abs(value-expected) <= 32 * math.ulp(max(1., abs(value), abs(expected))),
                 f"final query {field} contradicts retained polar interpolation")
    correction = controls.rotational_augmentation.apply(
        alpha, solution["raw_polar_cl"], solution["raw_polar_cd"], chord_over_radius=chord/solution["radius_m"])
    audit = solution["rotational_augmentation"]
    expected = correction.as_mapping()
    _require(set(audit) == set(expected), "invalid rotational augmentation record")
    for key, value in expected.items():
        if type(value) is float:
            _close(audit[key], value, f"rotational augmentation {key}")
        else:
            _require(type(audit[key]) is type(value) and audit[key] == value,
                     f"rotational augmentation {key} contradicts its retained policy")
    _close(solution["cl"], correction.cl, "annulus lift coefficient")
    _close(solution["cd"], correction.cd, "annulus drag coefficient")


def check_bem_report(doc, blade, condition, family):
    """Bind output to the retained geometry, policy and admitted polar family."""
    rotor = doc["rotor"]
    with _checking("policy"):
        controls = _policy(doc, blade, condition, family)
    with _checking("geometry"):
        count, elements = rotor["settings"]["annulus_count"], rotor["elements"]
        _require(type(count) is int and type(rotor["annulus_count"]) is int
                 and rotor["annulus_count"] == len(elements) == count, "annulus count contradicts the executed policy")
        inner, outer, _ = _radial_limits(blade, "station_span")
        _close(rotor["inner_radius_m"], inner, "inner radius")
        _close(rotor["outer_radius_m"], outer, "outer radius")
        dr = (outer-inner)/count
    with _checking("queries"):
        alpha = family.tables[0].alpha_rad
        _require(all(t.alpha_rad == alpha for t in family.tables), "retained polar family lacks a common angle grid")
        reynolds = [t.reynolds for t in family.tables]
        mach = [t.mach for t in family.tables]
        domain = ((alpha[0], alpha[-1]), (min(reynolds), max(reynolds)), (min(mach), max(mach)))
        sources = {t.source for t in family.tables}
    envelopes = []
    for i, e in enumerate(elements):
        with _checking("geometry"):
            _require(type(e["index"]) is int and e["index"] == i, "annulus indices must be ordered and contiguous")
            lo, hi = inner + i*dr, inner + (i+1)*dr
            _close(e["inner_radius_m"], lo, f"annulus {i} inner boundary")
            _close(e["outer_radius_m"], hi, f"annulus {i} outer boundary")
            width = _finite(e["outer_radius_m"]) - _finite(e["inner_radius_m"])
            _require(width > 0., "annulus width must be positive")
            _close(e["width_m"], width, f"annulus {i} width")
            station, extended = _interpolate_station(blade, .5*(lo+hi))
            _require(not extended and e["geometry_extrapolated"] is False, "annulus geometry was extrapolated")
            s = e["solution"]
            _close(s["radius_m"], station.r_over_R*blade.radius_m, f"annulus {i} midpoint radius")
            _close(s["r_over_R"], station.r_over_R, f"annulus {i} normalized radius")
            _close(s["chord_m"], station.chord_m, f"annulus {i} chord")
            _close(s["twist_rad"], station.twist_rad, f"annulus {i} twist")
        with _checking("convergence"):
            _annulus_status(s, controls, condition, family, rotor["settings"]["annulus_settings"])
        with _checking("queries"):
            env = _envelope(s["polar_query_envelope"], domain, sources)
            _final_query(s, env, condition, family, controls)
            envelopes.append(env)
        with _checking("loads"):
            _close(e["thrust_n"], s["differential_thrust_n_m"] * width, f"annular thrust {i}")
            _close(e["torque_nm"], s["differential_torque_nm_m"] * width, f"annular torque {i}")
    with _checking("queries"):
        combined = _envelope(rotor["polar_query_envelope"], domain, sources)
        _require(combined == BEMPolarQueryEnvelope.combine(tuple(envelopes)), "aggregate query envelope contradicts its annuli")
        final_sources = list(dict.fromkeys(source for e in elements for source in e["solution"]["polar_sources"]))
        final_dims = sorted({dim for e in elements for dim in e["solution"]["interpolated_dimensions"]})
        _require(rotor["polar_sources"] == final_sources and rotor["interpolated_dimensions"] == final_dims
                 and rotor["clamped_dimensions"] == [], "aggregate final query metadata contradicts its annuli")
    with _checking("convergence"):
        _close(rotor["maximum_residual_m2_s"], max(abs(e["solution"]["residual_m2_s"]) for e in elements),
               "maximum residual")
    with _checking("loads"):
        thrust, torque = (math.fsum(e[key] for e in elements) for key in ("thrust_n", "torque_nm"))
        power = condition.angular_speed_rad_s * torque
        _close(rotor["thrust_n"], thrust, "thrust total")
        _close(rotor["torque_nm"], torque, "torque total")
        _close(rotor["shaft_power_w"], power, "shaft power")
        n, d, rho = condition.angular_speed_rad_s / (2*math.pi), blade.diameter_m, condition.air_density_kg_m3
        force_scale = rho * n**2 * d**4
        _close(rotor["thrust_coefficient"], thrust/force_scale, "thrust coefficient")
        _close(rotor["torque_coefficient"], torque/(force_scale*d), "torque coefficient")
        _close(rotor["power_coefficient"], power/(rho*n**3*d**5), "power coefficient")
        if condition.forward_speed_m_s > 0. and power > 0.:
            _close(rotor["propulsive_efficiency"], condition.forward_speed_m_s*thrust/power, "propulsive efficiency")
        else:
            _require(rotor["propulsive_efficiency"] is None, "propulsive efficiency must be undefined")


def check_mechanism_history(result, request):
    """Validate drive/sample/terminal-event correspondence without integrating."""
    with _checking("mechanism"):
        samples, times = result["samples"], result["time_s"]
        drive, params = request.drive, request.parameters
        _require(isinstance(samples, list) and 2 <= len(samples) <= request.controls.max_samples,
                 "missing or oversized mechanism sample history")
        _require(all(isinstance(result[key], list) and len(result[key]) == len(samples)
                     for key in _MECHANISM_CHANNELS), "mechanism sample columns differ in length")
        previous = None
        for i, sample in enumerate(samples):
            time = _finite(times[i])
            _require(drive.time_s[0] <= time <= drive.time_s[-1]
                     and (previous is None or time > previous), "sample times contradict the drive window or order")
            if previous is not None:
                step = request.controls.max_step_s
                # The solver steps in elapsed time, then serializes time stamps;
                # subtraction of the two stamps can lose a few low bits.
                tolerance = 4 * max(math.ulp(previous), math.ulp(time), math.ulp(step))
                _require(time-previous <= step+tolerance, "sample time gap exceeds the retained maximum step")
            for key in _MECHANISM_CHANNELS:
                _require(_finite(sample[key]) == _finite(result[key][i]), f"sample {i} {key} differs from its retained column")
            j = min(len(drive.time_s)-2, bisect_right(drive.time_s, time)-1)
            fraction = (time-drive.time_s[j])/(drive.time_s[j+1]-drive.time_s[j])
            rpm = drive.rpm[j] + fraction*(drive.rpm[j+1]-drive.rpm[j])
            _close(sample["rpm"], rpm, f"sample {i} RPM from the drive")
            _close(sample["omega_rad_s"], rpm*RPM_TO_RAD_S, f"sample {i} shaft speed from the drive")
            previous = time
        _close(times[0], drive.time_s[0], "mechanism initial time")
        _close(samples[0]["angle_rad"], request.initial_angle_rad, "mechanism initial angle")
        _close(samples[0]["angular_velocity_rad_s"], request.initial_angular_velocity_rad_s, "mechanism initial velocity")
        terminal = result["contact"]
        status = result["status"]
        if status == "completed":
            _require(terminal is None and times[-1] == drive.time_s[-1], "completed termination must reach the drive end without contact")
            interior_angles = result["angle_rad"]
        else:
            _require(status == "stop_contact" and isinstance(terminal, dict), "unsupported mechanism termination")
            stops = {"lower": params.lower_stop_rad, "upper": params.upper_stop_rad}
            _require(terminal["stop"] in stops and terminal["time_s"] == times[-1],
                     "contact termination must identify a stop and the last sample")
            _close(terminal["angle_rad"], stops[terminal["stop"]], "contact stop angle")
            _close(samples[-1]["angle_rad"], terminal["angle_rad"], "terminal sample angle")
            _close(samples[-1]["angular_velocity_rad_s"], terminal["preimpact_angular_velocity_rad_s"], "terminal sample velocity")
            interior_angles = result["angle_rad"][:-1]
        _require(all(params.lower_stop_rad < angle < params.upper_stop_rad for angle in interior_angles),
                 "a sample lies at or outside a stop before terminal contact")
        knots = tuple(t for t in drive.time_s[:-1] if t < times[-1])
        indices = result["segment_start_indices"]
        expected = [bisect_left(times, t) for t in knots]
        _require(isinstance(indices, list) and all(type(i) is int for i in indices)
                 and indices == expected and all(times[i] == t for i, t in zip(expected, knots)),
                 "segment starts contradict the retained drive knots")
