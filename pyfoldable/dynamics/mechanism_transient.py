"""Explicit-SI prescribed-rotation model for one planar rigid hinge body.

The solve stops at the earliest stop contact, including contacts hidden inside
an accepted RK45 step. Impact reaction, bounce and latching are not modelled.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass

import numpy as np
from numpy.polynomial import Polynomial
from scipy.integrate import RK45
from scipy.optimize import brentq

from pyfoldable.dynamics.mechanism_contracts import ContactPolicy, DryFriction

RPM_TO_RAD_S = 2.0 * math.pi / 60.0
_EPS = np.finfo(float).eps


def _finite(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite scalar.")
    try:
        finite = math.isfinite(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite scalar.") from exc
    if not finite:
        raise ValueError(f"{name} must be a finite scalar.")


def _number(name: str, value: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError(f"Transient numerical {name} is not representable.") from exc
    if not math.isfinite(result):
        raise RuntimeError(f"Transient numerical {name} is not finite.")
    return result


@dataclass(frozen=True)
class MechanismParameters:
    mass_kg: float
    cg_distance_m: float
    hinge_inertia_kg_m2: float
    hinge_radius_m: float
    spring_stiffness_nm_rad: float
    rest_angle_rad: float
    viscous_damping_nm_s_rad: float
    lower_stop_rad: float
    upper_stop_rad: float
    dry_friction: DryFriction = DryFriction()

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if name != "dry_friction":
                _finite(name, value)
        if not isinstance(self.dry_friction, DryFriction):
            raise ValueError("dry_friction must be a validated DryFriction contract.")
        if self.mass_kg <= 0 or self.cg_distance_m < 0 or self.hinge_radius_m < 0:
            raise ValueError("Mass must be positive and SI distances nonnegative.")
        try:
            minimum = self.mass_kg * self.cg_distance_m**2
        except (ArithmeticError, OverflowError) as exc:
            raise ValueError("J >= m c² check overflowed; use representable inputs.") from exc
        if not math.isfinite(minimum):
            raise ValueError("J >= m c² check overflowed; use representable inputs.")
        tolerance = 16 * max(
            math.ulp(abs(self.hinge_inertia_kg_m2)),
            math.ulp(abs(minimum)),
        )
        if self.hinge_inertia_kg_m2 <= 0 or self.hinge_inertia_kg_m2 + tolerance < minimum:
            raise ValueError("Hinge inertia must satisfy J >= m c².")
        if self.spring_stiffness_nm_rad < 0 or self.viscous_damping_nm_s_rad < 0:
            raise ValueError("Spring stiffness and viscous damping must be nonnegative.")
        if self.lower_stop_rad >= self.upper_stop_rad:
            raise ValueError("Lower stop must be below upper stop.")


@dataclass(frozen=True)
class DriveHistory:
    time_s: tuple[float, ...]
    rpm: tuple[float, ...]
    applied_hinge_torque_nm: tuple[float, ...]

    def __post_init__(self) -> None:
        values = (self.time_s, self.rpm, self.applied_hinge_torque_nm)
        if any(not isinstance(item, tuple) for item in values):
            raise ValueError("Drive histories must be immutable tuples.")
        if len(self.time_s) < 2 or len({len(item) for item in values}) != 1:
            raise ValueError("Drive histories require equal-length arrays with at least two knots.")
        for sequence in values:
            for value in sequence:
                _finite("drive history value", value)
        if self.time_s[0] < 0 or any(b <= a for a, b in zip(self.time_s, self.time_s[1:])):
            raise ValueError("Drive knot times must be nonnegative and strictly increasing.")


@dataclass(frozen=True)
class SolverControls:
    rtol: float = 1e-8
    atol: float = 1e-10
    max_step_s: float = 0.002
    max_samples: int = 50_000
    max_knots: int = 256
    max_duration_s: float = 60.0
    atol_angular_velocity_rad_s: float = 1e-10

    def __post_init__(self) -> None:
        for name in ("rtol", "atol", "atol_angular_velocity_rad_s", "max_step_s", "max_duration_s"):
            _finite(name, getattr(self, name))
        if not (0 < self.rtol <= 1e-3 and 0 < self.atol <= 1e-5
                and 0 < self.atol_angular_velocity_rad_s <= 1e-3 and self.max_step_s > 0):
            raise ValueError("Solver tolerances and maximum step are outside the bounded budget.")
        if (isinstance(self.max_samples, bool) or not isinstance(self.max_samples, int)
                or not 100 <= self.max_samples <= 1_000_000):
            raise ValueError("Sample budget must be an integer from 100 to 1000000.")
        if (isinstance(self.max_knots, bool) or not isinstance(self.max_knots, int)
                or not 2 <= self.max_knots <= 4096 or not 0 < self.max_duration_s <= 3600):
            raise ValueError("Knot or duration budget is invalid.")


@dataclass(frozen=True)
class TransientRequest:
    parameters: MechanismParameters
    drive: DriveHistory
    initial_angle_rad: float
    initial_angular_velocity_rad_s: float
    controls: SolverControls = SolverControls()
    contact_policy: ContactPolicy = ContactPolicy()

    def __post_init__(self) -> None:
        if (not isinstance(self.parameters, MechanismParameters)
                or not isinstance(self.drive, DriveHistory)
                or not isinstance(self.controls, SolverControls)
                or not isinstance(self.contact_policy, ContactPolicy)):
            raise ValueError("Request requires validated parameter, drive, control and contact models.")
        _finite("initial_angle_rad", self.initial_angle_rad)
        _finite("initial_angular_velocity_rad_s", self.initial_angular_velocity_rad_s)
        if not self.parameters.lower_stop_rad < self.initial_angle_rad < self.parameters.upper_stop_rad:
            raise ValueError("Initial angle must lie strictly inside both stops.")
        duration = self.drive.time_s[-1] - self.drive.time_s[0]
        if len(self.drive.time_s) > self.controls.max_knots or duration > self.controls.max_duration_s:
            raise ValueError("Drive history exceeds the solver budget.")
        minimum_interval = min(b - a for a, b in zip(self.drive.time_s, self.drive.time_s[1:]))
        time_scale = min(minimum_interval, self.controls.max_step_s)
        if max(math.ulp(value) for value in self.drive.time_s) > time_scale * 1e-8:
            raise ValueError("Drive timestamp resolution is too coarse for the requested step or duration.")
        minimum_samples = 1 + sum(math.ceil((b - a) / self.controls.max_step_s)
                                  for a, b in zip(self.drive.time_s, self.drive.time_s[1:]))
        if minimum_samples > self.controls.max_samples:
            raise ValueError("Drive history exceeds the conservative sample budget preflight.")


@dataclass(frozen=True)
class StopContact:
    stop: str
    time_s: float
    angle_rad: float
    preimpact_angular_velocity_rad_s: float


@dataclass(frozen=True)
class TransientResult:
    status: str
    message: str
    time_s: tuple[float, ...]
    angle_rad: tuple[float, ...]
    angular_velocity_rad_s: tuple[float, ...]
    angular_acceleration_rad_s2: tuple[float, ...]
    rpm: tuple[float, ...]
    omega_rad_s: tuple[float, ...]
    omega_dot_rad_s2: tuple[float, ...]
    applied_torque_nm: tuple[float, ...]
    spring_torque_nm: tuple[float, ...]
    damping_torque_nm: tuple[float, ...]
    dry_friction_torque_nm: tuple[float, ...]
    centrifugal_torque_nm: tuple[float, ...]
    euler_torque_nm: tuple[float, ...]
    effective_energy_j: tuple[float, ...]
    applied_power_w: tuple[float, ...]
    damping_power_w: tuple[float, ...]
    dry_friction_power_w: tuple[float, ...]
    total_dissipation_power_w: tuple[float, ...]
    applied_work_j: tuple[float, ...]
    viscous_dissipated_energy_j: tuple[float, ...]
    dry_friction_dissipated_energy_j: tuple[float, ...]
    total_dissipated_energy_j: tuple[float, ...]
    segment_start_indices: tuple[int, ...]
    contact: StopContact | None


def _integral(times: list[float], values: list[float]) -> list[float]:
    result = [0.0]
    for index in range(1, len(times)):
        increment = 0.5 * (values[index - 1] + values[index]) * (times[index] - times[index - 1])
        result.append(_number("integral", result[-1] + increment))
    return result


def _first_contact(dense, start, end, y0, y1, parameters, controls):
    """Reconstruct RK45's quartic with five nodes and audit every monotone interval."""
    width = end - start
    nodes = np.linspace(0.0, 1.0, 5)
    angles = np.asarray([_number("dense angle", dense(start + width * float(x))[0]) for x in nodes])
    candidates = []
    for name, stop, direction in (("lower", parameters.lower_stop_rad, -1),
                                  ("upper", parameters.upper_stop_rad, 1)):
        # Fit stop-relative values.  Fitting a 1e10-rad offset and subtracting
        # the stop afterwards can lose a resolvable 1e-5-rad clearance.
        relative_angles = angles - stop
        try:
            shifted = Polynomial(
                np.polynomial.polynomial.polyfit(nodes, relative_angles, 4)
            )
        except (ArithmeticError, ValueError, np.linalg.LinAlgError) as exc:
            raise RuntimeError("Transient contact reconstruction failed numerically.") from exc
        extrema = []
        for root in shifted.deriv().roots():
            if abs(float(np.imag(root))) <= 512 * _EPS and 0 < float(np.real(root)) < 1:
                extrema.append(float(np.real(root)))
        boundaries = [0.0, *sorted(set(extrema)), 1.0]
        values = [float(shifted(x)) for x in boundaries]
        values[0], values[-1] = y0[0] - stop, y1[0] - stop  # exact endpoints
        scale = max(1.0, abs(stop), *(abs(value) for value in angles))
        angle_tol = max(8 * controls.atol, 2 * math.ulp(scale))
        velocity_tol = max(
            8 * controls.atol_angular_velocity_rad_s,
            2 * math.ulp(scale) / width,
        )
        roots = []
        for index, (left, right) in enumerate(zip(boundaries, boundaries[1:])):
            left_value, right_value = values[index:index + 2]
            # A merely close interval endpoint is not a hit; otherwise a
            # stationary in-bounds state can be reported as contact forever.
            if left_value == 0.0:
                roots.append(left)
            if left_value * right_value < 0:
                try:
                    roots.append(float(brentq(shifted, left, right, xtol=1e-14, rtol=1e-14)))
                except (ValueError, RuntimeError, ArithmeticError) as exc:
                    raise RuntimeError("Transient contact root is numerically ambiguous.") from exc
            if index == len(boundaries) - 2 and right_value == 0.0:
                roots.append(right)
        # A near-zero interior extremum can be a tangent contact.  Small-scale
        # cases within the requested state tolerance are accepted; at large
        # scales an unresolved tangent fails closed instead of inventing a hit.
        for extremum, value in zip(boundaries[1:-1], values[1:-1]):
            if extremum not in roots and abs(value) <= angle_tol:
                if abs(value) <= 8 * controls.atol:
                    roots.append(extremum)
                else:
                    raise RuntimeError("Transient contact root is numerically ambiguous.")
        for root in sorted(set(roots)):
            event_time = start + width * root
            event_state = dense(event_time)
            theta, velocity = _number("contact angle", event_state[0]), _number("contact velocity", event_state[1])
            if abs(theta - stop) > 4 * angle_tol:
                raise RuntimeError("Transient contact reconstruction is numerically ambiguous.")
            if ((direction > 0 and velocity >= -velocity_tol)
                    or (direction < 0 and velocity <= velocity_tol)):
                candidates.append((event_time, name))
                break
        breached = (
            max(float(shifted(x)) for x in boundaries) > angle_tol
            if direction > 0
            else min(float(shifted(x)) for x in boundaries) < -angle_tol
        )
        if breached and not any(candidate_name == name for _, candidate_name in candidates):
            raise RuntimeError("Transient stop crossing is numerically ambiguous.")
    if not candidates:
        return None
    event_time, name = min(candidates)
    event_state = dense(event_time)
    stop = parameters.lower_stop_rad if name == "lower" else parameters.upper_stop_rad
    return name, event_time, (stop, _number("contact velocity", event_state[1]))


