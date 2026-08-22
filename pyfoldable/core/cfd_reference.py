"""Published CFD context with explicit evidence and qualification boundaries."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping


CFD_REFERENCE_SCHEMA_VERSION = 1
CFDEvidenceForm = Literal["tabulated", "figure_only", "methodology_only"]
CFDGeometryMatch = Literal["exact", "different_pitch"]


class CFDReferenceError(ValueError):
    """Raised when published CFD context is ambiguous or over-promoted."""


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CFDReferenceError(f"{name} must be non-empty text.")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CFDReferenceError(f"{name} must be numeric and not boolean.")
    result = float(value)
    if not math.isfinite(result):
        raise CFDReferenceError(f"{name} must be finite.")
    return result


@dataclass(frozen=True)
class CFDReferenceSource:
    """One citable publication and the maximum evidence it can supply."""

    id: str
    title: str
    authors: str
    year: int
    url: str
    geometry_match: CFDGeometryMatch
    evidence_form: CFDEvidenceForm
    solver: str
    result_scope: str
    rights_scope: str
    doi: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "id",
            "title",
            "authors",
            "url",
            "solver",
            "result_scope",
            "rights_scope",
        ):
            _required_text(name, getattr(self, name))
        if not isinstance(self.year, int) or isinstance(self.year, bool):
            raise CFDReferenceError("source year must be an integer.")
        if self.geometry_match not in {"exact", "different_pitch"}:
            raise CFDReferenceError("source geometry_match is unsupported.")
        if self.evidence_form not in {
            "tabulated",
            "figure_only",
            "methodology_only",
        }:
            raise CFDReferenceError("source evidence_form is unsupported.")


@dataclass(frozen=True)
class CFDReferencePoint:
    """A numeric fact transcribed from a tabulated primary source."""

    id: str
    source_id: str
    quantity: str
    value: float
    rpm: float
    evidence_form: str
    qualification_eligible: bool
    cells: int | None = None
    turbulence_model: str | None = None
    y_plus_min: float | None = None
    y_plus_max: float | None = None
    reported_deviation_percent: float | None = None
    statistic: str | None = None

    def __post_init__(self) -> None:
        for name in ("id", "source_id", "quantity", "evidence_form"):
            _required_text(name, getattr(self, name))
        _finite("value", self.value)
        if _finite("rpm", self.rpm) <= 0.0:
            raise CFDReferenceError("rpm must be greater than zero.")
        if self.evidence_form != "tabulated":
            raise CFDReferenceError("Numeric CFD points must be tabulated.")
        if self.qualification_eligible:
            raise CFDReferenceError(
                "Published CFD context cannot be physical qualification evidence."
            )
        if self.cells is not None and (
            not isinstance(self.cells, int)
            or isinstance(self.cells, bool)
            or self.cells <= 0
        ):
            raise CFDReferenceError("cells must be a positive integer.")
        for name in (
            "y_plus_min",
            "y_plus_max",
            "reported_deviation_percent",
        ):
            value = getattr(self, name)
            if value is not None:
                _finite(name, value)
        if (
            self.y_plus_min is not None
            and self.y_plus_max is not None
            and self.y_plus_max < self.y_plus_min
        ):
            raise CFDReferenceError("y-plus bounds are reversed.")

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            name: value
            for name, value in vars(self).items()
            if value is not None
        }


@dataclass(frozen=True)
class CFDReferenceFixture:
    """Strict literature fixture that cannot masquerade as project review."""

    id: str
    target_geometry_id: str
    rights_scope: str
    independent_project_review: bool
    qualification: str
    sources: tuple[CFDReferenceSource, ...]
    points: tuple[CFDReferencePoint, ...]

    def __post_init__(self) -> None:
        for name in ("id", "target_geometry_id", "rights_scope"):
            _required_text(name, getattr(self, name))
        if self.independent_project_review:
            raise CFDReferenceError(
                "Published literature cannot satisfy independent project review."
            )
        if self.qualification != "model_form_context_only":
            raise CFDReferenceError(
                "Published CFD qualification must remain model_form_context_only."
            )
        source_ids = tuple(source.id for source in self.sources)
        if not source_ids or len(source_ids) != len(set(source_ids)):
            raise CFDReferenceError("CFD source ids must be non-empty and unique.")
        point_ids = tuple(point.id for point in self.points)
        if not point_ids or len(point_ids) != len(set(point_ids)):
            raise CFDReferenceError("CFD point ids must be non-empty and unique.")
        sources = {source.id: source for source in self.sources}
        for point in self.points:
            source = sources.get(point.source_id)
            if source is None:
                raise CFDReferenceError("Every CFD point must name a declared source.")
            if source.evidence_form != "tabulated":
                raise CFDReferenceError(
                    "A figure-only or methodology-only source cannot supply numeric points."
                )
            if source.geometry_match != "exact":
                raise CFDReferenceError(
                    "A different-pitch source cannot supply target numeric points."
                )


def load_cfd_reference_fixture(path: str | Path) -> CFDReferenceFixture:
    """Load factual publication metadata without importing copyrighted figures."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != CFD_REFERENCE_SCHEMA_VERSION:
        raise CFDReferenceError("Unsupported CFD reference schema_version.")
    sources = tuple(
        CFDReferenceSource(**source) for source in payload.get("sources", ())
    )
    points = tuple(
        CFDReferencePoint(**point) for point in payload.get("points", ())
    )
    return CFDReferenceFixture(
        id=payload.get("id", ""),
        target_geometry_id=payload.get("target_geometry_id", ""),
        rights_scope=payload.get("rights_scope", ""),
        independent_project_review=payload.get("independent_project_review", False),
        qualification=payload.get("qualification", ""),
        sources=sources,
        points=points,
    )
