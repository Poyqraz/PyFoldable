# PR-09 structural/FEA contract execution plan

## Objective

Create the fail-closed boundary between the revision-controlled SolidWorks design,
material characterization, ANSYS Mechanical load cases, and PyFoldable evidence.
This increment prepares and validates inputs/results; it does not fabricate stress,
fatigue, contact, or modal predictions.

## Required analysis cases

1. maximum-RPM steady centrifugal/aerodynamic loading;
2. peak opening-stop transient/contact loading;
3. declared imbalance loading at maximum RPM;
4. modal separation across the operating-speed envelope;
5. fatigue duty-cycle assessment for blade, hinge, pin, lock, and stop regions.

## Test-driven gates

- CAD identity requires revision, format, units, coordinate frame, and SHA-256.
- Material identity requires a source and explicitly states isotropic/orthotropic
  scope; PA-CF cannot be promoted from an unverified generic card.
- Every case declares its load source and required output metrics.
- Results must match CAD/material/case identities and ANSYS version.
- At least three mesh levels, convergence history, and unit-labelled metrics are
  required before an analysis case can pass the evidence gate.
- Missing cases, mismatched hashes, incomplete metrics, solver non-convergence, or
  unapproved warnings fail closed.
- Safety-factor, fatigue-life, displacement, contact-pressure, and modal-margin
  acceptance limits are project inputs; the validator never invents them.

## Completion boundary

The software/preparation gate is complete when a synthetic first-party fixture proves
the contract and the canonical project manifest reports its actual missing inputs.
Physical qualification remains pending until the real CAD revision, PA-CF/pin/lock
material cards, declared loads, and ANSYS result bundle are supplied.