def solve_mechanism_transient(request: TransientRequest) -> TransientResult:
    if not isinstance(request, TransientRequest):
        raise ValueError("Expected a validated transient request.")
    p, d, c = request.parameters, request.drive, request.controls
    origin = d.time_s[0]
    knots = tuple(value - origin for value in d.time_s)
    times, states, segment_starts = [], [], []
    state = (request.initial_angle_rad, request.initial_angular_velocity_rad_s)
    contact = None
    contact_segment = None
    evaluations = 0

    class _BudgetExceeded(RuntimeError):
        pass

    def drive_at(t, index):
        t0, t1 = knots[index:index + 2]
        fraction = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
        rpm = d.rpm[index] + fraction * (d.rpm[index + 1] - d.rpm[index])
        torque = d.applied_hinge_torque_nm[index] + fraction * (d.applied_hinge_torque_nm[index + 1] - d.applied_hinge_torque_nm[index])
        alpha = (d.rpm[index + 1] - d.rpm[index]) * RPM_TO_RAD_S / (t1 - t0)
        return _number("RPM", rpm * RPM_TO_RAD_S), _number("angular acceleration", alpha), _number("applied torque", torque)

    def torques(t, theta, velocity, index):
        omega, alpha, applied = drive_at(t, index)
        try:
            spring = -p.spring_stiffness_nm_rad * (theta - p.rest_angle_rad)
            damping = -p.viscous_damping_nm_s_rad * velocity
            friction = (0.0 if p.dry_friction.mode == "none" else
                        -p.dry_friction.coulomb_torque_nm * math.tanh(velocity / p.dry_friction.transition_velocity_rad_s))
            centrifugal = -p.mass_kg * p.hinge_radius_m * p.cg_distance_m * omega**2 * math.sin(theta)
            euler = -(p.hinge_inertia_kg_m2 + p.mass_kg * p.hinge_radius_m * p.cg_distance_m * math.cos(theta)) * alpha
        except (ArithmeticError, ValueError) as exc:
            raise RuntimeError("Transient torque evaluation overflowed numerically.") from exc
        return tuple(_number("torque", value) for value in (applied, spring, damping, friction, centrifugal, euler, omega))

    def rhs(t, y, index):
        nonlocal evaluations
        evaluations += 1
        if evaluations > 8 * c.max_samples:
            raise _BudgetExceeded("Transient evaluation budget exceeded.")
        theta, velocity = _number("state angle", y[0]), _number("state velocity", y[1])
        applied, spring, damping, friction, centrifugal, euler, _ = torques(t, theta, velocity, index)
        acceleration = _number("acceleration", (applied + spring + damping + friction + centrifugal + euler) / p.hinge_inertia_kg_m2)
        return velocity, acceleration

    for index, (start, end) in enumerate(zip(knots, knots[1:])):
        segment_starts.append(len(times) - (1 if times else 0))
        if not times:
            times.append(start)
            states.append(state)
        try:
            solver = RK45(lambda t, y: rhs(t, y, index), start, state, end,
                          max_step=c.max_step_s, rtol=c.rtol,
                          atol=(c.atol, c.atol_angular_velocity_rad_s))
            while solver.status == "running":
                previous_time = float(solver.t)
                previous_state = (_number("state angle", solver.y[0]), _number("state velocity", solver.y[1]))
                solver.step()
                if solver.status == "failed":
                    raise RuntimeError("Transient integration failed.")
                current_time = float(solver.t)
                current_state = (_number("state angle", solver.y[0]), _number("state velocity", solver.y[1]))
                hit = _first_contact(solver.dense_output(), previous_time, current_time,
                                     previous_state, current_state, p, c)
                if hit:
                    name, event_time, event_state = hit
                    times.append(event_time)
                    states.append(event_state)
                    if len(times) > c.max_samples:
                        raise _BudgetExceeded("Transient sample budget exceeded.")
                    contact = StopContact(name, _number("contact time", origin + event_time),
                                          event_state[0], event_state[1])
                    contact_segment = index
                    break
                times.append(current_time)
                states.append(current_state)
                if len(times) > c.max_samples:
                    raise _BudgetExceeded("Transient sample budget exceeded.")
        except _BudgetExceeded as exc:
            raise RuntimeError(str(exc)) from exc
        except (ArithmeticError, ValueError, FloatingPointError) as exc:
            raise RuntimeError("Transient integration failed numerically.") from exc
        state = states[-1]
        if contact:
            break

    absolute_times = [_number("output time", origin + value) for value in times]
    output = {name: [] for name in ("rpm", "omega", "alpha", "applied", "spring", "damping", "friction", "centrifugal", "euler", "acceleration", "energy", "applied_power", "damping_power", "friction_power", "total_power")}
    for sample_index, (t, (theta, velocity)) in enumerate(zip(times, states)):
        index = min(len(knots) - 2, max(0, bisect_right(knots, t) - 1))
        if contact and sample_index == len(times) - 1 and contact_segment is not None:
            index = contact_segment
        applied, spring, damping, friction, centrifugal, euler, omega = torques(t, theta, velocity, index)
        alpha = (d.rpm[index + 1] - d.rpm[index]) * RPM_TO_RAD_S / (knots[index + 1] - knots[index])
        acceleration = _number("output acceleration", (applied + spring + damping + friction + centrifugal + euler) / p.hinge_inertia_kg_m2)
        try:
            energy = (0.5 * p.hinge_inertia_kg_m2 * velocity**2
                      + 0.5 * p.spring_stiffness_nm_rad * (theta - p.rest_angle_rad)**2
                      + p.mass_kg * p.hinge_radius_m * p.cg_distance_m * omega**2 * (1 - math.cos(theta)))
            applied_power, damping_power, friction_power = applied * velocity, -damping * velocity, -friction * velocity
        except (ArithmeticError, ValueError) as exc:
            raise RuntimeError("Transient output evaluation overflowed numerically.") from exc
        for name, value in (("rpm", omega / RPM_TO_RAD_S), ("omega", omega), ("alpha", alpha),
                            ("applied", applied), ("spring", spring), ("damping", damping),
                            ("friction", friction), ("centrifugal", centrifugal), ("euler", euler),
                            ("acceleration", acceleration), ("energy", energy),
                            ("applied_power", applied_power), ("damping_power", max(0.0, damping_power)),
                            ("friction_power", max(0.0, friction_power)),
                            ("total_power", max(0.0, damping_power + friction_power))):
            output[name].append(_number(name, value))

    applied_work = _integral(absolute_times, output["applied_power"])
    viscous_loss = _integral(absolute_times, output["damping_power"])
    friction_loss = _integral(absolute_times, output["friction_power"])
    total_loss = [_number("total dissipation", a + b) for a, b in zip(viscous_loss, friction_loss)]
    return TransientResult(
        "stop_contact" if contact else "completed",
        "Integration terminated at first stop contact." if contact else "Drive history completed without stop contact.",
        tuple(absolute_times), tuple(x[0] for x in states), tuple(x[1] for x in states),
        tuple(output["acceleration"]), tuple(output["rpm"]), tuple(output["omega"]),
        tuple(output["alpha"]), tuple(output["applied"]), tuple(output["spring"]),
        tuple(output["damping"]), tuple(output["friction"]), tuple(output["centrifugal"]),
        tuple(output["euler"]), tuple(output["energy"]), tuple(output["applied_power"]),
        tuple(output["damping_power"]), tuple(output["friction_power"]), tuple(output["total_power"]),
        tuple(applied_work), tuple(viscous_loss), tuple(friction_loss), tuple(total_loss),
        tuple(segment_starts), contact)
