"""Fail-closed dashboard snapshot assembled from versioned project evidence."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

try:  # pragma: no cover - exercised by Python 3.10 CI
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from pyfoldable.core.config import load_design_config
from pyfoldable.core.units import normalize_quantity


class DashboardConfigError(ValueError):
    """Raised when dashboard metadata disagrees with its bound evidence."""


class EvidenceState(str, Enum):
    QUALIFIED = "qualified"
    SCREENING_ONLY = "screening_only"
    PENDING = "pending"
    FAILED = "failed"
    BLOCKED = "blocked"

    @property
    def label_tr(self) -> str:
        return {
            EvidenceState.QUALIFIED: "Nitelikli",
            EvidenceState.SCREENING_ONLY: "Tarama amaçlı",
            EvidenceState.PENDING: "Bekliyor",
            EvidenceState.FAILED: "Başarısız",
            EvidenceState.BLOCKED: "Bloklu",
        }[self]


@dataclass(frozen=True)
class EvidenceGate:
    id: str
    title: str
    state: EvidenceState
    summary: str
    evidence_path: Path
    evidence_sha256: str
    decision: str


@dataclass(frozen=True)
class BladeStationView:
    r_over_R: float
    chord_m: float
    twist_deg: float
    airfoil_id: str


@dataclass(frozen=True)
class OperatingConditionView:
    id: str
    rpm: float
    forward_speed_m_s: float
    air_density_kg_m3: float
    dynamic_viscosity_pa_s: float
    temperature_k: float
    pressure_pa: float


@dataclass(frozen=True)
class DashboardSnapshot:
    design_id: str
    design_description: str
    open_diameter_m: float
    stowed_envelope_m: float
    checkpoint_rpm: float
    blade_count: int
    hub_radius_m: float
    hinge_radius_m: float
    blade_stations: tuple[BladeStationView, ...]
    operating_conditions: tuple[OperatingConditionView, ...]
    design_path: Path
    design_sha256: str
    manifest_sha256: str
    qualification_warning: str
    gates: tuple[EvidenceGate, ...]


def _load_toml(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("rb") as stream:
            document = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise DashboardConfigError(f"Cannot load dashboard manifest {path}: {exc}") from exc
    if not isinstance(document, Mapping):
        raise DashboardConfigError("Dashboard manifest root must be a table.")
    return document


def _inside_repo(repo_root: Path, raw_path: object, *, field: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise DashboardConfigError(f"{field} must be a non-empty repository-relative path.")
    path = (repo_root / raw_path).resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise DashboardConfigError(f"{field} must remain inside the repository.") from exc
    if not path.is_file():
        raise DashboardConfigError(f"{field} does not exist: {raw_path}")
    return path


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardConfigError(f"Cannot load evidence {path}: {exc}") from exc
    if not isinstance(document, Mapping):
        raise DashboardConfigError(f"Evidence root must be an object: {path}")
    return document


def _required_string(row: Mapping[str, Any], field: str, *, context: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DashboardConfigError(f"{context}.{field} must be a non-empty string.")
    return value.strip()


def load_dashboard_snapshot(
    repo_root: str | Path,
    *,
    manifest_path: str | Path | None = None,
) -> DashboardSnapshot:
    """Load the UI snapshot without allowing labels to outrun evidence."""
    root = Path(repo_root).resolve()
    manifest = (
        Path(manifest_path)
        if manifest_path is not None
        else root / "configs/ui/dashboard.toml"
    )
    document = _load_toml(manifest)
    if document.get("schema_version") != 1:
        raise DashboardConfigError("Dashboard manifest schema_version must be 1.")

    design_path = _inside_repo(root, document.get("design_config"), field="design_config")
    design = load_design_config(design_path)
    warning = _required_string(document, "qualification_warning", context="dashboard")

    stowed_raw = design.metadata.get("stowed_envelope_requirement")
    try:
        stowed_envelope_m = normalize_quantity(
            stowed_raw,
            "length",
            field="metadata.stowed_envelope_requirement",
        ).si_value
    except ValueError as exc:
        raise DashboardConfigError(str(exc)) from exc

    if not design.operating_conditions:
        raise DashboardConfigError("Canonical design must define an operating condition.")
    if design.hinge is None:
        raise DashboardConfigError("Canonical foldable design must define hinge geometry.")
    checkpoint_rpm = design.operating_conditions[0].angular_speed_rad_s * 60.0 / (2.0 * math.pi)

    raw_gates = document.get("gates")
    if not isinstance(raw_gates, list) or not raw_gates:
        raise DashboardConfigError("Dashboard manifest must define at least one gate.")

    gates: list[EvidenceGate] = []
    seen_ids: set[str] = set()
    for index, raw_gate in enumerate(raw_gates):
        if not isinstance(raw_gate, Mapping):
            raise DashboardConfigError(f"gates[{index}] must be a table.")
        context = f"gates[{index}]"
        gate_id = _required_string(raw_gate, "id", context=context)
        if gate_id in seen_ids:
            raise DashboardConfigError(f"Duplicate dashboard gate id: {gate_id}")
        seen_ids.add(gate_id)
        try:
            state = EvidenceState(_required_string(raw_gate, "state", context=context))
        except ValueError as exc:
            raise DashboardConfigError(f"Unsupported evidence state for {gate_id}.") from exc

        evidence_path = _inside_repo(
            root,
            raw_gate.get("evidence_path"),
            field=f"{context}.evidence_path",
        )
        evidence = _read_json(evidence_path)
        evidence_sha256 = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        decision_key = _required_string(raw_gate, "decision_key", context=context)
        actual_decision = evidence.get(decision_key)
        expected_decision = _required_string(raw_gate, "expected_decision", context=context)
        if actual_decision != expected_decision:
            raise DashboardConfigError(
                f"{gate_id} expected decision {expected_decision!r}, got {actual_decision!r}."
            )
        if state is EvidenceState.QUALIFIED and evidence.get("passed") is not True:
            raise DashboardConfigError(
                f"{gate_id} cannot be marked qualified without passed=true evidence."
            )

        gates.append(
            EvidenceGate(
                id=gate_id,
                title=_required_string(raw_gate, "title", context=context),
                state=state,
                summary=_required_string(raw_gate, "summary", context=context),
                evidence_path=evidence_path,
                evidence_sha256=evidence_sha256,
                decision=actual_decision,
            )
        )

    return DashboardSnapshot(
        design_id=design.id,
        design_description=design.description,
        open_diameter_m=design.blade.diameter_m,
        stowed_envelope_m=stowed_envelope_m,
        checkpoint_rpm=checkpoint_rpm,
        blade_count=design.blade.blade_count,
        hub_radius_m=design.blade.hub_radius_m,
        hinge_radius_m=design.hinge.radius_m,
        blade_stations=tuple(
            BladeStationView(
                r_over_R=station.r_over_R,
                chord_m=station.chord_m,
                twist_deg=math.degrees(station.twist_rad),
                airfoil_id=station.airfoil_id,
            )
            for station in design.blade.stations
        ),
        operating_conditions=tuple(
            OperatingConditionView(
                id=condition.id,
                rpm=condition.angular_speed_rad_s * 60.0 / (2.0 * math.pi),
                forward_speed_m_s=condition.forward_speed_m_s,
                air_density_kg_m3=condition.air_density_kg_m3,
                dynamic_viscosity_pa_s=condition.dynamic_viscosity_pa_s,
                temperature_k=condition.temperature_k,
                pressure_pa=condition.pressure_pa,
            )
            for condition in design.operating_conditions
        ),
        design_path=design_path,
        design_sha256=hashlib.sha256(design_path.read_bytes()).hexdigest(),
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        qualification_warning=warning,
        gates=tuple(gates),
    )
