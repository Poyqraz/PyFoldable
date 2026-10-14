# Jointed-blade performance and validation contract

Status: **PROPOSED / NOT IMPLEMENTED**. This document is a planning contract
for one distal hinged blade. It defines obligations, audits the services on
main `022b466303c59b8c0adb02f935f9c2f065b0e2b5`, and names one next evidence
packet. It does not run a solver, CFD, FEA, polar provider, trajectory, or
qualification gate.

`physical_qualification` stays false. PR-06C stays unresolved. GEOM clearance
results stay screening records. ADR-009 stays unaccepted. No acceptance limit
in this document is a number, because no project limit has been supplied.

## Objective

The distal segment must do four things:

1. Align with its parent blade when deployed.
2. Transfer the loads that cross the joint.
3. Rotate within declared vibration limits.
4. Fold and deploy within a declared motion domain.

Alignment, load transfer, vibration, and folding are separate obligations.
Satisfying one does not satisfy the others.

## One parent, three matched cases

One immutable parent blade, `P`, supplies the global station radius, chord,
twist, and profile identity. Cases A, B, and C are matched uses of that same
parent. A later comparison is valid only when all three name the same parent
bytes.

| Case | Mechanical state | What it is for |
| --- | --- | --- |
| A. Monolithic reference | No joint cut and no hinge degree of freedom | Reference loads and response of `P` |
| B. Deployed and restrained | Joint geometry is present and the hinge rate is held at zero | Deployed alignment, joint load path, and joint-on versus joint-off differences |
| C. Movable joint | The hinge coordinate moves through deployment, operation, and folding | Motion, clearance, terminal contact, and the closed envelope |

Inheritance rules:

- Station radius, chord, twist, and profile follow `P` unless a joint-difference
  record names a local change.
- A missing local change stays missing. It is not filled by interpolation, a
  zero, or a copied neighbor.
- Chord and twist are not reset at the hinge.
- The parent profile is not replaced by a different profile at the tip.
- Case A is not edited so that it matches Case B.
- Case C does not inherit the restraint used in Case B.

The canonical file `configs/designs/TIP_HINGED_250_CANONICAL.toml` is a schema
example for the 250 mm project. Its hinge radius and station rows are not, by
themselves, a selected joint or an as-built blade.

## Four evidence planes

These planes stay distinct even when they describe the same station.

| Plane | Meaning | What does not belong here |
| --- | --- | --- |
| Shared parent intent | Declared radius, chord, twist, profile, and the intended deployed alignment of `P` | Measured hardware, fastener cuts, and deflection |
| Actual joint geometry | The undeformed cut, gaps, steps, misalignment, and hardware in the design model | Load deflection and shop measurements |
| Deformation | Change of that geometry under load or rotation | The undeformed CAD or station table |
| As-built evidence | Measurements of a manufactured article, with method and uncertainty | A design-file hash or a synthetic fixture |

A content hash identifies bytes. It does not authenticate a measurement or
qualify a rotor. External CAD and STEP are optional. If they are absent, the
geometry fields that only those files could supply remain `absent`.

## Scenario separation

The 250 mm project blade and any 13-inch blade are different parents. This
contract does not scale diameter, hinge radius, mass, stiffness, or operating
condition from one scenario to the other. The next packet below is 250 mm
only. A 13-inch parent needs its own identified blade, joint declaration, and
evidence record.

## Obligations

Each row needs a source, an uncertainty statement, and an acceptance limit
before it can be used as a decision. This contract names the rows. It does
not supply those values.

### Deployed geometry

| Observable | Question |
| --- | --- |
| Radial gap | Is there an unsupported or overlapping radial interval at the joint? |
| Surface step | Do the parent and distal outer surfaces meet without a step? |
| Angular misalignment | What are the fold, pitch, and sweep angles of the distal segment relative to `P` when restrained? |
| Exposed hardware | Which fasteners, lugs, or latches stand outside the parent surface? |
| Joint tolerances | Which manufacturing tolerances apply to the gap, step, angle, and hardware, and which are absent? |

