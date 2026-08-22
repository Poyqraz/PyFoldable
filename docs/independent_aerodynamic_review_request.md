# Independent aerodynamic review and ANSYS evidence request

## Purpose

This work package asks an independent engineer to test the fixed and foldable rotor
model, not merely to produce attractive flow images. Published APC Slow Flyer 10x4.7
CFD results provide useful setup checks, while the frozen UIUC measurements remain the
physical reference. The review is not complete until geometry identity, numerical
uncertainty, raw outputs, and the engineer's signed conclusion are all traceable.

## Mandatory baseline

1. Use the exact APC Slow Flyer 10x4.7 blade geometry and record the CAD source,
   revision, units, blade count, diameter, pitch, hub, coordinate system, and a geometry
   SHA-256. A nominal product name alone is insufficient.
2. Reproduce the UIUC static cases at 4319 and 6528 rpm. Report `CT`, `CP`, thrust,
   torque, shaft power, air properties, and coefficient definitions. The published ICAS
   reference gives UIUC `CP = 0.0474/0.0531`; its 3.2-million-cell SST k-omega results
   are `0.0480/0.0528`.
3. Include at least one full forward-flight curve from the frozen UIUC matrix, preferably
   6020 rpm over `J = 0.408..0.652`, plus the 6512 rpm low-to-moderate `J` range. Static
   agreement alone cannot close PR-06C.
4. Run three systematically refined meshes. Report cell counts, refinement ratios,
   near-wall layers, first-layer height, growth rate, skewness/orthogonal quality,
   `y+` distributions, and a Grid Convergence Index or equivalent observed-order
   uncertainty for `CT` and `CP`.
5. Use SST k-omega as the primary RANS model and compare at least one turbulence or
   transition alternative. Explain wall treatment and whether the achieved `y+` matches
   it. Do not select a model from residual convergence alone.

## Solver and boundary-condition record

- ANSYS/Fluent release and build, steady MRF or transient sliding-mesh choice, pressure-
  velocity coupling, gradient and spatial schemes, initialization, time step/rotor-angle
  increment, inner iterations, and all relaxation factors.
- Rotor/stator domain dimensions normalized by diameter; interface type; inlet, outlet,
  lateral, periodic/symmetry, and blade-wall conditions; turbulence intensity and length
  scale; reference pressure and rotating-frame sign convention.
- Residual history plus iteration/time histories of thrust and torque. Acceptance needs
  stabilized integral loads and mass balance, not an arbitrary residual count.
- For at least one case, compare steady MRF against transient sliding mesh and report
  mean, peak-to-peak variation, averaging window, and periodicity.

## Foldable cases

After the fixed baseline is credible, evaluate deployed, 30-degree, and 60-degree fold
states using the same material blade and hinge definition. Record whether geometry is a
true 3-D hinged blade or the PyFoldable radial-cosine projection. Report effective
diameter, clearance, thrust, torque, radial loading, hinge moment, and asymmetric force/
moment components. The current 0/15/30/45/60-degree PyFoldable sweep is screening-only
and must not be used as CFD truth.

## Files to deliver

- Native case/project files or a solver archive, revisioned CAD/mesh, journal/script,
  and a machine-readable case manifest (`JSON` or `CSV`).
- Per-case raw iteration/time histories and surface-integrated force/moment exports;
  spanwise loading; convergence and mesh-independence tables.
- Pressure, velocity/vorticity, wall shear, `y+`, and wake-plane fields. Images accompany
  numeric exports and never replace them.
- A comparison table with UIUC, published CFD, ANSYS review, and PyFoldable values using
  identical coefficient definitions and signed percent errors.
- A short signed review stating pass/fail for geometry identity, numerical convergence,
  static `CT/CP`, forward-flight `CT/CP`, model-form findings, uncertainty, limitations,
  and recommended action. Any omitted item must be declared explicitly.

## Promotion boundary

Published literature and a new ANSYS run can inform the model, but only the independent
review of the exact PyFoldable inputs/outputs can satisfy the review gate. The frozen
PR-06C thresholds and UIUC fixture must not be edited to obtain a pass. Raw evidence is
captured first; promotion is a separate, reviewable decision.
