"""Strict polar-family configuration and runtime binding tests."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from pyfoldable.core import (
    POLAR_CONFIG_SCHEMA_VERSION,
    PolarConfigError,
    PolarGenerationResult,
    PolarPointResult,
    ProviderCapabilities,
    ProviderIdentity,
    load_polar_family_config,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_CONFIG = (
    PROJECT_ROOT / "configs" / "polars" / "PYFOLDABLE_DEMO_FAMILY.toml"
)
CAPABILITIES = ProviderCapabilities(
    supports_mach=True,
    supports_n_crit=True,
    supports_forced_transition=True,
    supports_pointwise_confidence=False,
    supports_partial_results=True,
    supports_vectorized_alpha=True,
    supports_iteration_limit=True,
    supports_timeout=True,
)


class ConfiguredProvider:
    capabilities = CAPABILITIES

    def __init__(self, name: str) -> None:
        self.identity = ProviderIdentity(name, "1", "fixture", "1")
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        return PolarGenerationResult(
            request=request,
            provider=self.identity,
            points=tuple(
                PolarPointResult(
                    alpha,
                    "converged",
                    cl=10.0 * alpha,
                    cd=0.01 + alpha * alpha,
                    cm=-0.02,
                )
                for alpha in request.alpha_rad
            ),
            elapsed_s=0.0,
        )


def _copy_config(tmp_path: Path, transform=lambda text: text) -> Path:
    config_dir = tmp_path / "polars"
    airfoil_dir = tmp_path / "airfoils"
    config_dir.mkdir()
    airfoil_dir.mkdir()
    source_airfoil = PROJECT_ROOT / "configs" / "airfoils" / "PYFOLDABLE_DEMO.dat"
    (airfoil_dir / source_airfoil.name).write_text(
        source_airfoil.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    text = REFERENCE_CONFIG.read_text(encoding="utf-8")
    text = text.replace("../../.cache/polars", "../.cache/polars")
    path = config_dir / "family.toml"
    path.write_text(transform(text), encoding="utf-8")
    return path


def test_reference_config_binds_every_runtime_policy_without_loading_backends() -> None:
    config = load_polar_family_config(REFERENCE_CONFIG)

    assert POLAR_CONFIG_SCHEMA_VERSION == 1
    assert config.source_path == REFERENCE_CONFIG.resolve()
    assert config.source_sha256 == hashlib.sha256(
        REFERENCE_CONFIG.read_bytes()
    ).hexdigest()
    assert config.plan.cell_count == 3
    assert config.plan.request_template.airfoil.id == "PYFOLDABLE_DEMO"
    assert config.plan.request_template.alpha_rad == pytest.approx(
        tuple(math.radians(value) for value in (-10, -5, 0, 5, 10))
    )
    assert config.plan.reynolds_grid == (100_000.0, 200_000.0, 400_000.0)
    assert config.plan.mach_grid == (0.0,)
    assert tuple(provider.kind for provider in config.providers) == (
        "xfoil",
        "neuralfoil",
    )
    assert config.retry_policy.initial_backoff_s == pytest.approx(0.05)
    assert config.cache.enabled is True
    assert config.cache.root == (PROJECT_ROOT / ".cache" / "polars").resolve()
    assert config.health.enabled is True
    assert config.health.policy.failure_threshold == 3
    assert config.result_policy.minimum_usable_fraction == 1.0
    assert config.batch_policy.failure_mode == "fail_fast"
    assert config.acceptance_criteria.cd.relative == pytest.approx(0.10)
    json.dumps(config.as_mapping(), allow_nan=False)


def test_relative_paths_are_resolved_against_config_not_working_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = _copy_config(tmp_path)
    monkeypatch.chdir(tmp_path.parent)

    config = load_polar_family_config(path)

    assert config.plan.request_template.airfoil.coordinates
    assert config.cache.root == (tmp_path / ".cache" / "polars").resolve()


def test_runtime_factory_binds_services_and_generates_from_config(tmp_path: Path) -> None:
    path = _copy_config(
        tmp_path,
        lambda text: text.replace(
            "reynolds = [100000.0, 200000.0, 400000.0]",
            "reynolds = [100000.0, 200000.0]",
        ),
    )
    config = load_polar_family_config(path)
    built: dict[str, ConfiguredProvider] = {}

    def factory(spec):
        provider = ConfiguredProvider(spec.kind)
        built[spec.kind] = provider
        return provider

    runtime = config.build_runtime({"xfoil": factory, "neuralfoil": factory})
    generated = runtime.generate()

    assert generated.complete is True
    assert generated.family is not None
    assert len(generated.cells) == 2
    assert built["xfoil"].calls == 2
    assert built["neuralfoil"].calls == 0
    assert runtime.cache is not None
    assert runtime.cache.root == (tmp_path / ".cache" / "polars").resolve()
    assert runtime.health_registry.snapshot(built["xfoil"].identity).total_successes == 2


@pytest.mark.parametrize(
    ("transform", "message"),
    [
        (
            lambda text: text.replace(
                "schema_version = 1",
                "schema_version = 1\nunknown_root = true",
                1,
            ),
            "Unknown config field",
        ),
        (
            lambda text: text.replace(
                'scenario_id = "clean"',
                'scenario_id = "clean"\nrequest_options = "forbidden"',
            ),
            "request_options",
        ),
        (
            lambda text: text.replace(
                'version_timeout = "5 s"',
                'version_timeout = "5 s"\nrepanel = true',
            ),
            "repanel",
        ),
        (
            lambda text: text.replace(
                "minimum_usable_fraction = 1.0",
                "minimum_usable_fraction = 0.8",
            ),
            "must be 1.0",
        ),
        (
            lambda text: text.replace(
                "minimum_usable_points = 2",
                "minimum_usable_points = 99",
            ),
            "cannot exceed",
        ),
        (
            lambda text: text.replace(
                'subgrid_policy = "none"',
                'subgrid_policy = "complete_axes"',
            ),
            "subgrid_policy requires",
        ),
        (
            lambda text: text.replace('timeout = "30 s"', "timeout = 30.0"),
            "explicit unit",
        ),
        (
            lambda text: text.replace('root = "../.cache/polars"\n', ""),
            "requires config field cache.root",
        ),
        (
            lambda text: text.replace(
                'enabled = true\nroot = "../.cache/polars"',
                "enabled = false",
                1,
            ),
            "Disabled cache cannot declare cache.lock",
        ),
        (
            lambda text: text.replace(
                "[health]\nenabled = true",
                "[health]\nenabled = false",
            ),
            "Disabled health cannot declare",
        ),
        (
            lambda text: text
            + '\n[[providers]]\nkind = "xfoil"\nexecutable = "other"\n',
            "must not repeat",
        ),
        (
            lambda text: text.replace(
                '[[providers]]\nkind = "xfoil"\nexecutable = "xfoil"\nversion_timeout = "5 s"\n\n',
                "",
            ).replace("mach = [0.0]", "mach = [0.2]"),
            "No configured provider can satisfy",
        ),
    ],
)
def test_loader_rejects_unknown_or_ambiguous_configuration(
    tmp_path: Path,
    transform,
    message: str,
) -> None:
    path = _copy_config(tmp_path, transform)

    with pytest.raises(PolarConfigError, match=message):
        load_polar_family_config(path)


def test_runtime_requires_every_configured_factory_and_unique_identities(
    tmp_path: Path,
) -> None:
    config = load_polar_family_config(_copy_config(tmp_path))

    with pytest.raises(PolarConfigError, match="No provider factory"):
        config.build_runtime({})

    def duplicate_factory(spec):
        return ConfiguredProvider("duplicate")

    with pytest.raises(PolarConfigError, match="unique identities"):
        config.build_runtime(
            {"xfoil": duplicate_factory, "neuralfoil": duplicate_factory}
        )


def test_json_root_and_unsupported_extensions_fail_explicitly(tmp_path: Path) -> None:
    json_path = tmp_path / "empty.json"
    json_path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    text_path = tmp_path / "config.txt"
    text_path.write_text("schema_version = 1", encoding="utf-8")

    with pytest.raises(PolarConfigError, match="expected 1"):
        load_polar_family_config(json_path)
    with pytest.raises(PolarConfigError, match="must use .toml or .json"):
        load_polar_family_config(text_path)
