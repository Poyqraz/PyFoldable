# Strength-aware radial hinge-position assessment

Status: **PROPOSED / NOT IMPLEMENTED**. This documentation-only proposal is not
a frozen contract, implementation authorization or qualified design.
Inspection base: `a5286cc6d80ea0130bd3bdc87d2b42277c499900`.
Parent-blade design-intent clarification base:
`c2b267f1e1536e205c5d7ac3c05c2a8ab227533d` (merged proposal PR #86).

The question is where to divide an actual blade into fixed and movable parts,
given its section geometry and one declared joint design. A shorter tip can
reduce moving mass yet place the attachment in a thinner section; neither fact
alone establishes fracture resistance. The first useful result is a traceable
candidate comparison with explicit missing evidence, not an overall safe winner.
No CAD, solver, source, trajectory, executable fixture, numerical gate or CMM-2
contract changes belong to this proposal. PR #81/#84 remain separate.

## 1. Existing capabilities and their boundaries

| Existing path | Reuse in a later authorized assessment | Boundary retained |
| --- | --- | --- |
| [Legacy root/tip variants](../pyfoldable/variants.py) and [sweep](../pyfoldable/design_sweep.py) | Split labels and historical comparisons | Ratios partition the shaft-to-tip radius. The helper assumes midpoint tip CG and scales tip mass linearly with tip fraction; the sweep uses reference-scaled thrust. These are not CAD-derived mass, stress or source-bound aerodynamic evidence. Default percentage pairs do not encode exact 8:5 or 10:3 splits. |
| [Canonical design](../configs/designs/TIP_HINGED_250_CANONICAL.toml), [GEOM-02](geom02_station_contract.md), [draft service](../pyfoldable/application/design_draft.py) | SI units, explicit station/profile identities, candidate drafts | Canonical station/chord/twist values are schema examples, not recovered blade geometry. Stations span 0.20R–0.98R; missing span is not silently completed. Manufacturing thickness fields and analytic profiles are not strength evidence. |
| [GEOM-01](geom01_feasibility_plan.md), [geometry search](../pyfoldable/application/geometry_search.py) | Bounded hinge-radius/endpoint screening on the same declared source geometry | One planar rigid tip, +z hinge, zero offsets; centerline bounds and endpoint preview are not swept CAD clearance. Unsupported joint geometry is reported unsupported, not projected into this topology. |
| [GEOM-04](geom04_surface_hardware.md), [hardware contract](../pyfoldable/application/hardware_contract.py) | Candidate-specific retained-surface/declared hardware evidence within supported representations | Preview surfaces, convex solids and cylinder envelopes are not arbitrary CAD contact. Shared-hinge contact, exclusions, incomplete coverage and budget exhaustion remain visible. Evidence cannot be reused across changed candidates. |
| [Active BEM search](py04_deterministic_design_search.md), [adapter](../pyfoldable/application/active_design_search.py), [analysis](../pyfoldable/application/design_analysis.py) | Source-bound fully-open aerodynamic screening with matched coordinate/polar identity and unchanged budgets | Search axes are chord/twist multipliers, with hinge fixed. This is not a strength-aware hinge optimizer. Physical/structural constraints remain unknown. Supported first operating condition, profile and source-domain restrictions apply; no fallback polar or reference substitution. |
| [Mechanism binding](../pyfoldable/application/mechanism_binding.py) | Explicit one-tip radial mass samples and intrinsic inertia when their model is applicable | Caller-labelled samples remain unqualified. The radial reduction does not supply an arbitrary 3D joint tensor, measured CG or impact load. |
| [PR-09 plan](pr09_fea_contract_execution_plan.md), [FEA contract](../pyfoldable/core/fea_contract.py), [evidence](../reports/pr09_fea_contract_evidence.md) | Revision/material/load-case/result identities and existing convergence/unit/limit checks | Synthetic results prove validator behavior only. Software pass always leaves physical qualification false. Actual PA-CF, CAD, loads, limits and ANSYS evidence are missing. Schema acceptance alone does not prove a material card or load model physically adequate. |

These are separate capabilities. No existing adapter turns their outputs into a
structurally qualified radial-hinge winner. This proposal adds none and changes
none of their constraints.

## 2. Diameter, radius and split conventions

Use the **250 mm project baseline**: open swept diameter D=250 mm, shaft-to-tip
radius R=D/2=125 mm, canonical hub radius b=18 mm, canonical hinge radius
h=100 mm, nominal movable length L=R-h=25 mm. Hinge radius is measured from the
shaft axis. Available fixed radial span outside the hub is h-b, not h. The
canonical 140 mm stowed-diameter and 0.85 matched-reference thrust-retention
targets at 7100 RPM are targets, not achieved results or new acceptance gates.

For this comparison only, **diameter-equivalent A+B** means A=2h and B=2L,
so D=A+B. It does not mean two physical blade lengths added along one radius.
Raw user/CAD labels must declare units and reference origin before conversion;
unresolved conventions block the candidate. Radius-based or hub-edge splits
are different declarations, not silently interpreted as this convention.

| Scenario / split | h/R | h (mm) | L (mm) | Interpretation |
| --- | --- | --- | --- | --- |
| 250 mm, proportions 8:5 | 8/13 | 1000/13 ≈ 76.923 | 625/13 ≈ 48.077 | Same ratio, not an 8-inch fixed diameter |
| 250 mm, proportions 10:3 | 10/13 | 1250/13 ≈ 96.154 | 375/13 ≈ 28.846 | Same ratio; not the canonical 100 mm hinge |
| Separate 13-inch diameter, 8+5 inches equivalent | 8/13 | 101.6 | 63.5 | D=330.2 mm, R=165.1 mm |
| Separate 13-inch diameter, 10+3 inches equivalent | 10/13 | 127.0 | 38.1 | D=330.2 mm, R=165.1 mm |

These are unit/ratio arithmetic, not manufactured candidates or screening results.
The 13-inch scenario needs its own real blade, hub, motor/operating envelope,
joint, material and acceptance declarations. Do not scale 250 mm CAD, tip mass,
polars, targets or evidence into it. A 254 mm benchmark is also distinct from
the 250 mm project rotor.

Keep the existing topology conflict visible: full 180-degree folding with hub
nonpenetration requires h≥(R+b)/2 and centerline envelope diameter ≥R+b=143 mm
for the canonical R,b. Equality is touching, not positive clearance. Changing
hinge radius cannot meet the 140 mm target under that full-fold topology;
surface/hardware thickness can add restrictions. Partial travel must be explicitly
declared and reviewed as a different endpoint, not substituted for full stow.

## 3. Smallest useful first deliverable

### Parent blade and deployed correspondence

One original blade is the accepted reference **for this study**. Its presumed
optimality is a scoped study assumption at a declared operating condition, not
independently validated global optimality. Record the parent CAD/section/profile
source identities, revision/hashes and the assumed objective, RPM, inflow and
environment with their source; these actual inputs remain unsupplied. The 7100 RPM
project target alone does not identify that condition or prove the assumption.

The fixed and moving portions are complementary cuts of that same parent blade.
Use global shaft-based radius r and tip-local span s=r-r_h: outside explicitly
declared joint modifications, the tip inherits c_tip(s)=c0(r_h+s) and
beta_tip(s)=beta0(r_h+s), over s in [0,R-r_h]. Do not replay the parent root
distribution, reset twist at the cut or rescale span. Preserve original radial
station correspondence, chord, twist, section geometry and open-pose placement.
Local airfoil identity describes a section profile, not the complete 3D blade:
section scale/orientation, sweep, rake, stacking and placement also require
parent correspondence. A shared airfoil name does not prove matching surfaces.

Declare hinge-axis and hardware offsets separately from actual displacement of
the deployed aerodynamic surface. Record radial/tangential/axial translation
components, rotation components and conventions, reference points, units and
shaft/parent/fixed/tip/joint frames, with deployed transforms between them.
A hardware offset may preserve the nominal parent surface; it does not establish
that preservation. Report the transformed surface's position/orientation
deviations, joint gaps, steps and protrusions explicitly, with supplied CAD or
as-built uncertainty. No CAD tolerances are invented here. Existing BEM does not
capture these joint features, and zero-offset planar GEOM-01 does not clear a new
offset topology; unsupported representations remain unsupported.

The next practical CAD comparison is the untouched original versus the
cut/rejoined **deployed assembly at each of the two declared hinge positions**.
Require parent/child lineage for both cuts and assemblies; map each child station
back to its original global radius, section and orientation; compare open-pose
surfaces in a common declared frame. Itemize every joint-region removal/addition,
gap, step, protrusion and placement deviation separately from inherited geometry,
including unresolved regions and measurement uncertainty. This is a CAD evidence
request, not CAD creation or a numerical acceptance gate in this amendment.

A duplicated-root/twist-reset arrangement may be retained only as an optional
comparison control with its own geometry identity and departures from the parent.
Its greater performance loss is a hypothesis requiring matched operating
conditions, analysis/settings or experiments with uncertainty; it is not a
result or the default fixed/moving construction.

### Candidate dossier

Prepare one **250 mm actual-blade / declared-joint candidate dossier**. The blade
and joint design identities must be supplied; they are currently missing, not
inferred from canonical examples. Begin with two explicitly declared radial
locations motivated by the 8:5 and 10:3 proportions, subject to real station and
attachment coverage. This is a bounded comparison, not an optimization sweep.

Keep the same blade source revision and joint architecture/materials/nominal
attachment specification. Each placement needs its own assembly/cut/attachment
revision and evidence identity. If that design cannot fit a section, retain the
failure; do not covertly resize the pin, thicken the blade, relocate holes or
replace the joint to make a candidate pass. Any later change is separately
declared and invalidates dependent evidence.

Every candidate row must contain these fields, with source, revision/hash, units,
frame, uncertainty and evidence scope for each supplied value:

| Candidate field group | Required content / explicit unavailable reason |
| --- | --- |
| Radial position and actual section | D,R,b,h,L and h-b; hinge axis/offset/travel; local chord, twist, actual thickness distribution, walls/skins, internal voids/infill and remaining net ligament after attachment cuts. Actual CAD sections/tolerances, not thickness ratio alone. |
| Joint and load path | Pin/shaft, lug/clevis, bearing/bush, fastener/retention, lock and stop dimensions, fits, fillets, hole edge distances, contact and permitted movement; fixed/moving members and force/moment transfer. Declare absent components explicitly. |
| Movable mass properties | Candidate-specific blade-plus-moving-hardware mass, 3D CG and inertia tensor in declared frames, hinge-axis inertia, methods and uncertainty; reconcile CAD integration with measured mass/CG/inertia when available. No linear span scaling, midpoint CG or uniform-density replacement for unknown printed construction. |
| Folded geometry | Centerline bound, chord-inclusive preview and supported candidate-specific GEOM-04 evidence separately; entire declared travel, hub/interblade/hardware scope, manufacturing fit variation, exclusions and unresolved shared-hinge contact. No endpoint-only mesh claim of continuous CAD clearance. |
| Aerodynamic screening | Exact candidate draft/stations/profile and polar sources, operating condition, BEM settings/domain/coverage, annulus/rotor outputs or failure reasons. Joint-induced shape/gaps absent from BEM remain model limitations. |
| Structural evidence | Candidate CAD/material/load-source/result linkage for five PR-09 cases, mesh/convergence/force balance and metric/limit evidence; reviewer findings and missing-input reasons. |
| Decision scope | Separate screening, candidate structural-review and experimental-support states; failed/unknown/unsupported fields retained. No composite safety score or automatic safe winner. |

The first dossier may be complete as an **evidence inventory with blocked rows**
while FEA/tests are absent. It must still identify an actual blade and joint and
retain available geometry; a placeholder-only table is not the geometry-linked
deliverable. Structural acceptance and selection are separate later milestones.

## 4. Required real inputs before structural claims

- **CAD/sections:** revision-controlled native SolidWorks and/or faithful STEP
  export, source permission, hashes, units, shaft/blade/hinge/build frames,
  hub attachment, relevant full span and section cuts around each joint, internal
  construction and as-built deviations. Coordinate/station exports identify their
  CAD parent and extraction method. Chord/airfoil stations alone do not establish
  a solid, bore ligament or printable attachment.
- **PA-CF process and material:** actual filament grade/batch, conditioning,
  moisture/temperature range, machine/nozzle, layer height, roads/perimeters,
  infill, raster/build directions and post-processing. Coupons represent these
  processes and material axes. Supply density, directional elastic/shear response
  and Poisson coupling, tension/compression/shear allowables including interlayer
  behavior, and applicable bearing, net-section/shear-out, notch and fatigue data
  for declared modes/duty/environment. Record raw tests, repeats, uncertainty and
  allowable derivation. Missing directional properties block the affected claim;
  a generic datasheet or the minimal orthotropic schema property list is not a
  complete 3D material model.
- **Joint:** actual pin/fastener/bush/lock/stop materials and characterization,
  dimensions/tolerances, surface/fit/preload, retention/contact/friction assumptions,
  attachment fabrication, assembly and inspection records. Adhesive properties
  apply only if adhesive is part of the joint. Minimum wall/trailing-edge
  declarations are manufacturing inputs, not fracture limits.
- **Loads and limits:** declared speed/overspeed scope, operating/environment
  envelope, imbalance magnitude/direction, deployment/stop history and duty cycle,
  each with source and uncertainty. Engineering owners approve safety-factor/
  allowable margins, displacement, bearing/contact pressure, fatigue life and
  modal separation limits before judging results. Missing limits remain missing;
  this PR supplies no numerical values or new gates.

Attachment sections require evaluation of net-section tension, bending/torsion,
bearing, shear-out, pin shear/bending, local stress concentration, interlayer
failure and fatigue as applicable. Local thickness is one input, never a
stand-alone safety predictor. Nonapplicable modes need explicit load-path reasons.

## 5. Screening, FEA review and experimental selection

**Geometry-linked screening:** later authorized use may reuse GEOM-01 and
candidate-bound GEOM-04 within supported topology. Its `surface_path_clearance`
and `interblade_clearance` gates remain unknown unless the existing opt-in
negative policy establishes False; readiness is not True.
`full_propeller_clearance` remains null. Unsupported actual joint solids or
unresolved tolerances remain missing evidence, not substituted previews.

Reuse active BEM analysis for the actual supported fully-open candidate, with
matching profile/coordinate identity, explicit source domain and settings. The
existing chord/twist search does not vary hinge radius; later comparison of
separately identified drafts must not pretend the adapter has new axes. If
external open geometry is identical, rotor screening totals can be identical
while movable loads and attachment demands differ; this does not imply equal
strength. Preserve bounds/error behavior and budgets. Domain gaps or failed
solves cannot be filled with proxy loads. Total thrust or shaft torque alone
cannot define a local joint load case.

**Candidate FEA review:** reuse the PR-09 evidence boundary for:

| Existing required case | Candidate-specific preparation needed |
| --- | --- |
| Maximum-RPM steady centrifugal/aerodynamic | Distributed mass and section load mapping, frame/sign/lever-arm consistency, reactions and attachment paths; independently check resultant force/moment and avoid double-counting centrifugal loads. |
| Peak opening-stop transient/contact | Traceable pre-impact state, drive/stop compliance and contact history with uncertainty. CMM-2 screening terminal first contact does not compute impact/bounce/stop stress. No invented impact peak or accepted PR-C claim. |
| Maximum-RPM imbalance | Declared eccentric mass/vector/phase and speed, load path/support model; perfect balance is not assumed to clear the case. |
| Modal separation over speed envelope | Actual assembly stiffness, prestress, constraints and relevant excitation orders; not a generic free-blade frequency or guessed margin. |
| Fatigue of blade/hinge/pin/lock/stop | Declared repeated-load spectrum, environment/process-specific fatigue evidence, local failure modes and uncertainty. |

Retain PR-09's at-least-three mesh levels, convergence history, force balance,
units, matching identities and rejection of nonconvergence/warnings. Its current
validator checks declared properties/metrics/limits and CAD/material/result
fields; it does not certify CAD authenticity, physical load mapping, complete
anisotropic failure coverage or experimental validity. Bind external load
artifacts, material-card bytes, solver/version/settings and full case
correspondence for independent engineering review. Numerical policies remain
unchanged; this supplements review evidence, not executable schema.

**Experimentally supported selection:** only later authorized tests of the actual
process/assembly can support selection. Plan directional and attachment coupons,
dimensional/mass-property checks, static joint tests, declared deployment/stop
and cyclic tests, and matched rotor/stand measurements with calibrated sensors,
repeats and uncertainty under the [PR-10 boundary](pr10_experiment_contract_execution_plan.md).
Test scope/limits and appropriate containment are reviewed before hardware runs.
Candidate FEA review or a synthetic validator pass does not qualify the rotor.
No selection while required physical evidence or clearance is unknown; favorable
thrust cannot compensate for structural failure.

## 6. Parallel work, dependencies and completion criteria

| Bounded workstream | Deliverable and dependency | Completion boundary |
| --- | --- | --- |
| CAD/joint preparation | Actual 250 mm parent blade, one joint declaration and original-versus-cut/rejoined deployed comparison at two placements; requires engineering source data | Parent/child radial/section/orientation lineage, transforms and explicit joint-region differences, plus attachment coverage; retain infeasible/missing regions. No CAD alteration in this PR. |
| Material/manufacturing | Process declaration, directional coupon/test plan and later measured card; alongside CAD and CMM-2 | Raw/process-linked evidence and reviewed allowable derivation for each claimed mode; otherwise blocked. |
| Geometry/aerodynamic dossier | Candidate ledger using existing supported paths; actual geometry and suitable polars required | Identified results/failures, unchanged budgets, explicit coverage; screening only. No runs in this PR. |
| Structural preparation/review | Five-case matrix, approved limits and later real ANSYS bundles; depends on CAD, material and traceable loads | Independent candidate FEA review with converged matching results and unresolved modes; not experimental selection. |
| Experimental preparation/evidence | Calibrated component/rotor plans and later raw measurements; reviewed specimen/process/load/test limits required | Scoped comparisons with uncertainty; selection requires all applicable evidence, not a weighted proxy score. |
| CMM-2 verification, separately continuing | Existing PR #81/#84 and frozen contracts govern their own work | No bypass or acceptance from this proposal. Dynamic load claims require independently adequate evidence; CAD/coupon/static preparation need not wait for CMM-2 completion. |

No calendar estimates or predicted performance are supplied. CAD, material
coupons, load-case/test planning and identities can proceed in parallel; that
concurrency is not permission to execute solvers or hardware tests in this task.
Future execution/implementation requires a separately reviewed bounded scope.

This documentation increment completes with the proposal, roadmap/status links,
independent exact-HEAD review and normal document/CI checks recorded in its Draft
PR. The future first deliverable completes only when an actual blade/joint are
identified and every candidate field has real scoped evidence or a specific
reason/owner/dependency for missing evidence. Reviewers can compare positions and
identify the next experiment without implying structural acceptance.

Keep `physical_qualification=false`, PR-06C unresolved and GEOM unknown/False
states. No ADR-009 acceptance, calibration, experimental-validation promotion,
design freeze or merge follows. Existing normative contracts, numerical
thresholds and historical records are preserved.