### Matched aerodynamics

Compare A and B, and later C, only at the same parent, atmosphere, shaft
speed, and flight speed. Report thrust, torque, and shaft power, plus the
coefficients the solver actually supports. At zero flight speed, propulsive
efficiency is unsupported rather than zero. A difference is published only
when both cases return a complete result. A failed case stays visible and
does not donate its loads to a total.

### Joint mechanism

| Observable | Accounting location |
| --- | --- |
| Joint stiffness | Hinge moment per angle, on the hinge coordinate |
| Backlash | Free angle or displacement before load transfer; absent if not measured |
| Mass, center, and inertia | The restrained and the moving segment, including hardware |
| Friction | Hinge-coordinate torque and its power |
| Damping | Hinge-coordinate torque proportional to hinge rate, if declared |
| Stop and latch | Contact event, retained state, and release condition |

### Rotation and blades

| Observable | Question |
| --- | --- |
| Centrifugal loading | Hinge moment and joint force from rotation, kept separate from aerodynamic load |
| Rotating modal response | Frequencies and mode shapes in the declared operating envelope, with the declared boundary |
| Imbalance | Mass or geometric difference among blades, not a residual of a moment balance |
| Blade-to-blade difference | Per-blade joint geometry or response; identical-blade multiplication is not this measurement |

### Deployment and folding

| Observable | Question |
| --- | --- |
| Motion domain | Declared angle and rate bounds from closed to deployed |
| Clearance | Separated, violating, or unknown over that path |
| Terminal contact | Stop or latch contact, distinguished from an unresolved near-contact |
| Closed envelope | The restrained folded outline against its declared requirement |

## Service audit on this main

The audit is against the tree at `022b466303c59b8c0adb02f935f9c2f065b0e2b5`.
Screening behavior below is software behavior. It is not joint-loss evidence.

### BEM

`pyfoldable/core/bem.py` solves one annulus with QPROP's psi parameterization.
Tip loss is inside that annulus and is on by default. Root loss is off by
default. `pyfoldable/core/bem_rotor.py` integrates those annuli and returns no
partial rotor total. The active-design service
`pyfoldable/application/design_analysis.py` calls that kernel only for a fully
open, zero-offset blade with one profile and `bounds="error"`.

That path has no joint gap, step, hardware, stiffness, friction, or hinge
rate. It can represent Case A only when the draft is exactly parent `P`. It
cannot represent Case B or Case C.

### Foldable projection

`pyfoldable/core/foldable_rotor.py` maps a prescribed hinge angle into the
rotor plane with `radial_cosine_v1`. Outboard station radius is projected.
Existing stations keep their chord, twist, and profile id. At a nonzero angle,
a hinge that falls between stations of the same profile inserts one station
whose chord and twist are linearly interpolated. At exactly zero angle from
deployed, that insertion does not run: the effective blade is the nominal
blade object, and `solve_foldable_bem_rotor` calls `solve_bem_rotor` on that
blade.

`FixedLimitEquivalenceCase.passed` requires that mapping equality and exact
zero thrust, torque, and coefficient deltas. The recorded qualification is
`software_equivalence_not_physical_accuracy`. A passed comparison shows that
the zero-angle software path matches the monolithic kernel. It does not show
that a joint is aligned, stiff, or free of loss.

Opening sweeps report thrust and torque ratios to the deployed software case.
They are prescribed-angle screens. They do not contain a restrained joint
geometry or a free hinge.

`pyfoldable/core/foldable_aero_load.py` integrates the same projected BEM
densities into a planar hinge load. The map is rate-independent. Section
pitching moment is not added as a hinge couple. A missing hinge integral
fails closed and is not published as zero. The mapped hinge load is not a
second aerodynamic model.

### CMM-2

