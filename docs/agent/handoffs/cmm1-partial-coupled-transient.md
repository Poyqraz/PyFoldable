# Handoff — CMM-1 partial coupled screening transient

## Purpose

Implement the reviewed CMM-1 screening transient as a new workflow. Do not
replace PY-05, change PR-07 equations, or promote GEOM clearance.

## Base

`origin/main` at `aadfeaccd7867645706221532c467498fde4720f`.

## What landed

- Pure dynamics in `pyfoldable/dynamics/coupled_transient.py`.
- Source-bound service in `pyfoldable/application/coupled_transient_service.py`.
- Public PR-07 adapter `algebraic_motor_state` with no equation change.
- Focused dynamics and application tests.
- ADR-005 and `docs/cmm1_partial_coupled_transient.md`.
- Short roadmap, execution-plan, current-state, and PY-05 boundary notes.

## What did not land

- Dashboard changes.
- CMM-2 aerodynamic hinge torque.
- A successful `model_domain_exit` event locator. Domain departure fails closed.
- Physical qualification, calibration, optimization, or GEOM `True`.
- Any change to PY-05, PR-07 equilibrium behavior, BEM equations, or GEOM #67–#69.

## Review

An independent read of the equations, domain gates, motor adapter, and BEM
failure path found no blocker. That review is not GitHub CI and not Bugbot.
Do not merge until exact-head Python 3.10 and 3.11 CI is green and any
external review is closed.

## Next action

Wait for exact-head CI. Do not merge from this handoff. PY-06D2 remains
blocked without identifiable measurements.
