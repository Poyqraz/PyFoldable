"""Explicitly inert store/caller support. Never normal deployment data."""
from dataclasses import replace
from types import SimpleNamespace

from pyfoldable.application import design_analysis, provider_design_analysis as managed
from pyfoldable.application.provider_record_store import ProviderRecordStore
from pyfoldable.core.providers import ProviderIdentity
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.providers import xfoil
from examples.research_reference_data import make_plan, request_grid
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
        env = {"query_count": 0, "note": "INERT NOT A SOLVER", "clamped_dimensions": []}
        elems = []
        for i in range(count):
            s = {"settings": settings.annulus_settings.as_mapping(), "polar_query_envelope": env,
                 "radius_m": lo+(i+.5)*width, "r_over_R": (lo+(i+.5)*width)/blade.radius_m,
                 "chord_m": .05, "twist_rad": .1, "angle_of_attack_rad": .05,
                 "reynolds": 200000., "mach": .2, "cl": .8, "cd": .02,
                 "differential_thrust_n_m": 1.25/(hi-lo), "differential_torque_nm_m": .01/(hi-lo)}
            elems.append({"index": i, "inner_radius_m": lo+i*width, "outer_radius_m": lo+(i+1)*width,
                          "solution": s, "thrust_n": 1.25/count, "torque_nm": .01/count})
        result = {"airfoil_id": next(iter(families)), "thrust_n": 1.25, "torque_nm": .01,
                  "shaft_power_w": .01*condition.angular_speed_rad_s, "annulus_count": count,
                  "inner_radius_m": lo, "outer_radius_m": hi, "settings": settings.as_mapping(),
                  "polar_bounds": bounds, "polar_query_envelope": env, "elements": elems}
        return SimpleNamespace(as_mapping=lambda: result)
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", solve)
    return calls
