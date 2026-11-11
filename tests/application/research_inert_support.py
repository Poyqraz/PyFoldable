"""Explicitly inert store/caller support. Never normal deployment data."""
from dataclasses import fields, replace
import math

from pyfoldable.application import design_analysis, mechanism_transient as mech, provider_design_analysis as managed
from pyfoldable.application.provider_record_store import ProviderRecordStore
from pyfoldable.core.bem import BEM_ANNULUS_SCHEMA_VERSION, BEMAnnulusResult, BEMPolarQueryEnvelope
from pyfoldable.core.bem_rotor import BEM_ROTOR_SCHEMA_VERSION, BEMRotorElement, BEMRotorResult, _interpolate_station
from pyfoldable.core.providers import ProviderIdentity
from pyfoldable.dynamics.mechanism_transient import RPM_TO_RAD_S, StopContact, TransientResult
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.providers import xfoil
from research_reference_loader import ref
make_plan, request_grid = ref.make_plan, ref.request_grid
from test_provider_design_analysis import inert_cell


def store(tmp_path, monkeypatch, profiles):
    root = tmp_path / "INERT-store"
    plan, _ = make_plan()
    provider = ProviderIdentity("INERT-fixture", "1", "INERT-no-executable", "0")
    versions = {}
    with ProviderRecordStore(root) as disk:
        for profile in profiles:
            requests = tuple(replace(r, airfoil=load_project_airfoil(profile), scenario_id="INERT-reference")
                             for r in request_grid("NACA0012", plan["declaration"]))
            family = managed.ManagedProviderFamily(
                "INERT-family-" + profile, provider, requests,
                tuple(inert_cell(r, provider) for r in requests), "inert_fixture",
                "INERT; not an acquired provider family", (("provenance.txt", b"INERT ONLY"),))
            versions[profile] = disk.register_family(family, version_label="INERT-v1")
    monkeypatch.setenv("PYFOLDABLE_PROVIDER_STORE", str(root))

    def forbidden(*a, **k):
        raise AssertionError("Unexpected genuine provider or banner")
    monkeypatch.setattr(xfoil.XfoilProvider, "generate", forbidden)
    monkeypatch.setattr(xfoil, "_discover_backend_version", forbidden)
    return root, versions


def bem(monkeypatch, fail=False):
    calls = []
    def solve(blade, condition, families, *, settings, bounds):
        calls.append((blade, condition, settings, bounds))
        assert bounds == "error"
        if fail:
            raise ValueError("INERT BEM failure")
        count = settings.annulus_count
        lo, hi = [blade.radius_m * blade.stations[i].r_over_R for i in (0, -1)]
        width = (hi - lo) / count
        profile, family = next(iter(families.items()))
        omega = condition.angular_speed_rad_s
        sound_speed = math.sqrt(1.4 * 287.05 * condition.temperature_k)
        elems = []
        for i in range(count):
            inner, outer = lo + i*width, lo + (i+1)*width
            station, extended = _interpolate_station(blade, .5 * (inner + outer))
            radius = station.r_over_R * blade.radius_m
            speed = math.hypot(condition.forward_speed_m_s, omega * radius)
            phi = math.atan2(condition.forward_speed_m_s, omega * radius)
            alpha = station.twist_rad - phi
            re = condition.air_density_kg_m3 * speed * station.chord_m / condition.dynamic_viscosity_pa_s
            mach = speed / sound_speed
            query = family.query(alpha_rad=alpha, reynolds=re, mach=mach, bounds=bounds)
            correction = settings.annulus_settings.rotational_augmentation.apply(
                alpha, query.cl, query.cd, chord_over_radius=station.chord_m/radius)
            circulation = .5 * speed * station.chord_m * correction.cl
            local = BEMAnnulusResult(
                schema_version=BEM_ANNULUS_SCHEMA_VERSION, operating_condition_id=condition.id,
                airfoil_id=profile, scenario_id=family.scenario_id, polar_bounds=bounds,
                settings=settings.annulus_settings, radius_m=radius, r_over_R=station.r_over_R,
                chord_m=station.chord_m, twist_rad=station.twist_rad,
                loading_regime="positive" if circulation else "zero", iterations=0,
                psi_rad=phi, inflow_angle_rad=phi, angle_of_attack_rad=alpha,
                axial_induced_velocity_m_s=0., tangential_induced_velocity_m_s=0.,
                relative_speed_m_s=speed, reynolds=re, mach=mach, cl=correction.cl, cd=correction.cd,
                raw_polar_cl=query.cl, raw_polar_cd=query.cd, rotational_augmentation=correction.as_mapping(),
                circulation_m2_s=circulation, tip_loss_factor=1., root_loss_factor=1., combined_loss_factor=1.,
                differential_thrust_n_m=1.25/(hi-lo), differential_torque_nm_m=.01/(hi-lo), residual_m2_s=0.,
                polar_sources=query.sources, interpolated_dimensions=query.interpolated_dimensions,
                clamped_dimensions=query.clamped_dimensions,
                polar_query_envelope=BEMPolarQueryEnvelope.from_queries((query,)),
            )
            elems.append(BEMRotorElement(i, inner, outer, extended, local))
        env = BEMPolarQueryEnvelope.combine(tuple(e.solution.polar_query_envelope for e in elems))
        thrust, torque = math.fsum(e.thrust_n for e in elems), math.fsum(e.torque_nm for e in elems)
        power = torque * omega
        n = omega / (2*math.pi)
        d = blade.diameter_m
        force_scale = condition.air_density_kg_m3 * n**2 * d**4
        power_scale = condition.air_density_kg_m3 * n**3 * d**5
        return BEMRotorResult(
            BEM_ROTOR_SCHEMA_VERSION, condition.id, profile, family.scenario_id,
            settings.radial_domain, lo, hi, False, bounds, settings, tuple(elems), thrust, torque, power,
            thrust/force_scale, torque/(force_scale*d), power/power_scale,
            condition.forward_speed_m_s*thrust/power if condition.forward_speed_m_s > 0 else None,
            0., env.sources, env.interpolated_dimensions, env.clamped_dimensions, env,
        )
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", solve)
    return calls


def mechanism(monkeypatch, *, contact=False):
    """Serialize a synthetic PY-05 sample history; never integrate dynamics."""
    calls = []
    def inert(request):
        calls.append(request)
        d = request.drive
        stop_time = d.time_s[-1]/2 if contact else d.time_s[-1]
        n = math.ceil(stop_time / request.controls.max_step_s)
        times = tuple(stop_time*i/n for i in range(n)) + (stop_time,)
        rpm = tuple(d.rpm[0] + t/d.time_s[-1]*(d.rpm[-1]-d.rpm[0]) for t in times)
        angles = (request.initial_angle_rad,) * len(times)
        velocity = (request.initial_angular_velocity_rad_s,) * len(times)
        event = None
        if contact:
            angles = (*angles[:-1], request.parameters.upper_stop_rad)
            event = StopContact("upper", stop_time, angles[-1], velocity[-1])
        return TransientResult(**{
            f.name: (0.,)*len(times) for f in fields(TransientResult)
            if f.name not in {"status", "message", "contact", "segment_start_indices"}
        } | {
            "status": "stop_contact" if contact else "completed", "message": "INERT fixture",
            "time_s": times, "rpm": rpm, "omega_rad_s": tuple(r*RPM_TO_RAD_S for r in rpm),
            "angle_rad": angles, "angular_velocity_rad_s": velocity,
            "segment_start_indices": (0,), "contact": event,
        })
    monkeypatch.setattr(mech, "solve_mechanism_transient", inert)
    return calls
