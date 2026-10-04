<!-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0 -->
# Mixed-profile parent geometry — use-scope readiness addendum

**PROPOSED / NOT FROZEN / NOT IMPLEMENTED.** Addendum identity:
`mixed_profile_parent_use_scope_v1`. This is a bounded proposed scope amendment
for independent review, not implementation authorization or an asset license.
Starting PR #94 HEAD: `6d7c33231b9414e1bf85a3a8e0a45adbd95e4c3d`.

## 1. Current repository status; immutable historical authority

Checked 2026-10-04 UTC: PR #93 is merged at main
`6200b050809f7aca3ef3365608eea8cbfd80bd64`. Its tree
`136f451a3ace8ae011120c78174c99824508b42f` equals reviewed proposal HEAD
`1bbd9ccac876d5d612d2ac19e0cc16d492623e99`'s tree. Its merge does not freeze
the proposal or authorize geometry implementation. PR #94 remains Draft/unmerged.
Its earlier stacked-base, Draft #93 and old-main statements describe that earlier
repository state; this separate status record supersedes their current meaning.

The [merged proposal](generated_mixed_profile_parent_geometry_contract.md),
[immutable declaration](mixed_profile_parent_endpoint_declaration.md),
[machine-readable declaration](declarations/mixed_profile_parent_endpoint_model_v1.json)
and [assessment](mixed_profile_parent_endpoint_assessment.md) are unchanged.
Declaration commit `790d110734e0db5c1e09d3d9f4e9e8a0fe52061f`, all input/model
hashes and the assessment at `6d7c33231b9414e1bf85a3a8e0a45adbd95e4c3d`
remain provenance. In particular, selected A stays the exact UIUC E63 asset and
selected B stays the exact tabulated UIUC NACA4412 reference substitute, not APC12.
Their stronger admission PASS, permission UNRESOLVED and prior readiness BLOCKED
statements remain visible. No analytical replacement or new endpoint is selected.

## 2. Five distinct uses and current decisions

| Use | Concrete decision and remaining prerequisite |
| --- | --- |
| Already completed local endpoint assessment | Preserve the authorized parser/arithmetic receipt and private assets. Task authorization is not evidence of a third-party license. No additional use or permission is inferred from admission PASS. |
| Caller-supplied local coordinates/scalars | A general API may consume explicitly supplied inputs in a later authorized implementation. The caller's applicable rights/use scope and notices remain separate from numerical validity. Local supply does not automatically clear E63/NACA4412, APC data, commercial use or output publication. |
| Bundled coordinate redistribution | Selected E63/NACA4412 clearance is **UNRESOLVED**. Do not bundle either raw, normalized or canonical array, auto-download them, or put them in public fixtures/examples/artifacts. Each proposed third-party asset needs applicable permission/attribution evidence for its intended distribution. |
| Publication of complete derived arrays | Selected-asset and APC-derived complete arrays remain **UNRESOLVED / NOT CLEARED**. Normalization, interpolation, model hashing or Project-generated status does not establish redistribution rights. Keep full restricted derivatives private, including CI artifacts; public summaries retain provenance without publishing those arrays. |
| Our own general geometry algorithm and first-party synthetic tests | Independently authored first-party code and genuinely invented software inputs are separable from selected-asset clearance. A narrowly reviewed caller-input implementation can be considered for later authorization under §4, with no selected-asset dataset/demo bundled or cleared by that decision. No implementation occurs here. |

This is repository engineering scope routing, not a determination of all legal
rights in an asset. The Project license covers material it controls; it cannot
grant a caller rights in third-party inputs. Numerical approval and use-scope
approval must be recorded separately, neither inferred from the other.

## 3. Primary-source permission and attribution evidence

Checked 2026-10-04 UTC. The following short quotations are exact wording from
the linked primary pages; the stated limits are not inferred from another database.
No third-party coordinate or full derivative is reproduced in this addendum.

