"""CMM-2 cubic dense adapter for SciPy Radau.

The represented step is ``y = y_old + Q @ [x, x**2, x**3]`` with
``x = (t - t_old) / h``. Q is not multiplied by h again. This module does
not accept an RK45 quartic and does not sample its way out of an unresolved
root.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from pyfoldable.dynamics.coupled_transient import FOLD_LIMIT_RAD, OMEGA_MIN


CONTACT_WORK_LIMIT = 800
DOMAIN_WORK_LIMIT = 800
REFINEMENT_LIMIT = 80
ISOLATION_DEPTH_LIMIT = 32
WIDTH_FLOOR = Fraction(1, 1 << 80)
ROOT_XTOL = Fraction(1, 10**14)


class RadauContractFailure(RuntimeError):
    """The cubic adapter cannot prove a closed contact or domain decision."""


class RadauDomainExit(RadauContractFailure):
    """The represented cubic left the CMM-2 model domain."""


@dataclass
class RootBudget:
    """One accepted interval's shared root-work counter."""

    limit: int
    used: int = 0
    refinements: int = 0

    def charge(self, count: int = 1) -> None:
        self.used += count
        if self.used > self.limit:
            raise RadauContractFailure("CMM-2 root-work budget exhausted.")

    def refine(self) -> None:
        self.refinements += 1
        if self.refinements > REFINEMENT_LIMIT:
            raise RadauContractFailure("CMM-2 root refinement limit exhausted.")
        self.charge()


def _as_fraction(value: float) -> Fraction:
    number = float(value)
    if not math.isfinite(number):
        raise RadauContractFailure("CMM-2 Radau coefficient is not finite.")
    return Fraction.from_float(number)


def represented_cubic(dense):
    """Build exact cubics from a genuine RadauDenseOutput."""
    if type(dense).__name__ != "RadauDenseOutput":
        raise RadauContractFailure(
            "CMM-2 dense output representation is not the expected Radau cubic."
        )
    q_matrix = getattr(dense, "Q", None)
    y_old = getattr(dense, "y_old", None)
    step = getattr(dense, "h", None)
    if q_matrix is None or y_old is None or step is None:
        raise RadauContractFailure(
            "CMM-2 dense output representation is not the expected Radau cubic."
        )
    q_matrix = np.asarray(q_matrix, dtype=float)
    y_old = np.asarray(y_old, dtype=float)
    if q_matrix.shape != (3, 3) or y_old.shape != (3,) or getattr(dense, "order", None) != 2:
        raise RadauContractFailure("CMM-2 dense polynomial degree is not the Radau cubic.")
    if (
        not math.isfinite(step)
        or step <= 0.0
        or not np.isfinite(q_matrix).all()
        or not np.isfinite(y_old).all()
        or not math.isfinite(float(dense.t_old))
        or not math.isfinite(float(dense.t))
    ):
        raise RadauContractFailure("CMM-2 Radau cubic is not finite.")
    t_old = _as_fraction(dense.t_old)
    step_h = _as_fraction(step)
    if step_h <= 0:
        raise RadauContractFailure("CMM-2 Radau step width is not positive.")
    polynomials = []
    for row in range(3):
        coefficients = [_as_fraction(y_old[row])]
        coefficients.extend(_as_fraction(q_matrix[row, column]) for column in range(3))
        polynomials.append(tuple(coefficients))
    return t_old, step_h, tuple(polynomials)


def _evaluate(coefficients, value: Fraction) -> Fraction:
    total = Fraction(0)
    power = Fraction(1)
    for coefficient in coefficients:
        total += coefficient * power
        power *= value
    return total


def _derivative(coefficients):
    return tuple(index * coefficient for index, coefficient in enumerate(coefficients) if index)


