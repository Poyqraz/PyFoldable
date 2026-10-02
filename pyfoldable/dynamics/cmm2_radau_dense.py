"""CMM-2 cubic dense adapter for SciPy Radau.

The represented step is ``y = y_old + Q @ [x, x**2, x**3]`` with
``x = (t - t_old) / h``. Q is not multiplied by h again. Root decisions keep
exact rational roots and positive-width enclosures. A bisection midpoint is
not a certified root. Brent, with ``xtol = rtol = 1e-14``, confirms a
transverse monotone bracket and does not replace a proved rational root.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np
from scipy.optimize import brentq

from pyfoldable.dynamics.coupled_transient import FOLD_LIMIT_RAD, OMEGA_MIN


CONTACT_WORK_LIMIT = 800
DOMAIN_WORK_LIMIT = 800
REFINEMENT_LIMIT = 80
ISOLATION_DEPTH_LIMIT = 32
WIDTH_FLOOR = Fraction(1, 1 << 80)
ROOT_XTOL = Fraction(1, 10**14)
_SCALE_NODES = (0.0, 0.25, 0.5, 0.75, 1.0)


class RadauContractFailure(RuntimeError):
    """The cubic adapter cannot prove a closed contact or domain decision."""


class RadauDomainExit(RadauContractFailure):
    """The represented cubic left the CMM-2 model domain."""


class RecoverableConversionFailure(RadauContractFailure):
    """This timestamp cannot be certified. Another candidate may be tried."""


@dataclass
class IntervalTerminal:
    """Shared poison flag for both counters of one accepted interval."""

    message: str = ""


@dataclass
class RootBudget:
    """Shared root-work counter for one accepted interval.

    ``refinements`` is the cumulative bisection count of the bracket touched
    most recently. That count survives later helper calls on the same bracket.
    Exhaustion is terminal for the whole interval.
    """

    limit: int
    used: int = 0
    refinements: int = 0
    bracket_steps: dict = field(default_factory=dict)
    located: dict = field(default_factory=dict)
    refined_bounds: dict = field(default_factory=dict)
    terminal: IntervalTerminal = field(default_factory=IntervalTerminal)

    def _refuse_if_terminal(self) -> None:
        if self.terminal.message:
            raise RadauContractFailure(self.terminal.message)

    def charge(self, count: int = 1) -> None:
        self._refuse_if_terminal()
        self.used += count
        if self.used > self.limit:
            self.terminal.message = "CMM-2 root-work budget exhausted."
            raise RadauContractFailure(self.terminal.message)

    def refine(self, bracket_key) -> None:
        self._refuse_if_terminal()
        done = self.bracket_steps.get(bracket_key, 0) + 1
        self.bracket_steps[bracket_key] = done
        self.refinements = done
        if done > REFINEMENT_LIMIT:
            self.terminal.message = "CMM-2 root refinement limit exhausted."
            raise RadauContractFailure(self.terminal.message)
        self.charge()


@dataclass
class AcceptedIntervalWork:
    """Contact and domain counters for one accepted interval.

    Retries and later portions of that interval reuse the same counters.
    A new accepted step builds a new context.
    """

    contact: RootBudget
    domain: RootBudget

    @staticmethod
    def create(
        contact_limit: int = CONTACT_WORK_LIMIT,
        domain_limit: int = DOMAIN_WORK_LIMIT,
    ) -> "AcceptedIntervalWork":
        terminal = IntervalTerminal()
        return AcceptedIntervalWork(
            RootBudget(contact_limit, terminal=terminal),
            RootBudget(domain_limit, terminal=terminal),
        )


@dataclass(frozen=True)
class _Root:
    left: Fraction
    right: Fraction
    exact: Fraction | None
    anchor: Fraction | None = None

    @property
    def certified(self) -> Fraction:
        if self.exact is not None:
            return self.exact
        if self.anchor is not None and self.right - self.left <= ROOT_XTOL * (1 + abs(self.anchor)):
            return self.anchor
        raise RadauContractFailure("CMM-2 root enclosure is unresolved.")


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


def _trim(coefficients) -> tuple:
    coeffs = list(coefficients)
    while len(coeffs) > 1 and coeffs[-1] == 0:
        coeffs.pop()
    return tuple(coeffs)


def _evaluate(coefficients, value: Fraction) -> Fraction:
    total = Fraction(0)
    power = Fraction(1)
    for coefficient in coefficients:
        total += coefficient * power
        power *= value
    return total


def _derivative(coefficients):
    return _trim(tuple(index * coefficient for index, coefficient in enumerate(coefficients) if index))


def _sign(value: Fraction) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _perfect_square(value: Fraction):
    if value < 0:
        return None
    if value == 0:
        return Fraction(0)
    root_n = math.isqrt(value.numerator)
    root_d = math.isqrt(value.denominator)
    if root_n * root_n == value.numerator and root_d * root_d == value.denominator:
        return Fraction(root_n, root_d)
    return None


def _exact_quadratic_roots(coefficients):
    """Exact rational roots, ``[]`` when none are real, or ``None`` if irrational."""
    polynomial = _trim(coefficients)
    if polynomial == (Fraction(0),):
        return "identical"
    if len(polynomial) == 1:
        return []
    if len(polynomial) == 2:
        return [-polynomial[0] / polynomial[1]]
    if len(polynomial) != 3:
        return None
    constant, linear, quadratic = polynomial
    discriminant = linear * linear - 4 * quadratic * constant
    if discriminant < 0:
        return []
    root = _perfect_square(discriminant)
    if root is None:
        return None
    scale = 2 * quadratic
    return [(-linear - root) / scale, (-linear + root) / scale]


def _divide_polynomial(numerator, denominator):
    working = list(numerator)
    gap = len(working) - len(denominator)
    if gap < 0:
        return (Fraction(0),), _trim(tuple(working))
    quotient = [Fraction(0)] * (gap + 1)
    lead = denominator[-1]
    if lead == 0:
        raise RadauContractFailure("CMM-2 root count is unresolved.")
    for power in range(gap, -1, -1):
        factor = working[power + len(denominator) - 1] / lead
        quotient[power] = factor
        for index, coefficient in enumerate(denominator):
            working[power + index] -= factor * coefficient
    return _trim(tuple(quotient)), _trim(tuple(working))


def _deflate_root(polynomial, root: Fraction):
    quotient = []
    accumulator = Fraction(0)
    for coefficient in reversed(polynomial):
        accumulator = accumulator * root + coefficient
        quotient.append(accumulator)
    remainder = quotient.pop()
    if remainder != 0:
        raise RadauContractFailure("CMM-2 root identity is unresolved.")
    return _trim(tuple(reversed(quotient)))


def _remove_endpoint_roots(polynomial, root: Fraction):
    polynomial = _trim(polynomial)
    while len(polynomial) > 1 and _evaluate(polynomial, root) == 0:
        polynomial = _deflate_root(polynomial, root)
    return polynomial


def _sturm_chain(polynomial):
    polynomial = _trim(polynomial)
    if polynomial == (Fraction(0),):
        return None
    chain = [polynomial]
    derivative = _derivative(polynomial)
    if derivative != (Fraction(0),):
        chain.append(derivative)
    while len(chain[-1]) > 1:
        _quotient, remainder = _divide_polynomial(chain[-2], chain[-1])
        remainder = _trim(tuple(-coefficient for coefficient in remainder))
        if remainder == (Fraction(0),):
            break
        chain.append(remainder)
        if len(chain) > 8:
            raise RadauContractFailure("CMM-2 root count is unresolved.")
    return tuple(chain)


def _sign_variations(chain, value: Fraction) -> int:
    previous = 0
    changes = 0
    for polynomial in chain:
        sample = _evaluate(polynomial, value)
        if sample == 0:
            continue
        sign = 1 if sample > 0 else -1
        if previous and sign != previous:
            changes += 1
        previous = sign
    return changes


def _polynomial_gcd(left, right):
    left = _trim(left)
    right = _trim(right)
    while right != (Fraction(0),):
        _quotient, remainder = _divide_polynomial(left, right)
        left, right = right, remainder
    return _trim(left)


def _matched_key(budget: RootBudget, coefficients, left: Fraction, right: Fraction):
    polynomial = tuple(coefficients)
    match = None
    for key in budget.bracket_steps:
        stored, low, high = key
        if stored == polynomial and low <= left and right <= high:
            if match is None or (high - low) < (match[2] - match[1]):
                match = key
    if match is not None:
        return match
    return (polynomial, left, right)


def _refine_to(coefficients, left: Fraction, right: Fraction, budget: RootBudget, target: Fraction):
    """Shrink one sign-change bracket. The step count is stored on that bracket."""
    key = _matched_key(budget, coefficients, left, right)
    while right - left > target:
        if right - left <= WIDTH_FLOOR:
            break
        budget.refine(key)
        middle = (left + right) / 2
        if middle == left or middle == right:
            break
        middle_value = _evaluate(coefficients, middle)
        if middle_value == 0:
            return middle, middle
        if _sign(_evaluate(coefficients, left)) * _sign(middle_value) <= 0:
            right = middle
        else:
            left = middle
    return left, right


def _refine_sign_change(coefficients, left: Fraction, right: Fraction, budget: RootBudget) -> Fraction:
    """Bisect a sign change down to the Brent tolerance, keeping the bracket count."""
    left, right = _refine_to(coefficients, left, right, budget, ROOT_XTOL)
    return left if left == right else left


def _root_count(polynomial, left: Fraction, right: Fraction, budget: RootBudget) -> int:
    budget.charge()
    polynomial = _remove_endpoint_roots(_trim(polynomial), left)
    polynomial = _remove_endpoint_roots(polynomial, right)
    if len(polynomial) <= 1 or left >= right:
        return 0
    chain = _sturm_chain(polynomial)
    if chain is None:
        return 0
    count = _sign_variations(chain, left) - _sign_variations(chain, right)
    if count < 0:
        raise RadauContractFailure("CMM-2 root count is unresolved.")
    return count


def _isolate_real_roots(polynomial, left: Fraction, right: Fraction, budget: RootBudget, depth: int = 0):
    if depth > ISOLATION_DEPTH_LIMIT:
        raise RadauContractFailure("CMM-2 root isolation depth exhausted.")
    if right < left:
        raise RadauContractFailure("CMM-2 Radau audit interval is reversed.")
    if left == right:
        return []
    budget.charge()
    polynomial = _remove_endpoint_roots(_trim(polynomial), left)
    polynomial = _remove_endpoint_roots(polynomial, right)
    if len(polynomial) <= 1:
        return []
    exact = _exact_quadratic_roots(polynomial)
    if exact == "identical":
        return []
    if exact is not None:
        return [_Root(root, root, root) for root in exact if left < root < right]
    chain = _sturm_chain(polynomial)
    if chain is None:
        return []
    budget.charge()
    count = _sign_variations(chain, left) - _sign_variations(chain, right)
    if count < 0:
        raise RadauContractFailure("CMM-2 root count is unresolved.")
    if count == 0:
        return []
    if right - left <= WIDTH_FLOOR and count > 1:
        raise RadauContractFailure("CMM-2 root isolation width floor is unresolved.")
    middle = (left + right) / 2
    if middle == left or middle == right:
        raise RadauContractFailure("CMM-2 root isolation is unresolved.")
    if _evaluate(polynomial, middle) == 0:
        deflated = _remove_endpoint_roots(polynomial, middle)
        return [
            _Root(middle, middle, middle),
            *_isolate_real_roots(deflated, left, right, budget, depth + 1),
        ]
    if count == 1:
        low, high = _refine_to(polynomial, left, right, budget, ROOT_XTOL)
        return [_certify_interval(polynomial, low, high)]
    return [
        *_isolate_real_roots(polynomial, left, middle, budget, depth + 1),
        *_isolate_real_roots(polynomial, middle, right, budget, depth + 1),
    ]


def _simplest_between(low: Fraction, high: Fraction) -> Fraction | None:
    """Least-denominator rational strictly inside ``(low, high)``."""
    if low >= high:
        return None
    if low < 0 < high:
        return Fraction(0)
    if high <= 0:
        positive = _simplest_between(-high, -low)
        return None if positive is None else -positive
    left_n, left_d = 0, 1
    right_n, right_d = 1, 0
    for _step in range(128):
        mid_n = left_n + right_n
        mid_d = left_d + right_d
        if mid_d <= 0:
            return None
        middle = Fraction(mid_n, mid_d)
        if middle <= low:
            denominator = low.denominator * right_n - low.numerator * right_d
            numerator = low.numerator * left_d - low.denominator * left_n
            steps = 1 if denominator <= 0 else max(1, numerator // denominator)
            left_n += steps * right_n
            left_d += steps * right_d
        elif middle >= high:
            denominator = high.denominator * left_n - high.numerator * left_d
            numerator = high.numerator * right_d - high.denominator * right_n
            steps = 1 if denominator <= 0 else max(1, numerator // denominator)
            right_n += steps * left_n
            right_d += steps * left_d
        else:
            return middle
    return None


def _certify_interval(polynomial, low: Fraction, high: Fraction, anchor: Fraction | None = None) -> _Root:
    if low == high and _evaluate(polynomial, low) == 0:
        return _Root(low, high, low)
    candidate = _simplest_between(low, high)
    if (
        candidate is not None
        and low < candidate < high
        and _evaluate(polynomial, candidate) == 0
    ):
        return _Root(candidate, candidate, candidate)
    return _Root(low, high, None, anchor)


def _positive_divisors(value: int) -> list[int] | None:
    number = abs(int(value))
    if number == 0:
        return []
    shift = (number & -number).bit_length() - 1
    odd = number >> shift
    odd_divisors = [1]
    if odd > 1:
        if odd.bit_length() > 24:
            odd_divisors = [1, odd]
        else:
            factor = 1
            while factor * factor <= odd:
                if odd % factor == 0:
                    odd_divisors.append(factor)
                    quotient = odd // factor
                    if quotient != factor:
                        odd_divisors.append(quotient)
                factor = 3 if factor == 1 else factor + 2
    divisors = []
    for part in dict.fromkeys(odd_divisors):
        power = part
        for _exponent in range(shift + 1):
            divisors.append(power)
            power *= 2
    return divisors


def _pull_rational_roots(polynomial):
    """Deflate exact rational roots. A bounded divisor search is one isolation query."""
    current = _trim(polynomial)
    found: list[Fraction] = []
    while len(current) > 1 and current[0] == 0:
        found.append(Fraction(0))
        current = _deflate_root(current, Fraction(0))
    if len(current) <= 1:
        return found, current
    multiplier = 1
    for coefficient in current:
        multiplier = math.lcm(multiplier, coefficient.denominator)
    integers = []
    for coefficient in current:
        scaled = coefficient * multiplier
        if scaled.denominator != 1:
            return found, current
        integers.append(int(scaled))
    constant = abs(integers[0])
    leading = abs(integers[-1])
    if constant == 0 or leading == 0:
        return found, current
    numerators = _positive_divisors(constant)
    denominators = _positive_divisors(leading)
    if numerators is None or denominators is None or len(numerators) * len(denominators) > 4096:
        return found, current
    candidates = []
    for numerator in numerators:
        for denominator in denominators:
            candidates.append(Fraction(numerator, denominator))
            candidates.append(Fraction(-numerator, denominator))
    for candidate in dict.fromkeys(candidates):
        while len(current) > 1 and _evaluate(current, candidate) == 0:
            found.append(candidate)
            current = _deflate_root(current, candidate)
    return found, _trim(current)


def _locate_roots(coefficients, left: Fraction, right: Fraction, budget: RootBudget):
    polynomial = _trim(coefficients)
    key = (polynomial, left, right)
    cached = budget.located.get(key)
    if cached is not None:
        return cached
    budget.charge()
    if len(polynomial) <= 1:
        found: list[_Root] = []
    else:
        rational, remainder = _pull_rational_roots(polynomial)
        found = [_Root(root, root, root) for root in rational if left < root < right]
        remainder = _trim(remainder)
        if len(remainder) > 1:
            exact = _exact_quadratic_roots(remainder) if len(remainder) <= 3 else None
            if exact == "identical":
                raise RadauContractFailure("CMM-2 identical root is unresolved.")
            if isinstance(exact, list):
                found.extend(_Root(root, root, root) for root in exact if left < root < right)
            else:
                found.extend(_isolate_real_roots(remainder, left, right, budget, 0))
    found = _dedupe_roots(found)
    budget.located[key] = found
    return found


def _max_abs(coefficients, left: Fraction, right: Fraction) -> Fraction:
    samples = [left, right]
    derivative = _derivative(coefficients)
    if len(derivative) <= 3 and derivative != (Fraction(0),):
        exact = _exact_quadratic_roots(derivative)
        if isinstance(exact, list):
            samples.extend(root for root in exact if left < root < right)
    return max(abs(_evaluate(coefficients, sample)) for sample in samples)


def _value_bounds(coefficients, left: Fraction, right: Fraction):
    if left == right:
        value = _evaluate(coefficients, left)
        return value, value
    slope = _max_abs(_derivative(coefficients), left, right)
    middle = (left + right) / 2
    center = _evaluate(coefficients, middle)
    variation = slope * (right - left) / 2
    return center - variation, center + variation


def _require_in_step(dense, start: float, end: float) -> None:
    start = float(start)
    end = float(end)
    step_start = float(dense.t_old)
    step_end = float(dense.t)
    if not all(math.isfinite(value) for value in (start, end, step_start, step_end)):
        raise RadauContractFailure("CMM-2 Radau audit interval is outside the accepted step.")
    if end < start:
        raise RadauContractFailure("CMM-2 Radau audit interval is reversed.")
    if start < step_start or end > step_end:
        raise RadauContractFailure("CMM-2 Radau audit interval is outside the accepted step.")


def _normalized_interval(t_old: Fraction, step: Fraction, start: float, end: float):
    start_x = (_as_fraction(start) - t_old) / step
    end_x = (_as_fraction(end) - t_old) / step
    if end_x < start_x:
        raise RadauContractFailure("CMM-2 Radau audit interval is reversed.")
    return start_x, end_x


def _extend_exact_relative(t_old: Fraction, step: Fraction, latest: Fraction, moment: Fraction, dense) -> Fraction:
    """Normalize an exact relative time. Never replace it by a float subtraction."""
    if moment > Fraction.from_float(float(dense.t)) or moment < Fraction.from_float(float(dense.t_old)):
        raise RadauContractFailure("CMM-2 contact time is outside the accepted step.")
    coordinate = (moment - t_old) / step
    return coordinate if coordinate > latest else latest


def _scale_and_tolerances(stop: float, angles, width: float, controls):
    scale = max(1.0, abs(stop), *(abs(value) for value in angles))
    angle_tol = max(8 * controls.atol, 2 * math.ulp(scale))
    velocity_tol = max(8 * controls.atol_angular_velocity_rad_s, 2 * math.ulp(scale) / width)
    return angle_tol, velocity_tol


def _angles_at_nodes(dense, start: float, end: float):
    width = end - start
    angles = []
    for node in _SCALE_NODES:
        moment = start + width * node
        if moment < float(dense.t_old) or moment > float(dense.t):
            raise RadauContractFailure("CMM-2 contact scale node left the accepted step.")
        angles.append(float(dense(moment)[0]))
    return angles


def _shrink_root(polynomial, root: _Root, budget: RootBudget, target: Fraction) -> _Root:
    if root.exact is not None or root.right - root.left <= target:
        return root
    low, high = _refine_to(polynomial, root.left, root.right, budget, target)
    if low == root.left and high == root.right:
        return root
    if low == high:
        return _Root(low, high, low)
    return _Root(low, high, None, root.anchor)


def _domain_range(lower_value: Fraction, upper_value: Fraction, lower, upper, strict: bool) -> str:
    below = False
    above = False
    if lower is not None:
        below = upper_value <= lower if strict else upper_value < lower
    if upper is not None:
        above = lower_value >= upper if strict else lower_value > upper
    if below or above:
        return "exit"
    inside_lower = True if lower is None else (lower_value > lower if strict else lower_value >= lower)
    inside_upper = True if upper is None else (upper_value < upper if strict else upper_value <= upper)
    if inside_lower and inside_upper:
        return "safe"
    return "unknown"


def _boundary_polynomial(coefficients, boundary: Fraction):
    return _trim((coefficients[0] - boundary, *coefficients[1:]))


def _proves_boundary_root(derivative, coefficients, root: _Root, boundary: Fraction, budget: RootBudget) -> bool:
    budget.charge()
    level = _boundary_polynomial(coefficients, boundary)
    if root.exact is not None:
        return _evaluate(derivative, root.exact) == 0 and _evaluate(level, root.exact) == 0
    common = _polynomial_gcd(derivative, level)
    return _root_count(common, root.left, root.right, budget) == 1


def _component_probe(coefficients, derivative, root: _Root, lower, upper, strict: bool, budget: RootBudget) -> str:
    active = root
    while True:
        budget.charge()
        if active.exact is not None:
            value = _evaluate(coefficients, active.exact)
            decision = _domain_range(value, value, lower, upper, strict)
        else:
            decision = _domain_range(*_value_bounds(coefficients, active.left, active.right), lower, upper, strict)
        if decision != "unknown":
            return decision
        if active.exact is None and active.right - active.left > WIDTH_FLOOR:
            updated = _shrink_root(derivative, active, budget, WIDTH_FLOOR)
            if updated.left == active.left and updated.right == active.right and updated.exact == active.exact:
                return "unknown"
            active = updated
            continue
        boundaries = []
        if lower is not None:
            boundaries.append(lower)
        if upper is not None:
            boundaries.append(upper)
        for boundary in boundaries:
            if _proves_boundary_root(derivative, coefficients, active, boundary, budget):
                return "exit" if strict else "safe"
        return "unknown"


def _require_component_inside(coefficients, start_x, end_x, budget, *, lower, upper, strict, message):
    derivative = _derivative(coefficients)
    probes = [_Root(start_x, start_x, start_x), _Root(end_x, end_x, end_x)]
    if derivative != (Fraction(0),):
        probes.extend(_locate_roots(derivative, start_x, end_x, budget))
    for probe in probes:
        decision = _component_probe(coefficients, derivative, probe, lower, upper, strict, budget)
        if decision == "exit":
            raise RadauDomainExit(message)
        if decision != "safe":
            raise RadauContractFailure("CMM-2 domain enclosure is unresolved.")


def audit_represented_domain(
    dense,
    start: float,
    end: float,
    *,
    deployed_angle: float,
    origin: float | None = None,
    evaluation_time: float | None = None,
    work_limit: int = DOMAIN_WORK_LIMIT,
    work: AcceptedIntervalWork | None = None,
) -> int:
    """Audit the cubic through the actual returned interval. Returns domain-work used."""
    _require_in_step(dense, start, end)
    t_old, step, polynomials = represented_cubic(dense)
    start_x, end_x = _normalized_interval(t_old, step, start, end)
    if origin is not None:
        public = float(origin) + float(end)
        public_relative = Fraction.from_float(public) - Fraction.from_float(float(origin))
        end_x = _extend_exact_relative(t_old, step, end_x, public_relative, dense)
    if evaluation_time is not None:
        end_x = _extend_exact_relative(
            t_old, step, end_x, Fraction.from_float(float(evaluation_time)), dense
        )
    if work is None:
        work = AcceptedIntervalWork.create(domain_limit=work_limit)
    budget = work.domain
    _require_component_inside(
        polynomials[0],
        start_x,
        end_x,
        budget,
        lower=_as_fraction(deployed_angle - FOLD_LIMIT_RAD),
        upper=_as_fraction(deployed_angle + FOLD_LIMIT_RAD),
        strict=True,
        message="CMM-2 fold domain was left; paired aerodynamic loads are not replaced.",
    )
    _require_component_inside(
        polynomials[2],
        start_x,
        end_x,
        budget,
        lower=_as_fraction(OMEGA_MIN),
        upper=None,
        strict=False,
        message="CMM-2 shaft-speed domain was left; no zero-speed startup is used.",
    )
    return budget.used


def _dedupe_roots(roots: list[_Root]) -> list[_Root]:
    unique: list[_Root] = []
    for root in roots:
        if root.exact is None:
            unique.append(root)
            continue
        if any(other.exact == root.exact for other in unique):
            continue
        unique.append(root)
    return unique


def _confirm_brent(coefficients, left: Fraction, right: Fraction, exact: Fraction | None, budget: RootBudget) -> Fraction:
    """Confirm a monotone bracket with Brent. An exact rational root stays exact."""
    budget.charge()
    if exact is not None and _evaluate(coefficients, exact) != 0:
        raise RadauContractFailure("CMM-2 certified root does not satisfy the bracket.")
    narrow = right - left <= ROOT_XTOL or right == left
    same_sign = _sign(_evaluate(coefficients, left)) * _sign(_evaluate(coefficients, right)) >= 0
    if exact is not None and (narrow or same_sign):
        return exact
    if exact is None and narrow and float(left) >= float(right):
        raise RadauContractFailure("CMM-2 Brent root is unresolved.")
    if exact is None and same_sign:
        raise RadauContractFailure("CMM-2 Brent root is unresolved.")

    def function(value: float) -> float:
        budget.charge()
        return float(_evaluate(coefficients, Fraction(value)))

    try:
        found = brentq(function, float(left), float(right), xtol=1e-14, rtol=1e-14)
    except (ArithmeticError, RuntimeError, ValueError) as exc:
        raise RadauContractFailure("CMM-2 Brent root is unresolved.") from exc
    anchor = Fraction(found)
    if exact is not None and abs(anchor - exact) > ROOT_XTOL * (1 + abs(exact)):
        raise RadauContractFailure("CMM-2 Brent root does not match the certified root.")
    if exact is not None:
        return exact
    allowance = ROOT_XTOL * (1 + abs(anchor))
    if anchor < left - allowance or anchor > right + allowance:
        raise RadauContractFailure("CMM-2 Brent root left its certified enclosure.")
    return anchor


def _monotone_bracket(root: _Root, start_x: Fraction, end_x: Fraction, roots: list[_Root]):
    position = root.exact if root.exact is not None else root.left
    left, right = start_x, end_x
    for other in roots:
        if other == root:
            continue
        other_left = other.exact if other.exact is not None else other.left
        other_right = other.exact if other.exact is not None else other.right
        if other_right <= position and other_right > left:
            left = other_right
        if other_left >= position and other_left < right:
            right = other_left
    if left >= right:
        return position, position
    return left, right


def _transverse_roots(polynomial, start_x, end_x, _stationary, budget: RootBudget) -> list[_Root]:
    """Every interior root, including each exact rational root of a cubic."""
    located = list(_locate_roots(polynomial, start_x, end_x, budget))
    found: list[_Root] = []
    if _evaluate(polynomial, start_x) == 0:
        found.append(_Root(start_x, start_x, start_x))
    for root in located:
        left, right = _monotone_bracket(root, start_x, end_x, located)
        if root.exact is not None:
            _confirm_brent(polynomial, left, right, root.exact, budget)
            found.append(root)
            continue
        anchor = _confirm_brent(polynomial, root.left, root.right, None, budget)
        allowance = ROOT_XTOL * (1 + abs(anchor))
        if abs(anchor - root.left) > allowance or abs(anchor - root.right) > allowance:
            raise RadauContractFailure("CMM-2 Brent root left its certified enclosure.")
        found.append(_Root(root.left, root.right, None, anchor))
    if _evaluate(polynomial, end_x) == 0:
        found.append(_Root(end_x, end_x, end_x))
    return _dedupe_roots(found)


def _stationary_class(relative, root: _Root, exact_tol: Fraction, angle_tol: Fraction, budget: RootBudget) -> str:
    active = root
    derivative = _derivative(relative)
    while True:
        budget.charge()
        if active.exact is not None:
            value = _evaluate(relative, active.exact)
            lower, upper = value, value
        else:
            lower, upper = _value_bounds(relative, active.left, active.right)
        if lower == 0 and upper == 0:
            return "exact", active
        if lower > angle_tol or upper < -angle_tol:
            return "excluded", active
        if lower >= -exact_tol and upper <= exact_tol:
            if lower > 0 or upper < 0 or (active.exact is not None and _evaluate(relative, active.exact) != 0):
                return "tolerance", active
        if active.exact is not None:
            distance = abs(_evaluate(relative, active.exact))
            if distance == 0:
                return "exact", active
            if distance <= exact_tol:
                return "tolerance", active
            if distance > angle_tol:
                return "excluded", active
            return "unresolved", active
        if active.right - active.left <= WIDTH_FLOOR or derivative == (Fraction(0),):
            return "unresolved", active
        updated = _shrink_root(derivative, active, budget, WIDTH_FLOOR)
        if updated.left == active.left and updated.right == active.right:
            return "unresolved", active
        active = updated


def _direction_allows(rate, root: _Root, velocity_tol: Fraction, lower: bool, budget: RootBudget) -> bool:
    active = root
    while True:
        budget.charge()
        if active.exact is not None:
            sample = _evaluate(rate, active.exact)
            low = high = sample
        else:
            low, high = _value_bounds(rate, active.left, active.right)
        if lower:
            if high <= velocity_tol:
                return True
            if low > velocity_tol:
                return False
        else:
            if low >= -velocity_tol:
                return True
            if high < -velocity_tol:
                return False
        if active.exact is not None or active.right - active.left <= ROOT_XTOL:
            raise RadauContractFailure("CMM-2 contact direction is unresolved.")
        updated = _shrink_root(rate, active, budget, ROOT_XTOL)
        if updated.left == active.left and updated.right == active.right:
            raise RadauContractFailure("CMM-2 contact direction is unresolved.")
        active = updated


def _proved_breach(relative, root: _Root, tolerance: Fraction, lower: bool, budget: RootBudget) -> bool:
    active = root
    derivative = _derivative(relative)
    while True:
        budget.charge()
        if active.exact is not None:
            value = _evaluate(relative, active.exact)
            low = high = value
        else:
            low, high = _value_bounds(relative, active.left, active.right)
        if lower:
            if high < -tolerance:
                return True
            if low >= -tolerance:
                return False
        else:
            if low > tolerance:
                return True
            if high <= tolerance:
                return False
        if active.exact is not None or derivative == (Fraction(0),) or active.right - active.left <= WIDTH_FLOOR:
            raise RadauContractFailure("CMM-2 stop-breach threshold is unresolved.")
        updated = _shrink_root(derivative, active, budget, WIDTH_FLOOR)
        if updated.left == active.left and updated.right == active.right:
            raise RadauContractFailure("CMM-2 stop-breach threshold is unresolved.")
        active = updated


def _bisect_sign(polynomial, left: Fraction, right: Fraction, budget: RootBudget):
    key = _matched_key(budget, polynomial, left, right)
    budget.refine(key)
    middle = (left + right) / 2
    if middle == left or middle == right:
        return left, right
    if _evaluate(polynomial, middle) == 0:
        return middle, middle
    if _sign(_evaluate(polynomial, left)) * _sign(_evaluate(polynomial, middle)) <= 0:
        return left, middle
    return middle, right


def _enclosure_covers(left: Fraction, right: Fraction, xi: Fraction, allowance: Fraction) -> bool:
    return max(abs(xi - left), abs(xi - right)) <= allowance


def _root_identity(polynomial, root: _Root):
    return (tuple(_trim(polynomial)), root.left, root.right, root.exact)


def _stored_bounds(polynomial, root: _Root, budget: RootBudget):
    if root.exact is not None:
        return root.exact, root.exact
    return budget.refined_bounds.get(_root_identity(polynomial, root), (root.left, root.right))


def _certify_against_root(polynomial, root: _Root, xi: Fraction, budget: RootBudget):
    """Refine the retained bracket until ``xi`` lies in its allowance, or fail."""
    allowance = ROOT_XTOL * (1 + abs(xi))
    left, right = _stored_bounds(polynomial, root, budget)
    identity = _root_identity(polynomial, root)
    while not _enclosure_covers(left, right, xi, allowance):
        outside = xi < left or xi > right
        gap = min(abs(xi - left), abs(xi - right))
        if left == right or (outside and gap > allowance):
            raise RecoverableConversionFailure("CMM-2 contact time conversion is unresolved.")
        left, right = _bisect_sign(polynomial, left, right, budget)
        if root.exact is None:
            budget.refined_bounds[identity] = (left, right)
    budget.charge()
    return left, right


def certify_representable_time(polynomial, t_old: Fraction, step: Fraction, timestamp, budget: RootBudget):
    """Certify one timestamp against the quadratic/cubic root enclosure.

    This helper is the synthetic allowance witness. It is not a C2V-07 fixture.
    """
    budget.charge()
    polynomial = _trim(tuple(polynomial))
    roots = _locate_roots(polynomial, Fraction(0), Fraction(1), budget)
    if len(roots) != 1:
        raise RadauContractFailure("CMM-2 contact time conversion is unresolved.")
    xi = (Fraction.from_float(float(timestamp)) - t_old) / step
    _certify_against_root(polynomial, roots[0], xi, budget)
    budget.charge()
    budget.charge()
    return xi


def _significand_even(value: float) -> bool:
    if value == 0.0:
        return True
    mantissa, _exponent = math.frexp(value)
    significand = int(round(abs(mantissa) * (1 << 53)))
    return significand % 2 == 0


def _adjacent_timestamp_order(target: Fraction) -> list[float]:
    """Nearest-even binary64 neighbor, then the other adjacent bracket.

    An exactly representable value is a singleton. This is not a wider ULP search.
    """
    if target == 0:
        return [0.0]
    hint = float(target)
    if not math.isfinite(hint):
        raise RadauContractFailure("CMM-2 contact time conversion is unresolved.")
    low = hint
    for _step in range(64):
        if Fraction.from_float(low) <= target:
            break
        nxt = math.nextafter(low, -math.inf)
        if nxt == low:
            raise RadauContractFailure("CMM-2 contact time conversion is unresolved.")
        low = nxt
    else:
        raise RadauContractFailure("CMM-2 contact time conversion is unresolved.")
    for _step in range(64):
        nxt = math.nextafter(low, math.inf)
        if not math.isfinite(nxt) or Fraction.from_float(nxt) > target:
            break
        low = nxt
    else:
        raise RadauContractFailure("CMM-2 contact time conversion is unresolved.")
    low_value = Fraction.from_float(low)
    if low_value == target:
        return [low]
    high = math.nextafter(low, math.inf)
    high_value = Fraction.from_float(high) if math.isfinite(high) else None
    if (
        high_value is None
        or math.nextafter(low, math.inf) != high
        or not low_value < target < high_value
    ):
        raise RadauContractFailure("CMM-2 contact time conversion is unresolved.")
    below = target - low_value
    above = high_value - target
    if below < above or (below == above and _significand_even(low)):
        return [low, high]
    return [high, low]


def _rn64(value: Fraction) -> float:
    return _adjacent_timestamp_order(value)[0]


def _rate_allows(rate, xi: Fraction, limit: Fraction, lower: bool) -> bool:
    value = _evaluate(rate, xi)
    if lower:
        return value <= limit
    return value >= -limit


def _convert_root(
    origin,
    last_published,
    t_old,
    step,
    root: _Root,
    polynomial,
    rate,
    velocity_limit: Fraction,
    lower: bool,
    start: float,
    end: float,
    budget: RootBudget,
):
    budget.charge()
    identity = _root_identity(polynomial, root)
    left, right = _stored_bounds(polynomial, root, budget)
    origin_fraction = Fraction.from_float(float(origin))
    start_bound = Fraction.from_float(float(start))
    end_bound = Fraction.from_float(float(end))
    step_width = end_bound - start_bound
    if step_width <= 0:
        raise RadauContractFailure("CMM-2 contact time conversion is unresolved.")
    reasons: set[str] = set()
    while True:
        budget.charge()
        if root.exact is not None:
            anchor = root.exact
        elif root.anchor is not None and left <= root.anchor <= right:
            anchor = root.anchor
        else:
            anchor = (left + right) / 2
        root_radius = max(abs(left - anchor), abs(right - anchor))
        ideal = t_old + step * anchor
        ordered = _adjacent_timestamp_order(ideal)
        option_reasons: set[str] = set()
        restarted = False
        for relative in ordered:
            budget.charge()
            if not math.isfinite(relative):
                option_reasons.add("conversion")
                continue
            relative_fraction = Fraction.from_float(relative)
            public = _rn64(origin_fraction + relative_fraction)
            if not math.isfinite(public):
                option_reasons.add("conversion")
                continue
            if last_published is not None and not public > float(last_published):
                option_reasons.add("conversion")
                continue
            public_fraction = Fraction.from_float(public)
            public_elapsed = public_fraction - origin_fraction
            budget.charge()
            if not start_bound <= relative_fraction <= end_bound:
                option_reasons.add("conversion")
                continue
            if not start_bound <= public_elapsed <= end_bound:
                option_reasons.add("conversion")
                continue
            event_xi = (relative_fraction - start_bound) / step_width
            root_time = step * root_radius
            root_allowance = step_width * ROOT_XTOL * (1 + abs(event_xi))
            if root_time > root_allowance:
                if root.exact is not None or left == right:
                    option_reasons.add("conversion")
                    continue
                new_left, new_right = _bisect_sign(polynomial, left, right, budget)
                if (new_left, new_right) == (left, right):
                    raise RadauContractFailure("CMM-2 contact time conversion is unresolved.")
                left, right = new_left, new_right
                budget.refined_bounds[identity] = (left, right)
                restarted = True
                break
            relative_xi = (relative_fraction - t_old) / step
            public_xi = (public_elapsed - t_old) / step
            budget.charge()
            if not _rate_allows(rate, relative_xi, velocity_limit, lower):
                option_reasons.add("direction")
                continue
            budget.charge()
            if not _rate_allows(rate, public_xi, velocity_limit, lower):
                option_reasons.add("direction")
                continue
            span_left = min(left, right, relative_xi, public_xi)
            span_right = max(left, right, relative_xi, public_xi)
            angle_root = root.exact is not None and _evaluate(polynomial, root.exact) == 0
            sign_change = (
                root.exact is None
                and _sign(_evaluate(polynomial, root.left)) * _sign(_evaluate(polynomial, root.right)) < 0
            )
            identity_polynomial = polynomial if angle_root or sign_change else _derivative(polynomial)
            distinct_roots = _root_count(identity_polynomial, span_left, span_right, budget)
            if _evaluate(identity_polynomial, span_left) == 0:
                distinct_roots += 1
            if span_right != span_left and _evaluate(identity_polynomial, span_right) == 0:
                distinct_roots += 1
            if distinct_roots != 1:
                raise RadauContractFailure("CMM-2 contact identity is unresolved.")
            return relative, public, relative_xi, public_xi
        if restarted:
            continue
        reasons.update(option_reasons)
        break
    if "direction" in reasons and "conversion" not in reasons:
        raise RadauContractFailure("CMM-2 contact direction is unresolved.")
    raise RadauContractFailure("CMM-2 contact time conversion is unresolved.")


def _order_candidates(candidates, budget: RootBudget):
    budget.charge()
    for index, first in enumerate(candidates):
        for second in candidates[index + 1 :]:
            first_exact = first[0].exact
            second_exact = second[0].exact
            if first_exact is not None and second_exact is not None:
                if first_exact == second_exact:
                    budget.charge()
                    raise RadauContractFailure("CMM-2 contact order is unresolved.")
                continue
            left = max(first[0].left, second[0].left)
            right = min(first[0].right, second[0].right)
            if left < right:
                budget.charge()
                raise RadauContractFailure("CMM-2 contact order is unresolved.")
    return sorted(candidates, key=lambda item: item[0].exact if item[0].exact is not None else item[0].left)


def first_radau_contact(
    dense,
    start,
    end,
    _y0,
    _y1,
    parameters,
    controls,
    *,
    origin: float = 0.0,
    last_published: float | None = None,
    work_limit: int = CONTACT_WORK_LIMIT,
    work: AcceptedIntervalWork | None = None,
):
    """Return the earliest proved stop contact, or None.

    The returned angle is the snapped stop. ``pre_snap`` is the dense state at
    the converted relative time, before that snap is published.
    """
    _require_in_step(dense, float(start), float(end))
    t_old, step, polynomials = represented_cubic(dense)
    start_x, end_x = _normalized_interval(t_old, step, start, end)
    if not math.isfinite(end - start) or end <= start:
        raise RadauContractFailure("CMM-2 Radau contact interval is not usable.")
    if work is None:
        work = AcceptedIntervalWork.create(contact_limit=work_limit)
    budget = work.contact
    angles = _angles_at_nodes(dense, float(start), float(end))
    theta = polynomials[0]
    rate = polynomials[1]
    candidates = []
    for name, stop, lower in (
        ("lower", parameters.lower_stop_rad, True),
        ("upper", parameters.upper_stop_rad, False),
    ):
        relative = _trim((theta[0] - _as_fraction(stop), *theta[1:]))
        angle_tol, velocity_tol = _scale_and_tolerances(stop, angles, float(end) - float(start), controls)
        exact_tol = Fraction(8) * _as_fraction(controls.atol)
        tolerance = _as_fraction(angle_tol)
        velocity_limit = _as_fraction(velocity_tol)
        if relative == (Fraction(0),):
            stationary = []
            roots = [_Root(start_x, start_x, start_x)]
        else:
            derivative = _derivative(relative)
            stationary = [] if derivative == (Fraction(0),) else _locate_roots(derivative, start_x, end_x, budget)
            roots = _transverse_roots(relative, start_x, end_x, stationary, budget)
        eligible = []
        accepted = []
        for root in roots:
            try:
                root.certified
            except RadauContractFailure as exc:
                raise RadauContractFailure("CMM-2 contact root enclosure is unresolved.") from exc
            if not _direction_allows(rate, root, velocity_limit, lower, budget):
                continue
            if root.exact is not None and any(previous.exact == root.exact for previous in accepted):
                continue
            accepted.append(root)
            eligible.append(root)
        for root in stationary:
            if root.exact is not None and any(previous.exact == root.exact for previous in accepted):
                continue
            kind, root = _stationary_class(relative, root, exact_tol, tolerance, budget)
            if kind == "unresolved":
                raise RadauContractFailure("CMM-2 tangent contact threshold is unresolved.")
            if kind not in {"exact", "tolerance"}:
                continue
            if root.exact is None:
                anchor = root.anchor if root.anchor is not None else (root.left + root.right) / 2
                root = _Root(root.left, root.right, None, anchor)
                try:
                    root.certified
                except RadauContractFailure as exc:
                    raise RadauContractFailure("CMM-2 tangent contact threshold is unresolved.") from exc
            if not _direction_allows(rate, root, velocity_limit, lower, budget):
                continue
            accepted.append(root)
            eligible.append(root)
        probes = [_Root(start_x, start_x, start_x), _Root(end_x, end_x, end_x), *stationary]
        breached = False
        for probe in probes:
            if _proved_breach(relative, probe, tolerance, lower, budget):
                breached = True
        if breached and not eligible:
            raise RadauContractFailure("CMM-2 stop breach has no eligible contact.")
        for root in eligible:
            candidates.append((root, name, stop, angle_tol))
    if not candidates:
        return None
    ordered = _order_candidates(candidates, budget)
    converted = []
    for root, name, stop, angle_tol in ordered:
        lower = name == "lower"
        _angle_tol, velocity_tol = _scale_and_tolerances(stop, angles, float(end) - float(start), controls)
        relative_polynomial = _trim((theta[0] - _as_fraction(stop), *theta[1:]))
        relative_time, public, _relative_xi, _public_xi = _convert_root(
            origin,
            last_published,
            t_old,
            step,
            root,
            relative_polynomial,
            rate,
            _as_fraction(velocity_tol),
            lower,
            float(start),
            float(end),
            budget,
        )
        converted.append((public, relative_time, name, stop, angle_tol, root))
    if len({item[0] for item in converted}) != len(converted):
        raise RadauContractFailure("CMM-2 distinct contacts collapsed to one time.")
    public_order = [item[0] for item in converted]
    if public_order != sorted(public_order):
        raise RadauContractFailure("CMM-2 contact order is unresolved.")
    _public, relative_time, name, stop, angle_tol, _root = converted[0]
    pre_snap = dense(relative_time)
    if abs(float(pre_snap[0]) - stop) > 4 * angle_tol:
        raise RadauContractFailure("CMM-2 pre-snap contact angle is outside tolerance.")
    return name, relative_time, (stop, float(pre_snap[1])), pre_snap
