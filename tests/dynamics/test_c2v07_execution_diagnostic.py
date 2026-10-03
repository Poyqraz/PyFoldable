"""Focused checks for the C2V-07 execution diagnostic. Not an acceptance gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pyfoldable.dynamics.cmm2_coupled_transient as cmm2_dynamics


def _load():
    path = Path(__file__).resolve().parent / "c2v07_execution_diagnostic.py"
    spec = importlib.util.spec_from_file_location("c2v07_execution_diagnostic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archived_failure_replay_is_stable_and_capture_replays_match_live() -> None:
    diagnostic = _load()
    original = cmm2_dynamics.first_radau_contact
    archived = diagnostic.archived_failure_interval()
    historical = "CMM-2 contact time conversion is unresolved."
    first = diagnostic.replay_interval(archived)
    second = diagnostic.replay_interval(archived)
    assert first == second
    assert historical == "CMM-2 contact time conversion is unresolved."
    assert first != historical
    captured = diagnostic.capture_c2v07("focused")
    assert cmm2_dynamics.first_radau_contact is original
    assert captured["contacts"]
    for row in captured["contacts"]:
        assert row["y_old_hex"]
        assert row["Q_hex"]
        assert row["t_old_hex"]
        assert row["h_hex"]
        assert diagnostic.replay_interval(row) == row["classification"]
        if diagnostic.compare_inputs(row, archived):
            assert diagnostic.replay_interval(row) == first