def _sign(value: Fraction) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _isolate_derivative_roots(coefficients, left: Fraction, right: Fraction, budget: RootBudget):
    derivative = _derivative(coefficients)
    budget.charge()
    degree = len(derivative) - 1
    if degree < 1 or all(term == 0 for term in derivative):
        return []
    if degree == 1:
        root = -derivative[0] / derivative[1]
        return [root] if left < root < right else []
    constant, linear, quadratic = derivative[0], derivative[1], derivative[2]
    if quadratic == 0:
        if linear == 0:
            return []
        root = -constant / linear
        return [root] if left < root < right else []
    discriminant = linear * linear - 4 * quadratic * constant
    budget.charge()
    if discriminant < 0:
        return []
    vertex = -linear / (2 * quadratic)
    points = [left, right]
    if left < vertex < right:
        points.append(vertex)
    points = sorted(set(points))
    roots = []
    for bracket_left, bracket_right in zip(points, points[1:]):
        left_sign = _sign(_evaluate(derivative, bracket_left))
        right_sign = _sign(_evaluate(derivative, bracket_right))
        if left_sign == 0:
            roots.append(bracket_left)
        elif left_sign * right_sign < 0:
            roots.append(_refine_sign_change(derivative, bracket_left, bracket_right, budget))
    return [root for root in roots if left < root < right]


def _refine_sign_change(coefficients, left: Fraction, right: Fraction, budget: RootBudget) -> Fraction:
    steps = 0
    while right - left > ROOT_XTOL:
        steps += 1
        budget.charge()
        if steps > REFINEMENT_LIMIT:
            raise RadauContractFailure("CMM-2 root refinement limit exhausted.")
        middle = (left + right) / 2
        if _sign(_evaluate(coefficients, left)) * _sign(_evaluate(coefficients, middle)) <= 0:
            right = middle
        else:
            left = middle
    return (left + right) / 2


def _normalized_interval(t_old: Fraction, step: Fraction, start: float, end: float):
    start_x = (_as_fraction(start) - t_old) / step
    end_x = (_as_fraction(end) - t_old) / step
    if end_x < start_x:
        raise RadauContractFailure("CMM-2 Radau audit interval is reversed.")
    return start_x, end_x


def _scale_and_tolerances(stop: float, angles, width: float, controls):
    scale = max(1.0, abs(stop), *(abs(value) for value in angles))
    angle_tol = max(8 * controls.atol, 2 * math.ulp(scale))
    velocity_tol = max(8 * controls.atol_angular_velocity_rad_s, 2 * math.ulp(scale) / width)
    return angle_tol, velocity_tol


def _angles_at_nodes(dense, start: float, end: float):
    width = end - start
    nodes = (0.0, 0.25, 0.5, 0.75, 1.0)
    return [float(dense(start + width * node)[0]) for node in nodes]


def audit_represented_domain(dense, start: float, end: float, *, deployed_angle: float) -> int:
    """Audit the cubic on the actual returned interval. Returns domain-work used."""
    t_old, step, polynomials = represented_cubic(dense)
    start_x, end_x = _normalized_interval(t_old, step, start, end)
    budget = RootBudget(DOMAIN_WORK_LIMIT)
    theta = polynomials[0]
    omega = polynomials[2]
    _require_component_inside(
        theta,
        start_x,
        end_x,
        budget,
        lower=Fraction.from_float(deployed_angle - FOLD_LIMIT_RAD),
        upper=Fraction.from_float(deployed_angle + FOLD_LIMIT_RAD),
        strict=True,
        message="CMM-2 fold domain was left; paired aerodynamic loads are not replaced.",
    )
    _require_component_inside(
        omega,
        start_x,
        end_x,
        budget,
        lower=Fraction.from_float(OMEGA_MIN),
        upper=None,
        strict=False,
        message="CMM-2 shaft-speed domain was left; no zero-speed startup is used.",
    )
    return budget.used


def _require_component_inside(coefficients, start_x, end_x, budget, *, lower, upper, strict, message):
    points = [start_x, end_x, *_isolate_derivative_roots(coefficients, start_x, end_x, budget)]
    for point in points:
        budget.charge()
        value = _evaluate(coefficients, point)
        if lower is not None:
            outside = value <= lower if strict else value < lower
            if outside:
                raise RadauDomainExit(message)
        if upper is not None:
            outside = value >= upper if strict else value > upper
            if outside:
                raise RadauDomainExit(message)


