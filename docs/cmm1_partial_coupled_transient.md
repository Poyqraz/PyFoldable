# CMM-1 — partial coupled screening transient

CMM-1 is a bounded numerical screening model. It is not full deployment
physics, physical qualification, aerodynamic hinge-load qualification,
deep-stow simulation, startup from rest, GEOM clearance promotion,
calibration, or optimization.

`model_class` is `partial_coupled_screening_only`.
`physical_qualification` is false.
`aerodynamic_hinge_torque_status` is `unavailable_omitted_by_cmm1`.
`full_propeller_clearance`, `surface_path_clearance`, and
`interblade_clearance` stay null. A missing aerodynamic hinge moment is an
omitted term, not a measured, negligible, or validated zero. The report does
not publish `aerodynamic_hinge_torque_nm`.

CMM-2, a reviewed local aerodynamic hinge load, is not approved.

## States and sign convention

The dynamic state is `theta_rad`, `theta_dot_rad_s`, and `omega_rad_s`.
Shaft azimuth is not a state. Current is algebraic.

- `+z` is the positive shaft direction and `omega > 0`.
- `theta = 0` is deployed. `theta < 0` is folded.
- `theta_dot > 0` opens a negatively folded tip.
- Positive motor torque `Qm` drives `+z`.
- Positive whole-rotor BEM torque `Qa` is shaft drag and enters as `-Qa`.

For one movable tip, `C = m R c`, `A = J + m R^2 + 2 C cos(theta)`, and
`B = J + C cos(theta)`. For `N` identical synchronous tips and sourced base
inertia `I0`:

```text
M = [[I0 + N A,  N B],
     [N B,       N J]]
```

```text
M [omega_dot, theta_ddot]^T
  = [Qm - Qa + N C sin(theta) (2 omega theta_dot + theta_dot^2),
     N (Qh - k (theta - theta_rest) - b theta_dot
        - tau_c tanh(theta_dot / v_transition)
        - C omega^2 sin(theta))]
```

`Q_h,aero` is absent. With a prescribed `omega` and `omega_dot`, dividing the
hinge row by `N` is the PY-05 hinge equation. PY-05 itself is not modified.

`N` multiplies movable-tip inertia, spring, damping, friction, and one-hinge
actuation. It does not multiply `I0`, whole-rotor `Qa`, or `Qm`.

## Base inertia and regularity

`BaseRotatingAssemblyInertia` stores `inertia_kg_m2 > 0`, a nonempty source,
and a nonempty immutable component inventory. The exclusion flag must be true:
`I0` is the `+z` inertia of shaft-locked hardware excluding every modeled
movable tip. The value is not inferred from CAD, material names, blade shape,
or motor metadata.

```text
det M = N J I0 + N^2 m R^2 (J - m c^2 cos^2(theta))
```

The existing mechanism binding still requires `J >= m c^2`. CMM-1 also
requires `I0 > 0`. Regularity uses the analytical positive Schur complement
`det M / (N J)` and a scaled residual of `M x - rhs`. There is no absolute
determinant epsilon. The point-mass boundary `J = m c^2` with `I0 > 0` stays
regular. Singular, unresolved, or nonfinite systems fail closed.

## Motor, BEM, and domains

Motor voltage, back-EMF, current-dependent resistance, no-load current, torque
constant, line resistance, and battery voltage are the PR-07 algebraic state
exposed by `algebraic_motor_state`. That adapter does not change PR-07
equations. CMM-1 adds a domain gate: applied voltage must exceed back-EMF,
current must not exceed `current_max`, and current must not fall below the
no-load current. Those cases raise a domain exit. Current is not clipped.
Throttle is one constant in `(0, 1]`. There is no inductance ODE, SOC model,
ESC model, controller, regeneration, or reverse operation.
`magnetic_lag_tau` keeps its PR-07 meaning.

Each accepted right-hand side builds `FoldableRotorState(theta)`, projects it,
and solves `solve_foldable_bem_rotor` at `angular_speed_rad_s = omega` with
the fixed environment. `rotor_result.torque_nm` is `Qa`. Thrust is diagnostic
only. Hinge torque is not inferred from thrust, rotor torque, `Cm`, or a
lever arm. Caller `BEMRotorSettings`, loading branch, and `bounds="error"`
are preserved. Clamp and branch substitution are rejected.

The aerodynamic model is quasi-steady and radial-cosine. It has no
`theta_dot` airflow. Its qualification string remains
`screening_only_until_pr06c_passes`. The fold domain is
`abs(theta) < pi/2` plus the projection's positive-radius check. A deeper
stowed stop does not authorize a start there. The v1 shaft floor is 100 rpm,
`omega_min = 100 * 2 pi / 60`, inherited from the PR-07 default search bound.
It is not evidence that BEM physics are validated at 100 rpm. No accepted BEM
evaluation runs below that floor, at zero rpm, or in reverse.

Initial angle, hinge rate, and shaft speed are explicit. The angle must lie
strictly inside the mechanism stops and inside the fold domain. The solver
does not project or clamp the initial state.

## Contact, failure, and budgets

Contact reuses the PY-05 `first_contact_terminal` reconstruction. The first
hit records the stop, time, angle, pre-impact hinge rate, and shaft speed,
then stops. There is no impact reaction, rebound, latch, static hold, or
clamp-and-continue.

Hard failures, including BEM nonconvergence, polar-domain failure, nonfinite
arithmetic, a singular mass matrix, motor failure, and work-budget exhaustion,
raise and do not return a shortened success. v1 does not locate a
`model_domain_exit` terminal inside a step. Leaving the fold or speed domain
fails closed instead of inventing a terminal point. No zero, frozen, clamped,
or extrapolated aerodynamic load is substituted.

The integrator is adaptive RK45, restarted at each hinge-actuation knot.
Ceilings are software limits, not accuracy claims: `max_duration_s <= 2`,
`max_step_s <= 0.002`, `max_samples <= 5000`, `max_rhs_evaluations <= 12000`,
and `max_input_knots <= 256`.

Pure dynamics tests may inject analytic shaft loads. The source-bound service
builds only `Pr07MotorEvaluator` and `FoldableBemShaftEvaluator` and rejects
other callables. A synthetic evaluator is not stored as physical evidence.

## Energy and provenance

```text
T = 1/2 (I0 + N A) omega^2 + N B omega theta_dot + 1/2 N J theta_dot^2
V = 1/2 N k (theta - theta_rest)^2
E_dot = (Qm - Qa) omega + N Qh theta_dot - N b theta_dot^2
        - N tau_c theta_dot tanh(theta_dot / v)
```

There is no aerodynamic hinge work and no claim of battery-to-mechanics
conservation. Electrical diagnostics stay on the PR-07 sample.

The sealed input hash covers the draft and source hashes, one-tip mass
distribution, derived mass properties, `I0` value, source and inventory,
motor, battery, system, throttle, fixed environment, polar identity, BEM
settings, bounds, solver controls, initial state, and hinge-actuation history.
Hash identity is not source authentication or physical qualification. A
tampered binding is rejected. The report repeats the limitations above,
including unresolved PR-06C, omitted hinge load, no dynamic clearance, and
unqualified inertia unless a separate measurement exists.

Code: `pyfoldable/dynamics/coupled_transient.py`,
`pyfoldable/application/coupled_transient_service.py`. Decision: ADR-005.
