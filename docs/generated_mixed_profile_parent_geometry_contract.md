# Internally generated mixed-profile parent sections and surfaces

**PROPOSED / NOT IMPLEMENTED.** Documentation proposal based on main
`988a8524c4a8814eeee54071a86b6da67f0b150b`. No design freeze, geometry execution,
new coordinate asset, solver result or physical acceptance is recorded here.
This is a separately reviewed future scope, not a change to the merged
[sparse station generator](parent_blade_station_generation.md),
[station comparison](parent_blade_station_comparison.md) or
[local PE0 reporting contract](local_apc_pe0_geometry_reporting.md).

## 1. First bounded deliverable and reusable capabilities

The future deliverable is one identified internal parent section function, its
declared open-pose surface and complementary fixed/tip restrictions at two hinge
positions. Deterministic section/lineage/geometry-difference reports and a
descriptive surface representation are intended. A watertight blade/hub/joint
solid, manufacturing geometry, folding clearance and strength are separate work.
External CAD/STEP is optional reference/import/export, never an input prerequisite.

| Existing capability | Reuse and boundary |
| --- | --- |
| `core/apc_pe0.py` and `application/apc_pe0_geometry_report.py` | Local source parsing, complete retained rows/definitions and explicit radial conventions. Do not use `blade()` to omit the final row or assign one profile to a mixed blade. |
| `core/airfoil.py`, `core/profile_catalog.py` | Coordinate parsing, validated canonical ordering, content identities and pinned catalog access. Catalog names do not supply E63/APC12 identity; current catalog does not contain those profiles or NACA4412. |
| `application/design_draft.py`, `blade_stations.py`, parent generator/comparison | Identified internal inputs, SI values, immutable parent lineage, explicit row correspondence and missing coverage. Current single-profile sparse services cannot represent the new mixed section function without separately reviewed additions. |
| `visualization/propeller_25d.py` | Quarter-chord placement, twist convention and mesh primitives provide a zero-offset preview reference. Its one-profile mesh and preview hinge interpolation are not the proposed mixed-profile evaluator or complete solid. |
| GEOM-02/03/04 contracts | Provenance, incomplete coverage and bounded geometry audits. Existing accepted topology/clearance does not transfer automatically to new sections, surfaces, offsets or joints. |

Reuse must preserve existing behavior. In particular, existing sparse cuts do not
start interpolating missing rows, and existing single-profile bundles do not gain
an ambiguous mixed-profile name. The new section/surface manifest is distinct.

## 2. Evidence identities and scenario boundaries

Three identities must remain separate:

- **Retained manufacturer record:** original local bytes/member hash, revision,
  parsed table/definitions, source row indices and declarations. This records what
  was supplied, not complete coordinates or measured/as-built truth.
- **Generated geometry:** parent input identities, coordinate sources/hashes,
  every transformation/interpolation/transition choice, represented SI controls,
  frame/domain, method version and implementation digest. Generated sections and
  surfaces have fresh content hashes and link to their parents; they are model
  outputs, not additional manufacturer rows or recovered proprietary geometry.
- **As-built evidence:** specimen/revision, process/print orientation, dimensional
  metrology with uncertainty and registration to the design. No such evidence is
  supplied by a source table or generated mesh. Material/strength evidence remains
  separately required by the [hinge assessment](strength_aware_radial_hinge_assessment_proposal.md).

The reference parent's presumed optimality remains a scoped study assumption
bound to its source and declared operating condition, not independently validated
global optimality. No operating condition is inferred from a simulation date.

The canonical **250 mm project diameter** has nominal radius 125 mm and its own
hub/design inputs. It is not resized to match this **13-inch manufacturer example**:

| Retained convention for 13x5.5MR | Value | Consequence |
| --- | --- | --- |
| Nominal diameter / nominal radius | 330.2 / 165.1 mm | Product convention, not automatic surface coverage. |
| Footer `RADIUS` | 164.338 mm (6.47 in) | Distinct declared footer value. |
| Last source station | 164.465 mm (6.475 in) | Retain it, including its position beyond the footer radius. |
| `HUBRAD` / `HUBTRA` | 8.128 / 25.908 mm | Retain meanings as supplied; do not generate an unobserved hub solid. |
| Proposed comparison hinges | 101.6 / 127.0 mm | 8/13 and 10/13 of nominal radius; not recommended locations. |