def first_radau_contact(dense, start, end, _y0, _y1, parameters, controls):
    """Return the earliest proved stop contact, or None.

    The returned angle is the stop value. Callers that need the pre-snap state
    evaluate ``dense`` at the returned time before using that snapped angle.
    """
    t_old, step, polynomials = represented_cubic(dense)
    start_x, end_x = _normalized_interval(t_old, step, start, end)
    if not math.isfinite(end - start) or end <= start:
        raise RadauContractFailure("CMM-2 Radau contact interval is not usable.")
    budget = RootBudget(CONTACT_WORK_LIMIT)
    angles = _angles_at_nodes(dense, start, end)
    theta = polynomials[0]
    rate = polynomials[1]
    candidates = []
    for name, stop, lower in (
        ("lower", parameters.lower_stop_rad, True),
        ("upper", parameters.upper_stop_rad, False),
    ):
        relative = (theta[0] - _as_fraction(stop), *theta[1:])
        angle_tol, velocity_tol = _scale_and_tolerances(stop, angles, end - start, controls)
        exact_tol = Fraction(8) * Fraction.from_float(controls.atol)
        tolerance = _as_fraction(angle_tol)
        stationary = _isolate_derivative_roots(relative, start_x, end_x, budget)
        split = sorted({start_x, end_x, *stationary})
        roots = []
        for bracket_left, bracket_right in zip(split, split[1:]):
            left_sign = _sign(_evaluate(relative, bracket_left))
            right_sign = _sign(_evaluate(relative, bracket_right))
            if left_sign == 0:
                roots.append(bracket_left)
            elif left_sign * right_sign < 0:
                roots.append(_refine_sign_change(relative, bracket_left, bracket_right, budget))
        if _sign(_evaluate(relative, end_x)) == 0:
            roots.append(end_x)
        for point in stationary:
            budget.charge()
            distance = abs(_evaluate(relative, point))
            if distance == 0:
                roots.append(point)
            elif distance <= exact_tol:
                roots.append(point)
            elif distance <= tolerance:
                raise RadauContractFailure("CMM-2 tangent contact threshold is unresolved.")
        breached = False
        for point in (start_x, end_x, *stationary):
            budget.charge()
            value = _evaluate(relative, point)
            if (lower and -value > tolerance) or ((not lower) and value > tolerance):
                breached = True
        eligible = []
        for root in roots:
            budget.charge()
            hinge_rate = _evaluate(rate, root)
            velocity_limit = _as_fraction(velocity_tol)
            allowed = hinge_rate <= velocity_limit if lower else hinge_rate >= -velocity_limit
            if not allowed:
                continue
            physical = t_old + step * root
            eligible.append((physical, name, root))
        if breached and not eligible:
            raise RadauContractFailure("CMM-2 stop breach has no eligible contact.")
        candidates.extend(eligible)
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    physical, name, _root = candidates[0]
    event_time = float(physical)
    if not math.isfinite(event_time) or event_time < start or event_time > end:
        raise RadauContractFailure("CMM-2 contact time is outside the accepted step.")
    converted = (_as_fraction(event_time) - t_old) / step
    if abs(converted - _root) > ROOT_XTOL * (1 + abs(_root)):
        raise RadauContractFailure("CMM-2 contact time conversion is unresolved.")
    stop = parameters.lower_stop_rad if name == "lower" else parameters.upper_stop_rad
    pre_snap = dense(event_time)
    angle_tol, _velocity_tol = _scale_and_tolerances(stop, angles, end - start, controls)
    if abs(float(pre_snap[0]) - stop) > 4 * angle_tol:
        raise RadauContractFailure("CMM-2 pre-snap contact angle is outside tolerance.")
    return name, event_time, (stop, float(pre_snap[1])), pre_snap
