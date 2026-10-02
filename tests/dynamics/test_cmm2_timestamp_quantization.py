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
    AcceptedIntervalWork,
    RadauContractFailure,
    RadauDomainExit,
    RootBudget,
    _Root,
    _adjacent_timestamp_order,
    _convert_root,
    _rn64,
    _rounding_cell,
    audit_represented_domain,
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


def test_subnormal_tie_rounds_to_the_even_neighbor() -> None:
    odd = float.fromhex("0x0.0000000000001p-1022")
    even = float.fromhex("0x0.0000000000002p-1022")
    midpoint = (Fraction.from_float(odd) + Fraction.from_float(even)) / 2
    assert _adjacent_timestamp_order(midpoint)[0] == even
    assert _rn64(midpoint) == even


def test_root_time_uses_the_binary64_allowance_not_a_wider_rational() -> None:
    radius = (Fraction.from_float(1e-14) + Fraction(1, 10**14)) / 2
    root = _Root(left=-radius, right=radius, exact=None, anchor=Fraction(0))
    budget = RootBudget(800)
    _convert_root(
        0.0,
        None,
        Fraction(0),
        Fraction(1),
        root,
        (Fraction(0), Fraction(1)),
        (Fraction(0),),
        Fraction(1, 10**8),
        True,
        0.0,
        1.0,
        budget,
    )
    assert budget.refinements > 0


class _WideStops:
    lower_stop_rad = 0.0
    upper_stop_rad = 1.2


def test_public_relative_presnap_rejects_the_large_origin_witness() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 0] = -1.0
    dense = RadauDenseOutput(0.0, 1.0, np.array([0.501, -1.0, 40.0]), q_matrix)
    origin = 2.0**44
    with pytest.raises(RadauContractFailure, match="pre-snap"):
        first_radau_contact(
            dense,
            0.0,
            1.0,
            dense(0.0),
            dense(1.0),
            _WideStops(),
            _Controls(),
            origin=origin,
            last_published=origin,
        )


def test_retained_enclosure_extent_is_a_domain_exit() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 1] = -1.0
    q_matrix[2, 0] = -1.0
    dense = RadauDenseOutput(
        0.0,
        1.0,
        np.array([0.6, -1.0, float.fromhex("0x1.67e3eb57cc763p+3")]),
        q_matrix,
    )
    work = AcceptedIntervalWork.create()
    hit = first_radau_contact(
        dense,
        0.0,
        1.0,
        dense(0.0),
        dense(1.0),
        _WideStops(),
        _Controls(),
        origin=0.0,
        last_published=0.0,
        work=work,
    )
    assert hit is not None
    retained_right = Fraction(54507394858725, 2**46)
    assert hit[4].audit_extent == retained_right
    assert work.contact.required_audit_time == retained_right
    contact_used = work.contact.used
    with pytest.raises(RadauDomainExit):
        audit_represented_domain(
            dense,
            0.0,
            hit[1],
            deployed_angle=0.0,
            origin=0.0,
            evaluation_time=hit[1],
            work=work,
        )
    assert work.contact.used == contact_used
    assert work.domain.used > 0


def test_archived_cubic_exposes_the_actual_selection_certificate() -> None:
    replay, dense = _archived_dense()
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
    certificate = hit[4]
    selected = float.fromhex("0x1.7fffffffff83ap-1")
    assert certificate.selected_relative.hex() == selected.hex()
    assert certificate.selected_public.hex() == selected.hex()
    assert certificate.z == Fraction(52776558117645, 140737488355328)
    assert certificate.radius == Fraction(1, 2**47)
    assert certificate.root_time == Fraction(9007199254741, 2**99)
    assert certificate.q_r == Fraction(30540034973231, 2**99)
    assert certificate.q_p == 0
    width = replay["end"] - replay["start"]
    xi = (selected - replay["start"]) / width
    assert certificate.allowance == Fraction.from_float(width * (1e-14 + 1e-14 * abs(xi)))
    assert certificate.allowance_width == width
    assert certificate.allowance_xi == xi
    assert certificate.selected_option == 0
    assert certificate.relative_cell.lower == Fraction(13510798882107507, 2**54)
    assert certificate.relative_cell.upper == Fraction(13510798882107509, 2**54)
    assert certificate.relative_cell.lower_included
    assert certificate.relative_cell.upper_included
    assert certificate.relative_cell.contains(certificate.relative_target)
    assert certificate.public_cell.contains(certificate.public_target)


def test_rounding_cells_cover_singleton_exponent_boundary_and_subnormals() -> None:
    half = _rounding_cell(0.5)
    assert half.contains(Fraction(1, 2))
    assert half.lower_included and half.upper_included
    assert half.lower == (Fraction.from_float(math.nextafter(0.5, 0.0)) + Fraction(1, 2)) / 2
    assert half.upper == (Fraction(1, 2) + Fraction.from_float(math.nextafter(0.5, math.inf))) / 2

    boundary = _rounding_cell(1.0)
    assert boundary.lower_included and boundary.upper_included
    assert Fraction(1) - boundary.lower == Fraction(1, 2**54)
    assert boundary.upper - Fraction(1) == Fraction(1, 2**53)
    assert boundary.contains(Fraction(1))
    successor = math.nextafter(1.0, math.inf)
    successor_cell = _rounding_cell(successor)
    assert not successor_cell.lower_included and not successor_cell.upper_included
    assert not successor_cell.contains(boundary.upper)

    odd = float.fromhex("0x0.0000000000001p-1022")
    even = float.fromhex("0x0.0000000000002p-1022")
    midpoint = (Fraction.from_float(odd) + Fraction.from_float(even)) / 2
    odd_cell = _rounding_cell(odd)
    even_cell = _rounding_cell(even)
    assert not odd_cell.lower_included and not odd_cell.upper_included
    assert even_cell.lower_included and even_cell.upper_included
    assert even_cell.contains(midpoint)
    assert not odd_cell.contains(midpoint)
    zero = _rounding_cell(0.0)
    assert zero.lower_included and zero.upper_included
    assert zero.contains(Fraction(0))


def test_exact_half_conversion_records_its_singleton_cell() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 0] = -1.0
    dense = RadauDenseOutput(0.0, 1.0, np.array([0.5, -1.0, 40.0]), q_matrix)
    hit = first_radau_contact(
        dense,
        0.0,
        1.0,
        dense(0.0),
        dense(1.0),
        _WideStops(),
        _Controls(),
        origin=0.0,
        last_published=0.0,
    )
    certificate = hit[4]
    assert certificate.neighbors == (0.5,)
    assert certificate.selected_option == 0
    assert certificate.relative_target == Fraction(1, 2)
    assert certificate.relative_cell.contains(certificate.relative_target)
    assert certificate.public_cell.contains(certificate.public_target)


def test_one_third_neighbors_are_the_contract_pair_in_nearest_first_order() -> None:
    nearest = float.fromhex("0x1.5555555555555p-2")
    upper = float.fromhex("0x1.5555555555556p-2")
    ordered = _adjacent_timestamp_order(Fraction(1, 3))
    assert ordered == [nearest, upper]
