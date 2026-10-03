"""Pinned C2V-09 identity is checked before any motor, BEM, or mapper call."""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path

import pytest

from pyfoldable.application.cmm2_coupled_transient_service import (
    Pr07MotorEvaluator,
    map_foldable_bem_aero_loads,
    solve_foldable_bem_rotor,
)
from pyfoldable.application.design_draft import build_design_draft
from pyfoldable.application.mechanism_binding import RadialMassSample, TipMassDistribution
from pyfoldable.core.models import PolarTable
from pyfoldable.core.polar import PolarFamily
from pyfoldable.core.polar_spanwise import SpanwisePolarAnchor, SpanwisePolarSchedule


def _load(relative: str, name: str):
    path = Path(__file__).resolve().parents[1] / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_evidence = _load("c2v09_evidence.py", "c2v09_evidence")
_preflight = _load("dynamics/test_cmm2_c2v09_preflight.py", "c2v09_preflight_identity")
_service = _load("application/test_cmm2_coupled_transient_service.py", "c2v09_service_identity")


class _SourceCalls:
    def __init__(self) -> None:
        self.count = 0

    def note(self, function):
        def wrapped(*args, **kwargs):
            self.count += 1
            return function(*args, **kwargs)

        return wrapped


@pytest.fixture
def source_calls(monkeypatch):
    calls = _SourceCalls()
    service = __import__(
        "pyfoldable.application.cmm2_coupled_transient_service",
        fromlist=["solve_foldable_bem_rotor"],
    )
    monkeypatch.setattr(service, "solve_foldable_bem_rotor", calls.note(solve_foldable_bem_rotor))
    monkeypatch.setattr(service, "map_foldable_bem_aero_loads", calls.note(map_foldable_bem_aero_loads))
    monkeypatch.setattr(Pr07MotorEvaluator, "__call__", calls.note(Pr07MotorEvaluator.__call__))
    return calls


def _pinned_base():
    manifest = _evidence.load_full_manifest()
    return manifest["c2v09_candidates"][0]


def _gate(sealed) -> None:
    pinned = _pinned_base()
    _evidence.assert_matches_pinned_candidate(
        _evidence.project_executed_candidate(sealed, pinned),
        pinned,
    )
    _preflight._phase_b(sealed)


def _assert_rejected_before_source(sealed, source_calls, message: str) -> None:
    with pytest.raises(AssertionError, match=message):
        _gate(sealed)
    assert source_calls.count == 0


def test_additional_mass_sample_is_rejected_before_source_evaluation(source_calls) -> None:
    first = _service._mass().samples[0]
    extra = RadialMassSample(0.02, 0.01, "synthetic tip mass")
    distribution = TipMassDistribution(
        (first, extra),
        "synthetic-tip",
        "synthetic_test_fixture",
    )
    sealed = _service._binding(distribution=distribution)
    _assert_rejected_before_source(sealed, source_calls, "one mass sample")


def test_additional_polar_table_is_rejected_before_source_evaluation(source_calls) -> None:
    original = _service._family(0.6).tables[0]
    extra = PolarTable(
        airfoil_id=original.airfoil_id,
        scenario_id=original.scenario_id,
        reynolds=2.0e5,
        mach=original.mach,
        alpha_rad=original.alpha_rad,
        cl=original.cl,
        cd=original.cd,
        cm=original.cm,
        source=original.source,
        metadata=dict(original.metadata),
    )
    family = PolarFamily((original, extra))
    schedule = SpanwisePolarSchedule(
        "cmm2-span",
        (
            SpanwisePolarAnchor(0.2, family),
            SpanwisePolarAnchor(1.0, family),
        ),
    )
    sealed = _service._binding(polars=schedule)
    _assert_rejected_before_source(sealed, source_calls, "one polar table")


def test_changed_sealed_draft_is_rejected_before_source_evaluation(source_calls) -> None:
    sealed = _service._binding()
    changed_inputs = dataclasses.replace(_service._draft_inputs(), diameter="221 mm")
    changed = build_design_draft(_service.CANONICAL, changed_inputs)
    sealed = dataclasses.replace(sealed, draft=changed)
    _assert_rejected_before_source(sealed, source_calls, "Sealed draft")
