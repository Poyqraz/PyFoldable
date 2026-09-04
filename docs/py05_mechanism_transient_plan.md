# PY-05A — prescribed-rotation mechanism transient

> Historical first-slice plan. The subsequent PY-05A corrections and PY-05B
> implementation are recorded in [PY-05 completion](py05_completion.md).

## Decision and evidence boundary — 2026-09-03

PY-05A extends PY-04A without changing PR #3, legacy dynamics, benchmarks or
physical gates. It supplies an explicit-SI, one-degree-of-freedom planar rigid
hinge solver, a source-bound JSON application service, and a separate mechanism
workbench. It is not coupled to the active blade mesh, BEM or motor dynamics and
does not contain a collision model. Every report remains
`physical_qualification=false`.

The equation/method research was completed before implementation. Gutierrez-
Prieto, Gomez & Reis (2024) supports the centrifugal/Euler rotating-frame force
definitions; Chen (NASA TM-100023, 1987) supports the broad articulated rigid-
rotor/Lagrange context, not this exact equation. SciPy's `solve_ivp` documentation
supports bounded RK45 and directed terminal events. Yang et al. (2022) supplies
only a clearly separated nonrotating aluminium-rig modal example: `I=0.0051 kg
m²`, `ωn=15.237 rad/s`, and `ζ=0.111`. No matching 250 mm PA-CF prototype
parameter set was found.

The Yang example derives `k=I ωn²` and `b=2 I ωn ζ`; those values are effective
modal coefficients, not measured individual spring stiffness or a reconstruction
of the four-hinge rig. Its other mass, geometry, limits, initial state and drive
values are illustrative. Literature values are never promoted to prototype
measurements.

## Coordinates and model

The fixed spin axis is +z. Counterclockwise `Ω` and `θ` are positive, `θ=0` is
radially outward, and negative `θ` is the folded side. The hinge lies at radius
`R`; the rigid body's CG is distance `c` from it. `J` is inertia about the hinge
and must satisfy `J >= m c²`.

```text
T = J(Ω + θdot)²/2 + mR²Ω²/2 + mRc Ω(Ω + θdot) cosθ

J θddot = Q - k(θ-θrest) - b θdot
            - mRc Ω² sinθ - (J + mRc cosθ) Ωdot
```

`Q` is prescribed hinge-axis torque, never rotor-shaft torque or inferred thrust
moment. Relative-velocity rotating terms cancel for this restricted topology;
that is not a general dismissal of Coriolis effects. Gravity, aerodynamics and
dry friction are absent unless a future contract adds them explicitly.

## Numerical and contract decisions

* RPM and hinge torque are continuous piecewise-linear histories. RPM slope is
  constant within each segment, and RK45 is restarted at every declared knot.
* Lower and upper stops are directed terminal events. The first event ends the
  solution and records pre-impact angular velocity. There is no continuation,
  clamp, latch, contact reaction, restitution or bounce.
* Inputs are frozen finite scalar models with positive/physical inertia, ordered
  knots, strict initial-angle interior, bounded tolerances, duration, knots and
  samples. Failed/incomplete solves do not produce a successful report.
* The JSON retains the raw request, per-input provenance, implementation file
  hashes, runtime identity, solver controls, all samples, request hash and
  limitations. The service artifact exposes a report hash over the exact JSON
  bytes (outside the JSON, avoiding a recursive checksum). SHA-256 identifies
  content; it does not authenticate a source or qualify physics.
* The Streamlit workbench uses explicit user-declared values and a separate run
  button. Input changes or invalid input remove stale session results/downloads.

Tests cover the analytic zero-RPM oscillator, viscous energy decay, the `R=0`
inertial-angle invariant, constant-RPM centrifugal moment, Euler acceleration
sign, first-contact time/velocity, knot restart/continuity, strict budgets,
reproducible identities, provenance completeness and UI invalidation.

## Deferred scope

PY-05B must add validated active-geometry/mass-property binding and explicit dry-
friction/contact contracts. Active blade/BEM/motor coupling, aerodynamic hinge
moments, measured RPM histories, arbitrary hinge axes, gravity, restitution,
locking and physical deployment qualification remain later work. The 140 mm
geometry conflict and PR-06C/09/10 evidence gates are unchanged. Manufacturing,
print orientation and robust/Pareto recommendations are outside this slice.

## Sources

* Gutierrez-Prieto, Gomez & Reis, *Extreme Mechanics Letters* 72 (2024), 102246:
  <https://doi.org/10.1016/j.eml.2024.102246>
* Chen, NASA TM-100023 (1987):
  <https://ntrs.nasa.gov/citations/19880005158>
* Yang et al., *Data in Brief* 43 (2022), 108388:
  <https://doi.org/10.1016/j.dib.2022.108388>
* Yang raw identification dataset, version 1:
  <https://doi.org/10.17632/fnw2jrwwhx.1>
* SciPy `solve_ivp` API:
  <https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html>