Bind the [existing genuine receipt](local_apc_pe0_geometry_reporting.md#2026-10-03-supplied-genuine-member--repaired-execution):
member `13x55MR-PERF.PE0`, version `v2025-1001`, simulation date `2026-02-24`,
SHA-256 `2972e1b99215f2eb052e586e48cc59730cbfd4f08c6627ea7461a8afa150c30f`.
The receipt is earlier source-retention evidence, not a run of this proposal.
Vendor bytes, full station tables and full generated derivatives remain outside
public Git history. Public implementation tests must use first-party synthetic
inputs; source URLs, hashes and permissible summaries are not a license to vendor
the dataset. Existing [third-party restrictions](../THIRD_PARTY_NOTICES.md) apply.

## 3. Coordinate provenance, normalization and section inputs

The first proposed endpoint pair is **E63 reference coordinates** and an explicitly
identified **NACA4412 reference substitute**, not an APC12 coordinate definition.
UIUC's E63 and NACA4412 files are primary collection references listed in §9.
Their availability does not establish a particular APC blade's coordinates or
per-file redistribution permission. Actual input bytes, acquisition date,
attribution/permission and hashes remain **PENDING**; none is bundled by this PR.
Caller-supplied permitted local coordinates or a first-party analytic NACA4412
definition are eligible future inputs only after their exact manifest is reviewed.

Analytic and tabulated NACA4412 are different identities. An analytic option must
declare formula source, camber/thickness equations, trailing-edge coefficient,
sampling and arithmetic. Existing preview NACA4 uses a closed-edge coefficient
`-0.1036`; the classical finite-edge expression uses `-0.1015`. No silent switch
between them or between analytic and UIUC coordinates is permitted. The vendor's
APC12/NACA4412 equivalence statement does not prove byte, section or 3D identity.

Record both raw byte SHA-256 and the existing canonical coordinate digest
(`.17g` coordinate pairs with newline separators). Record any ordered-array,
normalization and generated common-abscissa hashes separately. Source names and
profile metadata cannot substitute for these identities.

Reuse the actual parser normalization: subtract `x_min`, divide x and y by
`x_max-x_min`, and subtract the mean leading-edge y used by that parser before
scaling y. It does **not** rotate. Record this method/code identity and any source
prealignment separately; an unsupported orientation is rejected, not silently
rotated. Preserve finite trailing-edge gaps and canonical upper-TE→LE→lower-TE
ordering. No unrecorded smoothing, closing or replacement of coordinate points.

For this bounded generated model, each upper/lower branch must be a single-valued
piecewise-linear graph over the entire normalized x interval `[0,1]`, with strictly
increasing distinct x breakpoints after reversing the upper branch. Branches share
the LE, and may differ at the TE. Inputs needing endpoint extrapolation, repeated-x
branch repair or rounded-x grouping are unsupported. Existing parser validation
is necessary but does not itself prove this stronger input requirement.
The common grid is the union of both endpoints' branch breakpoints. Evaluate their
declared piecewise-linear graphs there without extrapolation. This creates a new
generated representation, not a modification to either source file.

Keep all retained PE0 fields, including supplied `TWIST`, sweep/rake, thickness,
section area, pitch labels, `ZHIGH`, `CGY` and `CGZ`. Pitch `(QUOTED)`, `(LE-TE)` and
`(PRATHER)` are retained measurement labels; this model uses `TWIST` and does not
invent dimensional interpretations for the pitch fields or use them as twist.
Unknown coordinate/transition geometry stays unknown in the manufacturer record.

## 4. Explicit proposed continuous parent model

This is a **model choice**, not the unspecified manufacturer's blend. Let r be
the global radial station coordinate in metres. At existing scalar knots, return
the stored parsed SI values directly. Between consecutive supported knots,
declare piecewise-linear interpolation of chord c(r), supplied twist beta(r),
thickness ratio tau(r), sweep Y(r) and rake Z(r), with one immutable parent
evaluator. Do not interpolate profile names. No extrapolation, endpoint padding,
resizing to nominal radius or hidden truncation to footer radius is permitted.
The manifest declares a supported aerodynamic domain `[r_aero_start,r_end]`
within actual scalar coverage, including treatment of the last/footer discrepancy.
Neither an unmodelled inner/hub region nor the nominal-tip gap becomes covered.

Use the retained 3.70 / 6.00 inch anchors as **proposed model transition anchors**
`a=0.09398 m`, `b=0.1524 m`, not proof of the manufacturer's transition law.
With q=(r-a)/(b-a), declare w=0 for r<=a, w=1 for r>=b, and
`w=3*q*q-2*q*q*q` inside. For endpoint graphs A and B, define

```text
m_A(x) = (upper_A(x)+lower_A(x))/2
h_A(x) = (upper_A(x)-lower_A(x))/2           (likewise B)
m(r,x) = (1-w(r))*m_A(x)+w(r)*m_B(x)
h(r,x) = (1-w(r))*h_A(x)+w(r)*h_B(x)
d(r) = max over x in [0,1] of 2*h(r,x)
v_upper/lower(r,x) = m(r,x) +/- tau(r)*h(r,x)/d(r)
```

Require finite positive chord, tau and d, and nonnegative h with strictly positive
interior thickness. For the represented piecewise-linear x graphs, the continuous
maximum defining d is attained on the union breakpoints; do not substitute the
existing parser's sampled thickness metric as an exact maximum certificate.
Endpoint sections are the declared thickness-scaled endpoint models, and need
not equal their unscaled coordinate sources.

Here tau is deliberately interpreted as a **vertical normalized t/c model target**;
the vendor's measurement/normal-to-camber convention is not established by the
column label. Applying that scalar is an explicit modelling assumption. Camber is
preserved while thickness is scaled. Other retained thickness/area/centroid fields
are descriptive comparison inputs, not simultaneous fitting constraints. Their
differences/unknown definitions must be reported, not tuned away. This choice
does not establish fracture resistance. Alternative scaling/blending laws require
new model identities and later review, not runtime fallback.

The smoothstep weight is C1 at its anchors; this does not make the entire surface
C1. Scalar interpolation and coordinate graphs can introduce derivative breaks.
The intended surface is continuous where the declared inputs satisfy the stated
conditions, with those breaks recorded. Finite sample agreement alone is not a
proof of continuous validity. Future validation must cover each declared cell/
transition, represented operation path and any unresolved degeneracy.

## 5. Frame, placement and sweep/rake semantics

Declare a common right-handed deployed shaft frame: radial axis e_r, tangential
e_t, shaft e_z, with e_r cross e_t=e_z. r is the section's radial projection
coordinate, not the Euclidean shaft distance of every swept/chordwise surface
point. Both hinge radii identify the corresponding section planes `r=r_h`.
If a desired hinge instead lies on a cylindrical radius or a different reference
curve, that mapping must be declared and reviewed; it is not inferred here.

For the proposed first model, use quarter-chord stacking fraction f=0.25 and
positive twist from e_t toward e_z. With normalized chordwise x and ordinate v,

```text
P(r,x,v) = r*e_r
         + [Y(r)+c(r)*((x-f)*cos(beta(r))-v*sin(beta(r)))]*e_t
         + [Z(r)+c(r)*((x-f)*sin(beta(r))+v*cos(beta(r)))]*e_z
```

SWEEP(Y)/RAKE(Z) establish labels/axes, not the manufacturer's stacking origin,
sign, reference line or relationship to `ZHIGH`/centroids. A generated manifest
must explicitly declare them as offsets of this chosen stacking line, its units
and signs, labelling any unverified correspondence as a model assumption. Do not
add centroid/ZHIGH offsets on top or call this recovered APC placement. Missing
declarations block generation; a separately declared zero-offset model is not a
silent replacement for supplied sweep/rake. Surface points' true shaft distances
and any hub/rotation-axis registration must be reported separately when relevant.

The parent surface is P evaluated on both declared branch graphs for all supported
r and x; trailing-edge closure convention is explicit. A future mesh is a
discretization of that same function with method/settings and approximation limits,
not a recovered solid. Mesh samples alone do not certify continuous surface,
intersection or clearance claims. This proposal supplies no endcaps, joint cuts,
fillets, print voids or complete hub geometry.

## 6. Complementary cuts and acceptance scope

For **each** `r_h=0.1016 m` and `0.127 m`, require supported parent coverage on
both sides and at the hinge. Define fixed as the restriction r<=r_h and tip as
r>=r_h. If a local tip coordinate s is used, evaluate the parent at r=r_h+s:
`c_tip(s)=c(r_h+s)`, `beta_tip(s)=beta(r_h+s)` and the same section/placement
function. There is no root-distribution replay, span rescale or distal twist reset.
The shared hinge cross-section is a generated evaluation once, reused by both
children. It has evaluation/method/input lineage, not a fabricated PE0 row index.
All inherited source knots retain original indices and exact stored values.

| Future software acceptance item | Required report/evidence |
| --- | --- |
| Immutable parent | Same coordinate/scalar/frame/transition/domain manifest and hash for both cuts; generated revision cannot mutate retained records. |
| Knot correspondence | Original indices and stored global SI radii/chord/TWIST retained identically. Generated between-knot values marked generated with bracketing indices. |
| Hinge evaluation | Both absent source stations remain absent in the retained table. A supported generated section has one shared content identity and global radius; no missing source row is concealed. |
| Continuous inheritance | Children invoke restrictions of the identical parent map, including profile blend, sweep/rake and thickness. Establish structural correspondence and represented evaluation consistency; a few matched samples are insufficient. |
| Coordinate and surface distinction | Source/profile hashes, generated section hashes and surface identities separate. Airfoil equality alone is not full 3D equivalence. |
| Explicit joint differences | Joint-region extents, gaps, steps, protrusions, removed/added geometry, missing definitions and offsets reported independently; no guessed CAD tolerances. |
| Coverage/validity | Unsupported coordinates, outside-domain hinges, missing scalar/frame meanings or unresolved continuous validity produce incomplete/blocked outputs, not fabricated geometry. |

Declare hinge/hardware radial, tangential and axial offsets, axis orientation,
reference frames and each child's deployed rigid transform separately. A hardware
offset does not necessarily displace the aerodynamic surface. For ideal inherited
geometry outside a declared joint region, require the deployed child map to equal
the parent restriction; otherwise report the actual displacement/orientation
difference and its declared cause. Missing transforms are unsupported, not assumed
zero. The first zero-offset/identity-transform comparison is a bounded starting
case. New offset topology cannot inherit existing planar GEOM-01 clearance.

No numerical physical acceptance limit is introduced. Future software checks must
separate exact copied-value/identity predicates from declared arithmetic error
reports; new tolerances need separate justification/review. Complete 3D surface
equivalence, folded envelope, joint clearance, mass/CG/inertia, aerodynamic effect,
PA-CF directional properties, strength and safe-winner status remain unestablished.
No overall safe winner follows from correspondence.

## 7. Dependencies and completion criteria for later authorization

Before implementation authorization: review exact endpoint coordinate/formula
identities and rights, the scalar-domain manifest, vertical-thickness assumption,
stacking/sweep/rake interpretation and this explicit transition law. Unknown APC
blend stays unknown even when a generated substitute is approved. A first-party
internally declared parent may proceed independently of vendor reconstruction;
its model/source lineage must say so.

Later bounded implementation would add a distinct section/surface manifest and
evaluator, then two restriction reports and a small CLI/example. Reuse existing
services where their single-profile/frame constraints apply; preserve rejection
elsewhere. Review work/size limits before execution; existing GEOM budgets are not
permission for an unbounded new evaluator. No surface generation runs in this PR.

Required later TDD/review includes source immutability; distinct analytic/tabulated
and APC12 identities; normalization and finite/open TE handling; unsupported branch
shapes; transition endpoints/continuity and thickness; both absent hinge sections;
global radii/twist inheritance; a twist-reset negative control; unsupported offsets;
domain gaps; deterministic lineage/digests; and whole declared geometry validation
rather than sampling-only claims. Use synthetic software fixtures without vendor
data. Such software evidence is distinct from as-built comparison/experiments.

Completion of that software deliverable requires independent exact-head review,
documented validity/error limits, reproducible reports, unchanged retained-record
behavior and CI. Strength-aware selection still needs identified joint geometry,
load cases, material/process evidence and experimental support under the broader
proposal. CAD/material/test acquisition can proceed in parallel with CMM-2 work;
neither this proposal nor its later geometry implementation accepts CMM-2 evidence.
No calendar estimate, measured performance or hardware-test authorization is given.

## 8. Status, precedence and unchanged boundaries

This document proposes a future scope only. It does not replace GEOM-02/03/04,
station generation/comparison, PE0 retention or PR-C numerical contracts. A later
review must explicitly accept any necessary new representation/adapter. Historical
records remain unchanged; an implemented reporting slice is not implementation of
the broader strength assessment. PR #81/#84/#91 and C2V-09 are untouched.
No freeze, merge, BEM/FEA/trajectory run, strength acceptance, optimal-hinge claim,
ADR-009 acceptance or qualification promotion. `physical_qualification=false`;
existing unknown clearance/physical gates remain unknown/false.

## 9. Primary references and rights ledger

Checked 2026-10-03 UTC. Source references establish their own stated scope; they
do not supply missing source identities, blend definitions or permission by analogy.

| Primary reference | Use and rights/provenance boundary |
| --- | --- |
| [APC technical geometry data](https://www.apcprop.com/propeller-technical-data/) and [engineering](https://www.apcprop.com/technical-information/engineering/) | Spanwise data and proprietary varying/blended section description. No member-specific complete coordinate/blend reconstruction follows. |
| [APC performance documentation](https://www.apcprop.com/technical-information/performance-data/) | Manufacturer calculations are distinct from measured performance. No performance comparison is performed here. |
| [APC terms](https://www.apcprop.com/terms-conditions/) | Retain notices; broader redistribution requires authorization. Follow repository private local-data policy; no archive/full derivative in public Git. |
| [UIUC Airfoil Data Site](https://m-selig.ae.illinois.edu/ads.html), [coordinate collection](https://m-selig.ae.illinois.edu/ads/coord_database.html), [E63](https://m-selig.ae.illinois.edu/ads/coord/e63.dat), [NACA4412](https://m-selig.ae.illinois.edu/ads/coord/naca4412.dat) | Collection provenance and Selig/Lednicer formats. Pin actual raw/canonical hashes later. Per-file permission/attribution remains pending; a wind-tunnel database license is not automatically a coordinate-file license. No assets copied here. |
| [NASA-TM-X-3284, 1975](https://ntrs.nasa.gov/citations/19760003945) and [NACA-TR-460, 1933](https://ntrs.nasa.gov/citations/19930091108) | Primary analytic NACA section/publication basis. A future first-party formula implementation must declare its exact method; no copied publication assets or claim of APC identity. |
| [PDAS four-digit thickness explanation](https://www.pdas.com/naca456thick4.html) | Documents finite trailing-edge formulation; distinguish it from repository preview closure choice. Public-domain program notices do not automatically license every website/data asset. |
| [Repository notices](../THIRD_PARTY_NOTICES.md) and [licensing](licensing.md) | Control redistributable assets, attribution and caller-supplied local data. Endpoint rights unresolved means no coordinate vendoring. |

As-built identity, actual vendor blend/coordinate equivalence, exact stacking and
thickness semantics, and surface/strength validation remain explicit open evidence
items. The proposed modelling choices resolve a generated design definition only;
they do not resolve those manufacturer or experimental unknowns.