The merged screening service is
`pyfoldable/application/cmm2_coupled_transient_service.py`. Each aerodynamic
evaluation calls `solve_foldable_bem_rotor` and then
`map_foldable_bem_aero_loads`. The dynamics implementation is
`cmm2_planar_projected_rate_independent_coupling_v1` in
`pyfoldable/dynamics/cmm2_coupled_transient.py`, integrated with RK45. The
Radau contract is a separate document and is not this service.

Dry friction enters each hinge equation as
`-coulomb_torque_nm * tanh(theta_dot / transition_velocity_rad_s)` through
`_friction_nm` in `pyfoldable/dynamics/coupled_transient.py`, when the friction
mode is `regularized_coulomb`. Mode `none` contributes zero. The recorded
friction power is the blade count times that one-hinge torque times hinge
rate. The legacy quasi-static balance in `pyfoldable/kinematics.py` adds
`hinge_friction_nm` as a constant resisting moment. Neither implementation
multiplies steady thrust or shaft torque by a friction factor.

CMM-2 records clearance fields and is required to leave
`full_propeller_clearance`, `surface_path_clearance`, and
`interblade_clearance` null. It does not evaluate GEOM-03 or GEOM-04.
`physical_qualification` is false. Leaving the fold-angle domain raises
`Cmm2DomainExit`. That hard failure returns no shortened trajectory. A
returned stop contact is the separate `first_contact_terminal` record, and
that record is not a measured latch.

### Geometry

`pyfoldable/application/parent_blade_generator.py` first builds a draft, which
can scale chord with diameter and `chord_scale` and twist with `twist_scale`.
It then copies that realized parent into fixed and tip children at two
declared hinge radii, without a further chord or twist reset. Joint
modifications are caller-supplied text rows. The report sets
`joint_clearance`, `joint_solid_geometry`, and `movable_mass_cg_inertia` to
null. Two copied station tables are not a joint solid. JVP-01 must bind the
parent bytes after any such draft scaling, and must not scale them again.

`pyfoldable/application/parent_blade_comparison.py` compares supplied bundles
and retains gaps. It does not create the joint.

`pyfoldable/application/mixed_profile_parent_geometry.py` can build declared
section coordinates. The supported model accepts a request only when
`actual_joint_modifications` is `UNDEFINED` and every hardware offset is the
zero vector. A cut copies those values. The zeros are admission constraints,
not a measurement that hardware is flush or absent. The service does not
establish solid, clearance, strength, or as-built equivalence.

GEOM-03 (`docs/geom03_surface_clearance.md`) classifies a supplied surface
path as `separated`, `violation`, or `unknown`. GEOM-04
(`docs/geom04_surface_hardware.md`) adds declared convex hardware and refined
distance. Hardware dimensions are not inferred. Neither service produces
aerodynamic deltas or rotating modes. `full_propeller_clearance` stays null.

`pyfoldable/application/folding_mechanism.py` audits planar hub clearance and
the stow path from diameter, hub radius, hinge radius, and fold angle. Station
`r/R` values are used for span coverage. `pyfoldable/application/mechanism_binding.py`
reduces a supplied one-tip radial mass distribution to mass, center, and
inertia. Those reductions are screening inputs, not as-built properties.

The literature modal example in
`pyfoldable/application/mechanism_transient.py` uses derived scalar stiffness
and damping for one hinge oscillator. The name `imbalance` in
`pyfoldable/dynamics/physics_stability.py` is the residual between centrifugal
and stiffness moments. It is not a blade mass imbalance.

## Absent physics

The following are not implemented for a jointed blade on this main:

- A joint gap, surface step, or angular misalignment inside BEM.
- Exposed hardware as an aerodynamic body.
- Joint backlash.
- Elastic deformation of the joint or blade under load or spin.
- A rotating modal solution, Campbell diagram, or declared vibration limit check.
- Per-blade mass or geometry imbalance.
- Blade-to-blade joint differences. Rotor BEM multiplies one representative blade.
- A hinge-friction contribution to steady thrust or torque.
- Transfer of GEOM clearance or contact into CMM-2.
- An as-built measurement chain for the joint.
- Acceptance limits and uncertainty values for any obligation above.