| Primary evidence | Exact applicable wording / observation | Scope conclusion |
| --- | --- | --- |
| [UIUC Airfoil Data Site, Airfoil Contributions](https://m-selig.ae.illinois.edu/ads.html) | “Please include a description of the airfoil and also identify the source.” | This is an instruction to contributors. It supports preserving source identification, not a license to use or redistribute downstream coordinates. |
| [Same page, footer](https://m-selig.ae.illinois.edu/ads.html) | “© 1994 - 2026 UIUC Applied Aerodynamics Group” | A site notice is recorded; no per-file permission grant is established by it. |
| [UIUC coordinate directory](https://m-selig.ae.illinois.edu/ads/coord_database.html) | Lists E63 as Eppler E63 and NACA4412 as NACA 4412; describes formats, contributors and imports. | Collection/file provenance and compatibility only. No affirmative grant applicable to these two files was identified on the checked listing or homepage. Third-party tool links and their licenses do not license the data. |
| [UIUC linked FAQ](https://m-selig.ae.illinois.edu/ads_faq.html) | Provides file-opening, coordinate-location and performance-data guidance. | No applicable permission grant was identified in this checked FAQ. This bounded inspection is not proof that no permission could exist elsewhere. |
| Exact [E63](https://m-selig.ae.illinois.edu/ads/coord/e63.dat) and [NACA4412](https://m-selig.ae.illinois.edu/ads/coord/naca4412.dat) files | Selected byte identities and observed contents are recorded in the immutable declaration/assessment. | Availability, a profile name and coordinate values are not a license. Applicable local-use, distribution and derivative-publication permission remain UNRESOLVED. |
| [APC Terms & Conditions, Copyright](https://www.apcprop.com/terms-conditions/) | “solely for your own non-commercial use”; “unless authorized by Landing Products Inc.”; “not to change or delete any proprietary notices” | The terms describe conditional personal noncommercial display/download/print and restrict other uses, including redistribution. These phrases are qualified by the surrounding restrictions and do not supply blanket permission for geometry derivatives, research/commercial uses or publication. Preserve notices; no new APC clearance is claimed. |

Attribution record for these selected assets retains UIUC Applied Aerodynamics
Group / Michael Selig as collection provenance, source URLs, observed file labels,
acquisition date and raw/canonical/normalized hashes. Eppler/NACA labels do not
establish an identified rights holder or a required downstream citation license.
Any further licensor-specified attribution requirements remain UNRESOLVED.
APC record retains manufacturer, product/member, version/date/hash and notices.
No permission from UIUC propeller measurements, wind-tunnel books, PDAS programs,
NASA publications or the Project license is transferred to these coordinate files.

Repository controls remain [third-party notices](../THIRD_PARTY_NOTICES.md),
[licensing scope](licensing.md) and the [local PE0 contract](local_apc_pe0_geometry_reporting.md).
No permission request is sent and no grant is invented. Before clearing a selected
asset, record the actual applicable grant/authority, permitted uses, restrictions,
attribution, date and immutable evidence identity for that exact asset/use.

## 4. Controlling clauses and precise prospective amendment

| Existing clause, unchanged | Meaning relevant to the narrow scope |
| --- | --- |
| Proposal §3 | Other permitted local or analytic inputs require their own exact reviewed manifest; analytic and tabulated profiles are distinct identities. |
| Proposal §7, first paragraph | Exact endpoint identities/rights and generated assumptions precede implementation authorization; an internally declared first-party parent may proceed independently of vendor reconstruction. |
| Proposal §7, TDD paragraph | Public software checks use synthetic inputs without vendor data. |
| Declaration §1, final paragraph | Both selected assets' permissions remain unresolved; future distribution/use must resolve applicable permissions and attribution. |
| Declaration opening and §6 | This is one selected exact model; changed assets/recipes/scalars/model choices require a new declaration/version and independent review. It supplies no implementation/freeze readiness. |
| Assessment §5 and opening | Selected-model readiness remains blocked by required permission/use-scope decisions; executable conformance is later work. |

Conclusion: the general-code/synthetic route is compatible with proposal §7's
first-party route, but the broad selected-model readiness statement does **not**
currently authorize bypassing its rights gate for a newly generic implementation.
The proposed amendment below explicitly separates the scopes. It must receive
independent review and separate future implementation authorization. Publication
approval of this addendum is not adoption/freeze of the amendment.

**Proposed normative text — `mixed_profile_parent_use_scope_v1`:**

> For the sole purpose of reviewing and subsequently authorizing an independently
> authored general caller-input geometry implementation, the endpoint-rights
> dependency in proposal §7 and declaration §1/§6 applies to the inputs actually
> used, bundled or published by that scope. Unresolved rights of the selected
> `mixed_profile_parent_endpoint_model_v1` assets shall continue to block clearing
> or distributing that selected-asset realization, but shall not be substituted
> for a rights defect in genuinely first-party synthetic implementation fixtures.
>
> The software-only scope MUST use first-party synthetic test manifests, each
> independently identified before measurement/execution, and accept caller inputs
> with explicit source, numerical and use-scope records. It MUST NOT hard-code,
> download, bundle or publicly reproduce the selected E63/NACA4412 assets or APC
> tables/complete derivatives. Unknown rights are not numerical rejection; neither
> numerical PASS nor caller supply is permission. Reports MUST preserve unresolved
> use restrictions. Selected-asset use or public derivative distribution requires
> its own applicable clearance. Caller-controlled local output is not automatic
> permission to publish it, and the API must not automatically upload it.
>
> The original selected endpoint declaration and admitted model MUST remain
> unchanged. Generic fixture/input manifests have distinct identities and MUST
> NOT be recorded as replacements, equivalent endpoints or realization of that
> selected manufacturer example. Such new manifestations require the declaration
> and independent-review obligations of the original proposal; this amendment
> changes only readiness dependency routing, not admission, model arithmetic,
> finite limits, numerical predicates, evidence claims or historical results.

Proposed precedence, only after explicit adoption: this addendum narrows the
rights/readiness dependency in the cited clauses **for the software-only scope**.
The proposal governs the algorithm model; declaration §§2–6 retain their admission,
reference arithmetic, error/work limits and inheritance obligations. Case-specific
source hashes/domain/scalar knots/anchors are not universal fixture defaults:
each generic realization declares its own exact manifest under those methods,
without changing the selected v1 model. The v1 assessment remains its own receipt,
not a certificate for new inputs. No other normative section is replaced.

Current decision: **technically separable and eligible for a later bounded
implementation authorization proposal**, conditional on independent review of this
scope amendment and each required fixture/API declaration. **Not authorized,
frozen or implemented by this task.** Selected-asset readiness remains BLOCKED.

## 5. Concrete implementation-readiness checklist

The following is an acceptance plan, not a new executable API or fixture. Names
describe required records; final API/schema names must be reviewed before coding.
No fixture coordinates, synthetic generated model or output arrays are created here.

| Obligation | Concrete future input/output/evidence | Current readiness |
| --- | --- | --- |
| Caller input/API | Explicit two local byte assets or explicitly declared canonical coordinate arrays; format, raw/ordered/canonical/normalized identities, parser/normalization code identity and use-scope record. Scalar bundle contains immutable `{index,r,c,beta,tau,Y,Z}` SI values, source lineage and knot bits; no hidden file search/network download/profile-name inference. Declare model/domain/anchors/frame/zero-offset baseline, two global hinges and requested sections. Local PE0 adapter is optional; caller-authored SI bundles need no vendor file or CAD. | Proposed record content ESTABLISHED; exact executable schema/signature and fixture manifests UNRESOLVED. |
| Input integrity/admission | Existing parser/canonical checks plus exact single-valued full `[0,1]` branch support, strict x order and whole-cell gap signs; retain count/order/normalization, LE/TE treatment and every rejection. Finite scalar bounds, strict radial order, positive chord/tau, domain/anchor/hinge ownership and supported frame/transform guards precede evaluation. No clipping, deduplication, implicit rotation/extrapolation or endpoint repair. | Method ESTABLISHED; new inputs need their own proof, not archived PASS. |
| Shared finite limits | Declaration §5 byte/row/pair/grid/section/output bounds, 20,000,000 rational operations, 65,536-bit integers and 80…128 trig terms remain unchanged. One counter across admission/proof/scalars/sections/cuts/refinement/retries; charge before each rational operation. No child/retry reset, hidden bulk vectorization escape or fallback. Output bytes and point count checked before expansion/serialization. | Policy ESTABLISHED; enforcement UNIMPLEMENTED. |
| Exact reference | Exact rationals of declared stored binary64 points/knots; exact common-x union, PWL/scalar/smoothstep/blend and positive finite maximum thickness normalization. Knot copies retain stored bits and signed zero. Reference sin/cos are ideal real quantities with bounded rational Taylor enclosures propagated through complete placement before rounding. No rounded intermediate trig surrogate. | Recipe ESTABLISHED conditionally; implementation/oracle UNIMPLEMENTED. |
| Continuous proof | Whole affine-cell admission, scalar cell bounds, convex branch separation, uniform positive thickness denominator, continuous finite maximum and parent restriction arguments. Finite samples supplement these proofs; they cannot prove continuity, positivity or inherited topology. Derivative breaks remain explicit. | Recipe ESTABLISHED; each input proof UNRESOLVED until declared/checked. |
| Rounding evidence | For each new scalar/complete placed coordinate, retain exact target or certified enclosure, actual selected binary64 value/hex, adjacent rounding-cell boundaries and ties-even ownership, derived displacement bounds with units and term/work counts. Exact midpoint/subnormal/signed-zero cases must be explicit. Unresolved cell at term/work limit is BLOCKED; no guessed ULP accuracy or fitted epsilon. | Required evidence ESTABLISHED; executable production-independent oracle/tests UNIMPLEMENTED. |
| Parent/child identity | One immutable parent-manifest digest; shared evaluator/reference map and one shared hinge result per cut. Fixed/tip restrictions use the same global r, c and supplied beta; local s maps to r_h+s with no span rescale/root replay/twist reset. Retained knots have original indices; absent manufacturer hinge rows stay absent, generated hinge IDs stay separate. Test lineage and structural restriction, then bit comparison; finite equality is not the structural proof. | Method ESTABLISHED; executable verification UNIMPLEMENTED. |
| Joint/frame boundary | Explicit zero hardware offset and identity deployed transforms for the ideal baseline; actual joint differences remain UNDEFINED. Record gaps/steps/protrusions/removed or added geometry and offset components/frames separately when supplied. Unsupported offsets/transforms remain blocked, not implicitly zero. | Ideal assumption ESTABLISHED; real joint and surface displacement UNRESOLVED. |
| Expected success outputs | Deterministic local JSON and readable table: input/model/code/use-scope identities, reference/rounded section IDs and certificates, source versus generated station labels, coverage, knot/bracketing correspondence, two complementary cut reports, explicit joint differences and shared budget receipt. Content canonicalization and stable ordering/number/zero encoding must be declared before implementation; avoid run-time timestamps in content digests. No complete solid/clearance/strength field becomes established. | Field obligations ESTABLISHED; exact serialization schema/hashes and generated outputs UNRESOLVED. |
| Expected failure outputs | Fail-closed BLOCKED/incomplete report or documented exception boundary; retain reason/field/input identity and partial diagnostics with budgets, never success arrays from a failed case. Distinguish unsupported numerical input, unresolved proof/budget and uncleared use scope. No automatic public artifact/upload. | Required behavior ESTABLISHED; API exception/report contract UNRESOLVED. |
| Independent regressions | TDD: source immutability; first-party fixture admission/rejection; incomplete endpoint support; knot and transition boundaries; continuous proof versus sampling; thickness maximum; ties/zero/subnormal and bounded ambiguous rounding; shared exhaustion; missing-source hinge labels; both cuts and twist-reset negative control; deterministic hashes; unsupported frames/joints and restricted-output provenance. Independent exact-head reviewer and Python 3.10/3.11 CI. | Plan ESTABLISHED; no tests/fixtures/code created or executed here. |

The two selected-example hinge radii remain 101.6 mm and 127.0 mm, with their exact
stored literals in the immutable declaration. A later synthetic fixture manifest
must explicitly cover these requests if used to test this comparison, without
copying vendor knots. It is a synthetic software check, not an APC result. The
13-inch retained example remains separate from the 250 mm project baseline.

## 6. Readiness result and next bounded prerequisites

**ESTABLISHED:** separation of data rights from first-party algorithm development;
checked primary-source attribution/permission limits; exact clause map and a
reviewable narrow amendment; numerical/API/output/identity obligations above.

**UNRESOLVED:** applicable selected E63/NACA4412 local-use/distribution/derivative
permissions and required attribution; any further APC use clearance; exact generic
API/serialization and first-party fixture manifests; future executable conformance.
The asset-rights findings are bounded observations, not inferred licenses or an
assertion that all possible rights have been exhausted.

**BLOCKED / NOT GRANTED:** selected-asset implementation/freeze readiness; adoption
or freezing of this proposed amendment; any software implementation or generator
execution in this task. The next software-only prerequisite is independent review
of this exact addendum, followed by explicit bounded authorization and reviewed
fixture/API declarations. That route need not wait for unrelated asset clearance
if the proposed scope separation is explicitly adopted. New manifestations still
need rights for their own inputs, numerical admission and exact identities.

Manufacturer blend/coordinate/stacking/thickness equivalence and operating-condition
optimality remain unknown. As-built identity, complete surfaces/solids, clearance,
strength and experimentally supported selection are separate assessments, not
blocked software dependencies that can be silently promoted by CI. External CAD
remains optional. No generator, source/BEM/FEA, clearance, strength or trajectory
call is made. PR #81/#84/#91 and C2V-09 are untouched; no merge/freeze, ADR-009
acceptance or qualification promotion. `physical_qualification=false`.
