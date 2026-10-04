# Concrete mixed-profile parent endpoint/model declaration v1

**PROPOSED / NOT FROZEN / NOT IMPLEMENTED.** This immutable declaration is stacked
on reviewed proposal HEAD `1bbd9ccac876d5d612d2ac19e0cc16d492623e99` (Draft PR #93),
with main `988a8524c4a8814eeee54071a86b6da67f0b150b`. It does not modify that
[proposal](generated_mixed_profile_parent_geometry_contract.md). No merge/freeze
authorization follows. This declaration precedes the separately recorded endpoint
assessment; hashes below identify inputs and do **not** assert admissibility.

The authoritative machine-readable declaration is
[mixed_profile_parent_endpoint_model_v1.json](declarations/mixed_profile_parent_endpoint_model_v1.json).
Its byte hash and sorted compact-JSON hash are recorded in the subsequent assessment.
JSON hexadecimal strings denote exact stored binary64 values; count limits are
integers, and decimal limit constants denote the stated exact decimal bounds.
Changing an asset, recipe, stored scalar manifest or model choice requires a new
declaration/version and independent review, retaining this declaration/results.

## 1. Exact endpoint assets and rights

Selected A is the UIUC **E63 coordinate asset**; selected B is the UIUC **tabulated
NACA4412 reference substitute**. No analytic alternative, APC12 alias or fallback
asset is selected by this declaration.

| Identity | A: E63 | B: NACA4412 reference |
| --- | --- | --- |
| Primary source | [e63.dat](https://m-selig.ae.illinois.edu/ads/coord/e63.dat) | [naca4412.dat](https://m-selig.ae.illinois.edu/ads/coord/naca4412.dat) |
| Retrieved | 2026-10-04 Europe/Istanbul | 2026-10-04 Europe/Istanbul |
| Raw bytes / coordinate pairs | 1312 / 61 | 693 / 35 |
| Raw byte SHA-256 | `eb90138d5e0b2476c99e431651475e3a6b058872b368e0793e3b5e0383988f9d` | `5c86886f667266f29a5f3a0a48505b9b25ea10539d8a112486c62bf3a5bbd6ad` |
| Source-order numeric SHA-256 | `5c8316a732ff959242b981df54ac61e9f7d041e2f2d8a006e0da2756c624e593` | `139420a465db2e6ffdf55007795f454dd1345577a81cf2b8183eafb694595d74` |
| Normalized candidate SHA-256 | `87e28637ac162d9deeb1dcb2ae90acae067c4b3081d100caddf1841947e3ecb1` | `139420a465db2e6ffdf55007795f454dd1345577a81cf2b8183eafb694595d74` |

Numeric hashes use UTF-8 `x:.17g,y:.17g` pairs joined by newline, no final newline.
The raw numeric hash uses parsed source order; the normalized candidate hash uses
the following declared arithmetic in that same order. The actual returned canonical
digest and its equality to the candidate digest must be checked after this commit.
No parser PASS is claimed in this declaration.

The [UIUC collection](https://m-selig.ae.illinois.edu/ads.html) describes collection
provenance and Selig/Lednicer ordering. It does not establish an explicit per-file
redistribution grant here. **Permission status UNRESOLVED** for both assets; no
raw coordinates or complete derived arrays are committed. There is no inference
from another UIUC database's license. Local assessment is authorized by this task;
future distribution/use must resolve applicable permissions and attribution.
APC's equivalence statement is retained evidence, not exact NACA4412/APC12 identity.

## 2. Normalization and stronger admission, fixed before assessment

Use the pinned `core/airfoil.py` parser with explicit `format="selig"` and the
declared IDs. Decode the exact downloaded ASCII bytes as UTF-8 without newline
translation. The parser's source digest and independent raw digest must agree.
Normalization is its actual `_normalize` expression:

```text
x_min = minimum source x; x_max = maximum source x; chord = x_max-x_min
leading_y = mean of source y with abs(x-x_min) <= chord*1e-7
normalized = ((x-x_min)/chord, (y-leading_y)/chord)
```

These are binary64 operations, not rotation or an exact rational redefinition of
the downloaded decimal shape. The normalized stored binary64 points subsequently
define the exact-rational graph reference. The original bytes remain immutable.
Existing parser tolerances are retained; they do not relax the stronger conditions.

| Stored normalization operand | A | B |
| --- | --- | --- |
| x_min | `0x1.205bc01a36e2fp-11` | `0x0.0p+0` |
| x_max | `0x1.0000000000000p+0` | `0x1.0000000000000p+0` |
| chord | `0x1.ffb7e90ff9724p-1` | `0x1.0000000000000p+0` |
| leading_y | `-0x1.719f7f8ca8199p-10` | `0x0.0p+0` |

Require both the existing parser and already-canonical validator, then independently:

1. Finite pairs and unchanged point count/order/content under the declared
   normalization. No deduplication, reversal, clipping, extra points or repair may
   be hidden by a parser success. Any differing canonical array is a rejection.
2. The unique interior minimum-x node is the shared LE `(0,0)`. The sequence is
   upper TE→LE→lower TE. Reversing the upper **view** for graph evaluation is not
   rewriting the source array. Each view has strictly increasing, distinct x.
3. Both graphs have exact represented domain `[0,1]`; both TE x values are 1.
   No endpoint extension/clamp is allowed. TE ordinate equality means a retained
   closed cusp; a nonnegative finite TE gap is supported and remains explicit.
4. On the exact union of branch x breakpoints, prove upper-minus-lower >=0 and
   strictly positive at every interior point. On each intervening cell the
   difference is affine, so endpoint signs prove the whole cell; zero only at a
   supported LE/closed TE is allowed. Report exact rational witnesses, not only
   parser metadata or rounded minima.

An endpoint rejection remains recorded. It blocks the current model; alternate
coordinates, a different LE construction, graph conversion or any repaired shape
would be a separately reviewable model choice with fresh identities, not a fix
performed to make this declaration pass.

## 3. Immutable manufacturer scalars and domain

Use caller-local `13x55MR-PERF.PE0`, version `v2025-1001`, simulation date
`2026-02-24`, raw SHA-256
`2972e1b99215f2eb052e586e48cc59730cbfd4f08c6627ea7461a8afa150c30f`.
The [merged reporting contract](local_apc_pe0_geometry_reporting.md) and
[private-data notices](../THIRD_PARTY_NOTICES.md) remain controlling.
Keep all 51 rows and 14 fields. No vendor file or full restricted derivative is
published. No new vendor download is performed for this task.

Two private compact sorted-key ASCII JSON identities bind the complete inputs:

- Retained table SHA-256
  `84621877a55558634f92fcf53b3a7d5d17f7be7926c2068137b8ac6051bf911f`:
  ordered rows `{index,lexemes,values_f64}`, retaining every original numeric token
  and its `float(token).hex()` value for all 14 columns.
- Stored scalar SHA-256
  `3e8a6164e691719dbacf0e14139456a3084f18505e263fc983bbb8762e1f733c`:
  ordered rows `{index,r,c,beta,tau,Y,Z}`, all six values stored as `.hex()` strings.
  r/c use existing core PE0 values; beta uses supplied TWIST through
  `math.radians`; tau is column 7, Y/Z are columns 5/6 times the inch constant.

SI conversion is `float(source_token)*INCH_TO_M`, with the existing stored constant
`0x1.a027525460aa6p-6`; radians use the pinned code's `math.radians`, with observed
unit multiplier `0x1.1df46a2529d39p-6`. No extra scaling is applied. Pitch fields
retain their measurement labels and are not reinterpreted as TWIST.
Source hashes plus these exact serialization recipes permit private reproduction;
matching names/revisions alone do not establish the stored scalar identity.

The generated surface domain is explicitly **source indices 10…50**, from
`0x1.a87a072d1aeb4p-6` m (25.908 mm) through
`0x1.50d306a2b1704p-3` m (stored last-station conversion, about 164.465 mm).
The inner/hub rows 0…9 remain in the retained record, outside this generated
aerodynamic-section model. The last row remains beyond footer RADIUS: including it
in a generated model is a declared design choice, not promotion of source
aerodynamic applicability. No extrapolation to nominal tip or hub surface occurs.

Nominal diameter/radius 330.2/165.1 mm, footer radius 164.338 mm, last station
164.465 mm, HUBRAD 8.128 mm and HUBTRA 25.908 mm retain separate conventions.
The **250 mm project baseline remains a different scenario**, not rescaled here.
Simulation date is not an experimental/operating-condition identity.

## 4. Fixed generated assumptions and restrictions

The exact reference uses rational values of the stored binary64 knots. Scalars
c/beta/tau/Y/Z are continuous PWL between adjacent declared knots; knot outputs
copy stored bits directly, including signed zeros. This is generated interpolation,
not a change to the source table or the sparse reporting services.

Anchors are the reviewed proposal's decimal SI model literals rounded to binary64:
`a=0x1.80f12c27a6373p-4`, `b=0x1.381d7dbf487fdp-3` m. The retained 6-inch
conversion is **`0x1.381d7dbf487fcp-3`**, one ULP lower than declared b.
Keep both; do not claim bit identity or silently move the model anchor. This
declares the proposal's model choice, not a recovered manufacturer blend.
For q=(r-a)/(b-a), w=0/1 outside the anchors and w=3q²−2q³ inside.

The chordwise grid is the exact sorted union of both endpoints' normalized upper/
lower x breakpoints; identical values merge, nearby values do not. No epsilon,
rounded-x grouping, extrapolation or padded points. Endpoint graphs are PWL on
their actual supports. Use the proposal's camber/half-thickness blend and
`d=max_union(2h)`; preserve camber and scale half-thickness by tau/d.
Tau is an assumed **vertical normalized t/c target**, not an established vendor
normal-to-camber convention. Other area/thickness/centroid fields are retained
comparison metadata, not fitted constraints. Any changed law requires a new model.

Frame and placement are exactly proposal §5: e_r cross e_t=e_z, global station
projection r, quarter-chord fraction 0.25, positive beta from e_t toward e_z.
Y/Z are declared tangential/axial offsets of that stacking line. This sign/origin
interpretation is a generated assumption; vendor stacking and ZHIGH/centroid
relationships remain unknown. No extra centroid/ZHIGH offset is added.
Upper/lower surface sheets retain finite/cusped TE behavior; no TE strip, caps,
hub/solid or joint geometry is generated by the planned first deliverable.

Hinges are `0x1.a027525460aa6p-4` (101.6 mm) and
`0x1.04189374bc6a8p-3` (127 mm) in the same deployed frame. Fixed/tip are
restrictions of the identical parent map at r<=r_h / r>=r_h; local s uses r_h+s.
No rescale, distal beta reset or replay of the root distribution. A shared
generated hinge section is evaluated once with model lineage, not a source index.
Missing manufacturer hinge rows remain missing. Original copied rows retain indices.

For the explicit ideal baseline, hardware offsets are zero, hinge axis is +e_z
and both deployed child transforms are identity. **Actual joint differences are
UNDEFINED**, not measured zero: no gap, step, protrusion, removed/added geometry,
clearance or hardware shape is supplied. Future joint records must declare each
offset component/frame/transform and surface displacement separately; this baseline
does not validate a new offset topology or a real joint.

## 5. Finite limits and numerical/error policy before implementation

These are proposed software resource limits, not acceptance thresholds for safety:

| Resource/input | Hard bound |
| --- | --- |
| Source / each endpoint file | 2 MiB / 256 KiB |
| Source rows / endpoint pairs | 64 / 256 per endpoint |
| Common x grid / radial breakpoints or section requests | 512 / 68 |
| Output coordinate points / serialized report | 69,632 / 16 MiB |
| Shared exact-rational operations / integer bit length | 20,000,000 / 65,536 |
| Trig Taylor terms per expansion | 80 initially, at most 128 |
| r, c, beta, tau, Y/Z, normalized ordinate | 0<=r<=0.2 m; 0<c<=0.2 m; abs(beta)<=4 rad; 0<tau<=1; abs(Y/Z)<=0.2 m; abs(y)<=1 |

All validation, certificate arithmetic, retries and both cuts share one work
counter; each rational add/subtract/multiply/divide/compare consumes one operation.
Parsing/hashing are additionally bounded by bytes/rows/pairs; integer operations
are bounded by bit length. Count before work. No per-child/retry reset, adaptive
padding or unbudgeted fallback. Exhaustion, nonfinite outputs or missing proof
produce BLOCKED with retained partial diagnostics.

The reference section uses exact rational PWL/scalar/blend arithmetic from pinned
represented inputs. The reference placement uses ideal real sin/cos. Future
binary64 reports require unique round-to-nearest/ties-even cells for complete
reference scalars/coordinates, with error enclosures; copying a source knot is a
direct stored-bit fast path. Newly evaluated exact-zero outputs use positive zero;
copied knots retain their stored zero signs. Distinguish continuous reference geometry from its
discrete rounded outputs. A binary64-valued output map is not mathematically C0.

Planned trig bounding uses exact rational Taylor sums at the reference beta.
For N terms, sin has powers through 2N−1 and remainder bounded by
abs(beta)^(2N+1)/(2N+1)!; cos has powers through 2N−2 and remainder bounded by
abs(beta)^(2N)/(2N)!. These Lagrange bounds hold over the whole declared abs(beta)<=4
range without a libm/global-correct-rounding assumption. Propagate their outward
enclosures through the **complete P expression before rounding**; rounding trig
intermediates first is not the same reference computation. Increase N within the
shared limits only if the rounding cell remains unresolved; exact beta=0 uses
sin=0/cos=1. Remaining ambiguity at N=128 is BLOCKED, not a guessed tie direction.
This is a future recipe, not executed geometry or a runtime certificate here.

At a proved unique rounding cell, the component error is the derived rounding
displacement (at most half the relevant spacing, including ties/subnormals), not a
fitted SI tolerance. Record bounds in m/rad/dimensionless units as applicable.
Point error follows from the component enclosure. Rounded outputs, reference
equivalence and mesh discretization error are distinct; this declaration supplies
no clearance/strength tolerance or existing GEOM/CMM gate change.

## 6. Whole-domain proof obligations and readiness boundary

Endpoint positivity is proved on all PWL cells by exact sign/endpoint arguments.
Convex blending with 0<=w<=1 then preserves interior branch separation for every
r. d is a finite maximum of continuous functions, hence continuous. A positive
uniform denominator bound can use one interior x* where both endpoint gaps are
positive: d(r)>=min(gap_A(x*),gap_B(x*))>0. This proof query does not alter the grid
or turn sampled clearance into a theorem. Positive chord/tau and finite scalar
ranges follow from exact PWL endpoint bounds over all declared radial cells.
Those proofs are obligations until actual endpoint/scalar checks establish them.

Knot fast-path consistency must be checked against the exact interpolants at each
knot. The PWL endpoints coincide with copied values, so the reference remains C0;
smoothstep does not remove scalar/profile derivative breaks. Future represented
output validity, rounding-cell enclosures and resource accounting require tests
and independent implementation review. Child inheritance is proved by restriction
of the same parent function and shared identities, supplemented by bit checks,
not inferred from matched finite samples.

This declaration selects exact assets and model choices for assessment. It does
not establish permission, endpoint admission, numerical implementation readiness
or freeze readiness. The later assessment must label each prerequisite ESTABLISHED,
BLOCKED or UNRESOLVED and retain every rejection. Manufacturer blend, exact
stacking/thickness correspondence and as-built evidence are separate unknowns;
the generated model does not assert them or make them disappear.

No proposed generator, surface, BEM, FEA, trajectory, solid, clearance, strength
or optimum-hinge execution/assessment is authorized here. External CAD/STEP is
optional. PR #81/#84/#91 and C2V-09 remain untouched; no ADR-009 acceptance or
qualification promotion. `physical_qualification=false`.