Perfect-open software equivalence is not evidence of joint loss. It is
evidence that the zero-angle projection did not change the monolithic BEM
inputs.

## Loss accounting

Each loss has one place in the equations.

| Loss | Where it is allowed | Where it must not be added again |
| --- | --- | --- |
| Profile drag | Section polar queried by BEM | A second drag table for the same section |
| Tip loss | The annulus tip-loss factor | Another tip factor after radial projection |
| Root loss | The annulus root-loss factor, only when that option is on | A hinge-gap model that silently repeats it |
| Aerodynamic hinge moment | The integral of the same projected BEM densities | Section pitching moment added again, or a second BEM solve |
| Hinge friction | One-hinge torque; recorded power is blade count times that torque times hinge rate | A steady thrust or power multiplier |
| Hinge damping | Hinge-coordinate torque from hinge rate | A change to the section polar |
| Stop or latch | Contact load on the hinge coordinate | An aerodynamic penalty |

Hinge friction must not be turned into an arbitrary steady thrust multiplier.
Doing so would count a hinge-coordinate torque as a rotor-force loss and
could count it twice if the hinge equation is also integrated.

## Next evidence packet

Packet id: `JVP-01`.

Title: deployed joint-difference identity for one 250 mm parent.

This packet records identity and absence. It does not solve aerodynamics,
structure, dynamics, or clearance.

### Prerequisites

1. One immutable parent station bundle for the 250 mm scenario, with its
   canonical hash, profile coordinate hash, and a statement that it is parent
   intent rather than as-built evidence.
2. One hinge radius strictly inside that parent span. The radius is an input
   to the packet, not a selected optimum.
3. Case A bytes equal to the parent bytes.
4. No 13-inch rows in the packet.
5. No use of the blocked two-profile polar study. Draft PR #97, head
   `ce023ba59ea84c0c39060d1a9dbc69f959c8fbe0`, remains a separate aerodynamic
   baseline issue. This packet does not narrow that polar envelope and does
   not call a polar provider.

### Scope

For that one hinge, write one source-bound record with these fields, each
marked `declared`, `measured`, or `absent`:

- radial gap;
- surface step;
- fold, pitch, and sweep misalignment of the restrained distal segment;
- exposed hardware identity and envelope;
- joint tolerances.

Case B may differ from Case A only through those fields. Unmarked fields fail
the packet. A field marked `measured` needs the measurement source and
uncertainty statement; this contract does not invent either. Case C is named
and left unsolved: its motion, clearance, contact, and envelope rows are
`absent` unless a later packet supplies them.

### Review

A review of JVP-01 checks only the following:

- the parent hash is unchanged;
- Case A matches that parent;
- every required field has one of the three marks;
- `absent` was not replaced by zero or by a copy of the parent surface;
- chord, twist, profile, and station radius outside an explicit joint field
  still match `P`;
- the 250 mm and 13-inch scenarios are not mixed;
- no solver output, polar table, trajectory, or qualification flag was added;
- `physical_qualification` is false.

Existing station-copy reports and `UNDEFINED` joint-modification records do
not satisfy this packet. They may be cited as inputs. They are not the
packet.

## Explicitly later work

These are not part of JVP-01 and are not authorized by this document:

- a matched A-versus-B thrust, torque, and power comparison;
- a Case C trajectory;
- rotating modal analysis or an imbalance survey;
- joint FEA or CFD;
- any change to the PR #97 polar grid;
- physical qualification or a qualified joint position.

## Preserved gates

PR-06C, GEOM unknown and failed states, CMM-2 `physical_qualification=false`,
null CMM-2 clearance fields, and ADR-009 remain as they are. Archived failed
or blocked records stay archived. This contract does not reinterpret them as
joint performance.
