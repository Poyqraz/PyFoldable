"""Explicit-SI prescribed-rotation model for one planar rigid hinge body.

The solution terminates at first stop contact.  Contact reaction, restitution,
latching, dry friction, aerodynamics and motor/rotor coupling are deliberately
outside this first mechanism-transient slice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.integrate import solve_ivp

RPM_TO_RAD_S = 2.0 * math.pi / 60.0


def _finite(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite scalar.")


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

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            _finite(name, value)
        if self.mass_kg <= 0 or self.cg_distance_m < 0 or self.hinge_radius_m < 0:
            raise ValueError("Mass must be positive and SI distances nonnegative.")
        if self.hinge_inertia_kg_m2 <= 0 or self.hinge_inertia_kg_m2 < self.mass_kg * self.cg_distance_m**2:
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
        if any(not isinstance(values, tuple) for values in (self.time_s, self.rpm, self.applied_hinge_torque_nm)):
            raise ValueError("Drive histories must be immutable tuples.")
        if len(self.time_s) < 2 or len(self.time_s) != len(self.rpm) or len(self.rpm) != len(self.applied_hinge_torque_nm):
            raise ValueError("Drive histories require equal-length arrays with at least two knots.")
        for values in (self.time_s, self.rpm, self.applied_hinge_torque_nm):
            for value in values:
                _finite("drive history value", value)
        if self.time_s[0] < 0 or any(b <= a for a, b in zip(self.time_s, self.time_s[1:])):
            raise ValueError("Drive knot times must be nonnegative and strictly increasing.")
        if any(value < 0 for value in self.rpm):
            raise ValueError("RPM must be nonnegative.")


@dataclass(frozen=True)
class SolverControls:
    rtol: float = 1e-8
    atol: float = 1e-10
    max_step_s: float = 0.002
    max_samples: int = 50_000
    max_knots: int = 256
    max_duration_s: float = 60.0

    def __post_init__(self) -> None:
        for name in ("rtol", "atol", "max_step_s", "max_duration_s"):
            _finite(name, getattr(self, name))
        if not (0 < self.rtol <= 1e-3 and 0 < self.atol <= 1e-5 and self.max_step_s > 0):
            raise ValueError("Solver tolerances and maximum step are outside the bounded budget.")
        if not isinstance(self.max_samples, int) or self.max_samples < 100 or self.max_samples > 1_000_000:
            raise ValueError("Sample budget must be an integer from 100 to 1000000.")
        if not isinstance(self.max_knots, int) or not 2 <= self.max_knots <= 4096 or not 0 < self.max_duration_s <= 3600:
            raise ValueError("Knot or duration budget is invalid.")


@dataclass(frozen=True)
class TransientRequest:
    parameters: MechanismParameters
    drive: DriveHistory
    initial_angle_rad: float
    initial_angular_velocity_rad_s: float
    controls: SolverControls = SolverControls()

    def __post_init__(self) -> None:
        if not isinstance(self.parameters, MechanismParameters) or not isinstance(self.drive, DriveHistory) or not isinstance(self.controls, SolverControls):
            raise ValueError("Request requires validated parameter, drive and control models.")
        _finite("initial_angle_rad", self.initial_angle_rad)
        _finite("initial_angular_velocity_rad_s", self.initial_angular_velocity_rad_s)
        if not self.parameters.lower_stop_rad < self.initial_angle_rad < self.parameters.upper_stop_rad:
            raise ValueError("Initial angle must lie strictly inside both stops.")
        if len(self.drive.time_s) > self.controls.max_knots or self.drive.time_s[-1] - self.drive.time_s[0] > self.controls.max_duration_s:
            raise ValueError("Drive history exceeds the solver budget.")


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
    centrifugal_torque_nm: tuple[float, ...]
    euler_torque_nm: tuple[float, ...]
    effective_energy_j: tuple[float, ...]
    damping_power_w: tuple[float, ...]
    segment_start_indices: tuple[int, ...]
    contact: StopContact | None


def solve_mechanism_transient(request: TransientRequest) -> TransientResult:
    if not isinstance(request, TransientRequest):
        raise ValueError("Expected a validated transient request.")
    p, d, c = request.parameters, request.drive, request.controls
    times: list[float] = []
    states: list[tuple[float, float]] = []
    segment_starts: list[int] = []
    state = (request.initial_angle_rad, request.initial_angular_velocity_rad_s)
    contact = None
    contact_segment: int | None = None
    evaluations = 0

    class _BudgetExceeded(RuntimeError):
        pass

    def drive_at(t: float, index: int) -> tuple[float, float, float]:
        t0, t1 = d.time_s[index:index + 2]
        fraction = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
        rpm = d.rpm[index] + fraction * (d.rpm[index + 1] - d.rpm[index])
        torque = d.applied_hinge_torque_nm[index] + fraction * (
            d.applied_hinge_torque_nm[index + 1] - d.applied_hinge_torque_nm[index])
        alpha = (d.rpm[index + 1] - d.rpm[index]) * RPM_TO_RAD_S / (t1 - t0)
        return rpm * RPM_TO_RAD_S, alpha, torque

    def rhs(t: float, y: tuple[float, float], index: int) -> tuple[float, float]:
        nonlocal evaluations
        evaluations += 1
        if evaluations > 8 * c.max_samples:
            raise _BudgetExceeded("Transient evaluation budget exceeded.")
        theta, velocity = y
        omega, alpha, applied = drive_at(t, index)
        centrifugal = -p.mass_kg * p.hinge_radius_m * p.cg_distance_m * omega**2 * math.sin(theta)
        euler = -(p.hinge_inertia_kg_m2 + p.mass_kg * p.hinge_radius_m * p.cg_distance_m * math.cos(theta)) * alpha
        spring = -p.spring_stiffness_nm_rad * (theta - p.rest_angle_rad)
        damping = -p.viscous_damping_nm_s_rad * velocity
        return velocity, (applied + spring + damping + centrifugal + euler) / p.hinge_inertia_kg_m2

    def lower(_t: float, y: tuple[float, float]) -> float:
        return y[0] - p.lower_stop_rad

    def upper(_t: float, y: tuple[float, float]) -> float:
        return y[0] - p.upper_stop_rad

    lower.terminal, lower.direction = True, -1
    upper.terminal, upper.direction = True, 1
    for index, (start, end) in enumerate(zip(d.time_s, d.time_s[1:])):
        segment_starts.append(len(times) - (1 if times else 0))
        try:
            solution = solve_ivp(lambda t, y: rhs(t, y, index), (start, end), state,
                                 method="RK45", rtol=c.rtol, atol=c.atol, max_step=c.max_step_s,
                                 events=(lower, upper))
        except _BudgetExceeded as exc:
            raise RuntimeError(str(exc)) from exc
        if not solution.success:
            raise RuntimeError(f"Transient integration failed: {solution.message}")
        begin = 1 if times else 0
        times.extend(float(value) for value in solution.t[begin:])
        states.extend((float(a), float(v)) for a, v in zip(solution.y[0, begin:], solution.y[1, begin:]))
        if len(times) > c.max_samples:
            raise RuntimeError("Transient sample budget exceeded.")
        state = (float(solution.y[0, -1]), float(solution.y[1, -1]))
        hit = next(((name, events[0]) for name, events in zip(("lower", "upper"), solution.y_events) if len(events)), None)
        if hit:
            name, event_state = hit
            contact = StopContact(name, float(solution.t[-1]), float(event_state[0]), float(event_state[1]))
            contact_segment = index
            break
    output = {name: [] for name in ("rpm", "omega", "alpha", "applied", "spring", "damping", "centrifugal", "euler", "acceleration", "energy", "damping_power")}
    for t, (theta, velocity) in zip(times, states):
        # Interior knots use the right-hand segment, matching the restarted ODE.
        index = min(len(d.time_s) - 2, max(0, next((i for i in range(len(d.time_s) - 1) if d.time_s[i] <= t < d.time_s[i + 1]), len(d.time_s) - 2)))
        # A terminal event exactly on a knot belongs to the segment that found it;
        # unlike an ordinary knot, the right-hand segment was never entered.
        if contact is not None and t == contact.time_s and contact_segment is not None:
            index = contact_segment
        omega, alpha, applied = drive_at(t, index)
        spring = -p.spring_stiffness_nm_rad * (theta - p.rest_angle_rad)
        damping = -p.viscous_damping_nm_s_rad * velocity
        centrifugal = -p.mass_kg * p.hinge_radius_m * p.cg_distance_m * omega**2 * math.sin(theta)
        euler = -(p.hinge_inertia_kg_m2 + p.mass_kg * p.hinge_radius_m * p.cg_distance_m * math.cos(theta)) * alpha
        output["rpm"].append(omega / RPM_TO_RAD_S); output["omega"].append(omega); output["alpha"].append(alpha)
        output["applied"].append(applied); output["spring"].append(spring); output["damping"].append(damping)
        output["centrifugal"].append(centrifugal); output["euler"].append(euler)
        output["acceleration"].append((applied + spring + damping + centrifugal + euler) / p.hinge_inertia_kg_m2)
        output["energy"].append(0.5 * p.hinge_inertia_kg_m2 * velocity**2 + 0.5 * p.spring_stiffness_nm_rad * (theta - p.rest_angle_rad)**2 + p.mass_kg * p.hinge_radius_m * p.cg_distance_m * omega**2 * (1 - math.cos(theta)))
        output["damping_power"].append(p.viscous_damping_nm_s_rad * velocity**2)
    return TransientResult("stop_contact" if contact else "completed", "Integration terminated at first stop contact." if contact else "Drive history completed without stop contact.", tuple(times), tuple(x[0] for x in states), tuple(x[1] for x in states), tuple(output["acceleration"]), tuple(output["rpm"]), tuple(output["omega"]), tuple(output["alpha"]), tuple(output["applied"]), tuple(output["spring"]), tuple(output["damping"]), tuple(output["centrifugal"]), tuple(output["euler"]), tuple(output["energy"]), tuple(output["damping_power"]), tuple(segment_starts), contact)
