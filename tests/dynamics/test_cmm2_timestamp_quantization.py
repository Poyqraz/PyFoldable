"""Amended timestamp selection. Historical old-policy results stay recorded."""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate._ivp.radau import RadauDenseOutput

from pyfoldable.dynamics.cmm2_radau_dense import (
    RadauContractFailure,
    _adjacent_timestamp_order,
    first_radau_contact,
)

HISTORICAL_OLD_POLICY_C2V07 = "CMM-2 contact time conversion is unresolved."


def _archived_dense():
    repository = Path(__file__).resolve().parents[2]
    replay = json.loads(
        (repository / "reports" / "c2v07_representability" / "coefficient_replay_inputs.json").read_text(
            encoding="utf-8"
        )
    )

    def hex_float(text: str) -> float:
        return float.fromhex(text)

    y_old = np.array([hex_float(value) for value in replay["y_old_hex"]])
    q_matrix = np.array([[hex_float(value) for value in row] for row in replay["Q_hex"]])
    t_old = hex_float(replay["t_old_hex"])
    step = hex_float(replay["h_hex"])
    dense = RadauDenseOutput(t_old, t_old + step, y_old, q_matrix)
    return replay, dense


class _Parameters:
    lower_stop_rad = -0.5
    upper_stop_rad = 0.2


class _Controls:
    atol = 1.0e-8
    atol_angular_velocity_rad_s = 1.0e-8


def test_archived_c2v07_cubic_is_distinct_from_its_old_policy_failure() -> None:
    replay, dense = _archived_dense()
    assert HISTORICAL_OLD_POLICY_C2V07 == "CMM-2 contact time conversion is unresolved."
    hit = first_radau_contact(
        dense,
        replay["start"],
        replay["end"],
        dense(replay["start"]),
        dense(replay["end"]),
        _Parameters(),
        _Controls(),
        origin=replay["origin"],
        last_published=replay["last_published"],
    )
    assert hit is not None
    assert hit[0] == "lower"


def test_exact_representable_time_has_one_neighbor() -> None:
    ordered = _adjacent_timestamp_order(Fraction(1, 2))
    assert ordered == [0.5]


def test_nonrepresentable_time_uses_nearest_even_then_the_other_neighbor() -> None:
    down = 1.0
    up = math.nextafter(1.0, math.inf)
    midpoint = (Fraction.from_float(down) + Fraction.from_float(up)) / 2
    ordered = _adjacent_timestamp_order(midpoint)
    assert ordered == [down, up]
    assert math.nextafter(ordered[0], math.inf) == ordered[1]


def test_one_third_neighbors_are_the_contract_pair_in_nearest_first_order() -> None:
    nearest = float.fromhex("0x1.5555555555555p-2")
    upper = float.fromhex("0x1.5555555555556p-2")
    ordered = _adjacent_timestamp_order(Fraction(1, 3))
    assert ordered == [nearest, upper]
