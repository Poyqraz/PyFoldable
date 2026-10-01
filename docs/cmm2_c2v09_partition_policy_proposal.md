# Prospective C2V-09 provenance partition policy

Status: **PROPOSED / NOT FROZEN / NOT IMPLEMENTED**.

Policy identity: `prc_c2v09_partition_provenance_neighborhood_v2_proposed`.
This policy is separate from selector v3 and numerical implementation v2; it
creates neither a candidate-selection record nor a Radau seal. Main/base
`4cf0d0ea017fa824ba8d4a063ceddd015dae09d6` still ships RK45/v1.

## 1. Before / after, scope and immutable evidence

Before: the [frozen PR-C section11](cmm2_numerical_verification_contract.md)
requires every literal boundary distance strictly greater than its unchanged
uncertainty. The [captured candidate29 preflight](cmm2_c2v09_candidate29_initial_preflight.md)
records **v1 FAIL**. That JSON, its raw zero distances, source measurements,
observer errors, historical recipes and hashes remain unchanged. A structural
identity classification below must never label a zero row as passing v1.

After, only if independently approved and frozen later: first certify complete
source/mapper topology over the whole initial angle neighborhood; then classify
proven represented endpoint identities, retain all literal rows, and apply the
unchanged strict center-distance plus whole-neighborhood signed-separation
gates across distinct identity classes. This is an explicit prospective
**change in comparison policy**, not reinterpretation of historical acceptance.

Candidate29 is unchanged: [complete manifest](cmm2_c2v09_candidate29_proposal.md),
SHA256 `0b37fb45c005d7a046dee6541d1a89e4a0a5cead7434621718c90d191843b7a4`.
No candidate30, tuning, new geometry/table, numerical threshold or controls.
Original00…28 and their histories remain; candidate28 remains a mapper rejection.
The [timestamp amendment](cmm2_numerical_feasibility_amendment.md) is unchanged.
No production, executable fixture, test, workflow or ADR changes are proposed.
PR81/84 are untouched. Numerical verification is NOT ESTABLISHED; ADR-009
NOT CREATED / NOT ACCEPTED; physical_qualification=false; PR-06C unresolved;
GEOM/calibration/experimental validation NONE.

## 2. Exact initial neighborhood and proof scope

Use the **stored declared binary64 scale**, not a decimal reconstruction or a
fresh recomputation of the scale at nearby angles:

```text
q = Fraction.from_float(theta0)
s = Fraction.from_float(stored_S_theta0)
Theta0 = [q-s, q+s]
theta0 = stored binary64 -0.2 rad
stored_S_theta0 = stored binary64 2.1e-7 rad
```

The exact rational endpoints are in the declaration capsule below. They are
not inward rounded or clamped. The certificate quantifies over **every stored
binary64 angle in this exact closed neighborhood** and all corresponding
represented source operations, including endpoint equality. A rigorous real-
interval extension enclosing all those executions is admissible; discrete
endpoint/center evaluation or sampled angles is not a whole-neighborhood proof.
Other physical/numerical inputs are the immutable candidate29 initial inputs.
No new assessment is permitted until this complete declaration is committed
and independently mathematically reviewed at its exact HEAD.

A proof must bind code/runtime, candidate/seal and input digests; identify each
rounded operation, stored operand and branch; and use exact rational differences
or rigorously outward enclosures. Rounding-cell splitting or analytic error
bounds may prove a universal claim. A guessed libm error, assumed global correct
rounding, center-only hypot/trig observations or smooth-real derivative is
insufficient for actual represented operations. Missing uniform runtime bounds
remain **UNRESOLVED / BLOCKED**. A conditional certificate must identify its
hypotheses and must not be published as unconditional source stability.

## 3. Topology first: actual construction paths

Authority at base4cf: [projection](../pyfoldable/core/foldable_rotor.py),
[radial cells and interpolation](../pyfoldable/core/bem_rotor.py),
[spanwise query](../pyfoldable/core/polar_spanwise.py),
[annulus kernel](../pyfoldable/core/bem.py),
[mapper and native terminal guard](../pyfoldable/core/foldable_aero_load.py).
RN below denotes each actual binary64 operation; do not fuse or reassociate it.

Let R be parsed nominal radius, h stored hinge, c the **actual emitted**
projection factor. The terminal station at1.0 and projected polar anchor1.0
use the same tip expression; finite-normal multiply/divide by2 preserves t.
The first radial limit is reconstructed, not assumed constant:

```text
c = emitted math.cos(stored angle_from_deployed)
t = RN(h + RN(RN(R-h)*c))
r_first = RN(0.2*R)
first_ratio = RN(r_first/t)
a = RN(first_ratio*t)
last_ratio = RN(t/t) = 1.0
b = RN(last_ratio*t) = t
d = RN(b-a)
w = RN(d/4)
E_j = RN(a + RN(j*w)), j=0…4
m_i = RN(0.5*RN(E_i+E_(i+1)))
q_i = RN(m_i/t)
r_kernel_i = RN(q_i*t)
```

All integer operands0…4 convert exactly. `E_0=RN(a+0*w)` and its provenance
must be retained rather than assumed equal by index. First/station/anchor
round trips and kernel recomposition are separate operation paths. The recorded
cell1 midpoint0.05481312416726164 m differs from its kernel radius
0.05481312416726165 m by one ULP; both must remain in the certificate.

Prove `E2(theta) < h < E3(theta)` for all Theta0 before asserting five mapped
intervals or stable ownership. Also prove positive ordered cells, inner coverage,
tip>h, fold/projection validity, inserted-hinge station order, and branch behavior.
Source `_spans` checks outer<=h, then inner>=h, otherwise returns copied
`(inner,h)` and `(h,outer)` endpoints. Under the strict topology, intervals
0/1 copy cells0/1; intervals2/3 split cell2 at h; interval4 copies cell3.
Attaching a role after only inspecting the center is prohibited.

Every boundary occurrence needs a provenance DAG node with operation/copy
kind, exact source operands/paths, original source index, source-object identity,
normalization branch, guard evidence and the all-Theta ownership proof. Node
identity is a mathematical execution/construction identity, not report-ID equality.
For E2 and E3, adjacent-loop constructions have the **same RN graph and operands**:
prior outer uses index+1=k and next inner uses index=k. The mapper then copies
that stored boundary; source-index labels alone are not the proof.

| Canonical owner | Occurrences when topology is proved | Construction obligation |
| --- | --- | --- |
| E2 | cell1 outer; cell2 inner; mapped1 outer; mapped2 inner | Same a,k=2,w operation graph; direct mapper copies |
| E3 | cell2 outer; cell3 inner; mapped3 outer; mapped4 inner | Same a,k=3,w operation graph; direct mapper copies |
| h | hinge; mapped2 outer; mapped3 inner | Copy the same stored hinge through proved split branch |
| E0/E1 | corresponding source/map endpoints | Exact loop node and copied occurrence, not numeric matching |
| mapped terminal / t | normalized mapped4 outer, declared tip | Separate whole-Theta native guard certificate, below |
| m0…m3, geometry/polar q, kernel radius | Independent operation nodes | Retain paths; never substitute midpoint for kernel radius |

The original unnormalized E4 remains a distinct source-edge node from t.
Even if E4=t at the center, those differently rounded constructions are not
an unconditional STRUCTURAL_IDENTITY. The mapped terminal can belong to the
canonical tip class only after proving every native-guard case throughout Theta0.

## 4. STRUCTURAL_IDENTITY and complete comparison ledger

Define the equivalence relation only from proven **whole-Theta represented
construction identities** after topology/ownership certification. Permitted
proofs are direct copies from one stored primitive boundary or demonstrably
identical RN graphs/operands, including proved guards joining certified branches
at one unchanged canonical owner. Do not quotient by numerical closeness,
matching index, derivative equality or real algebraic equivalence with a
different rounding path. Independent coincidence is not structural identity.

Retain every original v1 comparison row, operands, raw center distance,
uncertainty and strict predicate result. Four zero rows remain `v1_pass=false`:

```text
mapped1 outer vs hinge-cell2 inner: E2, raw distance0
mapped2 inner vs hinge-cell2 inner: E2, raw distance0
mapped3 outer vs hinge-cell2 outer: E3, raw distance0
mapped4 inner vs hinge-cell2 outer: E3, raw distance0
```

Add separate fields: `prospective_policy_id`, identities, provenance/certificate
references, proof scope, `STRUCTURAL_IDENTITY_PROVED` or unresolved status,
and additional distinct-class comparison rows. A certified alias is recorded
as a structural incidence **under the new policy**, never as a v1 strict-distance
PASS. If topology/source predicates are unproved, proposed alias certificates
remain conditional and no exemption is authorized.

Boundary universe includes every source radial edge, original/normalized terminal,
hinge, mapped occurrence, source radial midpoint, relevant station/anchor ratio
boundary and query-operation node, with types/units kept explicit. The original
metric comparison universe remains hinge-containing cell endpoints and radial
midpoints in metres; source geometry/span branches additionally compare their
actual dimensionless queries to their appropriate station/anchor boundaries.
Do not mix radii and ratios or introduce a new numerical margin for ratio checks.

For each original tested occurrence r, form boundary-owner classes of **all**
original relevant metric boundaries. Find nearest boundaries over every distinct
class from r; not merely over nonmatching indices. Record tied nearest classes
and all relevant nonidentity pair certificates. Do not hide another nearby
boundary just because r is an alias of one boundary. The unchanged gate is

```text
U(r) = abs(s_tip*sin(theta0))*stored_S_theta0
     + 64*ulp(max(projected_radius_of_r, hinge_radius))
abs(Fraction(r(theta0))-Fraction(B(theta0))) > Fraction(stored_U(r))
```

Use the frozen source-defined s_tip and arithmetic paths, and the original
stored uncertainty at each row. Do not refit, round the distance favorably or
add tolerance. For every relevant distinct-class pair also prove throughout
Theta0 either r−B>0 or r−B<0, with no touching zero. An interval containing
zero is unresolved unless rigorously refined within existing limits; proof of
actual coincidence/crossing fails. Strict center equality to U fails. Missing
proof, changing class ownership or unresolved ordering is BLOCKED. A different
nearest-class label may vary only when every affected signed relation and full
class set is certified; it cannot authorize skipping a comparison.

The all-Theta signed-separation condition is additional to, not a replacement
for, the original center-distance/uncertainty numerical threshold. No new root
control or budget is introduced; proof/refinement exhaustion under existing
work limits is BLOCKED, not a sampling fallback or candidate substitution.

## 5. Complete source branch and native-tip obligations

Before claiming **source-partition stability**, prove actual predicates, not
merely mapper interval endpoints:

1. Mapper coverage/contiguity, `outer<=h` / `inner>=h` / split branches, fixed
   E2<h<E3 ownership and source endpoint copies.
2. Projection and inserted hinge: actual delta/cos, each nominal-radius test
   versus h, stored projected ratios and station order, terminal expression.
3. Geometry interpolation: q_i=RN(m_i/t) versus stored station ratios;
   endpoint `<=`/`>=` and `bisect_right` brackets, positive denominator and
   represented weight in[0,1]. Constant coefficients do not excuse a changing
   interpolation branch. Record r_kernel=RN(q_i*t) separately and prove any
   predicate that actually consumes it using that value.
4. Spanwise polar: its actual q_i versus projected anchor ratios, inclusive
   bounds and chosen adjacent pair/weight. Mach/Re/alpha coverage remains the
   unchanged synthetic table and bounds="error"; the earlier conditional
   source-envelope hypotheses must not be promoted to unproved uniform runtime
   or BEM-success claims. Missing required query/coverage proofs are BLOCKED.
5. Native terminal: prove either E4=t or the actual finite delta=t−E4 satisfies
   `abs(delta)<=2*max(ulp(E4),ulp(t))` and `t>last_inner` at every angle. For
   the equal branch retain source E4, false flag, zero delta; for normalization
   retain original E4, true flag and actual represented delta. Outside the
   guard retain original endpoint and fail exact generic mapping; do not
   enlarge two ULPs or fabricate tip loads. Nonfinite/ownership-unresolved cases
   are BLOCKED. Guard-valid exact and normalized branches may be certified
   piecewise only if the mapped endpoint's canonical tip owner is unchanged;
   varying flags are reported, not silently assumed constant.

A possible proof plan for the native guard is **not a result yet**: certify
both t and d=RN(t−a) in binade[2^-4,2^-3), with finite normal values. Then d/4
and multiplication by4 are exact power-of-two scaling; E4=RN(a+d). Subtraction
and addition each have error at most2^-57, so |E4−t|<=2^-56, one ULP of t,
inside the unchanged two-ULP guard. Certify E3<t independently, and exact
represented delta via the actual subtraction (Sterbenz where applicable).
This conditional plan does not establish actual uniform cos/query predicates.
Different binades or uncertified RN/runtime semantics require their own proof
or BLOCKED; the one-step argument is not a universal native-ULP theorem.

## 6. Concrete policy examples (symbolic, not fixture tuning)

Let s normalize Theta0 to[0,1]; U is the unchanged relevant uncertainty.
These examples illustrate policy decisions, not new fixtures or thresholds.

| Example | Required outcome |
| --- | --- |
| cell1 outer and cell2 inner both RN(a+RN(2*w)); mapped1 outer/mapped2 inner copy them | With whole-Theta topology/path proof: E2 alias class across adjacent source indices; preserve raw0/v1 FAIL |
| Independent A(s), B(s)=A(s)+K*(s−1/2), K nonzero; equal at center | Not identity; strict center distance0 fails and ordering changes: BLOCKED |
| h−E2(s)=delta*(1−8*s*(1−s)), delta>0 | Endpoints positive, interior crosses0: topology/ownership FAIL; endpoints alone insufficient |
| h−E2(s)=delta*(2*s−1)^2 | Interior tangency at s=1/2: BLOCKED despite safe endpoints |
| Distinct pair center distance=U exactly | FAIL: original strict > is preserved |
| r is copied alias of A, but distinct B lies U/2 from r at center | Alias does not hide B; distinct-class gate FAIL |
| q_i crosses a stored station ratio inside Theta0 while endpoints stay in the same outer bracket | Interpolation branch changes/unresolved interior: BLOCKED; equal coefficients do not waive it |
| Terminal E4=t at one angle, differs by one ULP elsewhere, certified guard and lastinner<t everywhere | Mapped tip owner may be proved piecewise; retain false/true flags and original deltas, do not alias raw E4 with t |
| Native terminal error outside unchanged two-ULP guard, or tip<=lastinner | No tip identity/success; exact mapper rejects or unresolved proof BLOCKED |
| Real algebraic a+4*(t−a)/4 equals t, but represented E4 uses separate RN operations | Algebra alone proves no identity; native guard certificate is mandatory |

## 7. Proposed Q4 successor recipe: conjunction, not bits alone

The historical captured recipe and numeric JSON remain unchanged for exact
reproducibility. Its `pass` expression tested only bit identity, while separate
recorded finite/index/metadata/provenance flags were true. This successor
**supersedes that proposed audit expression**; it does not rewrite the old
measured result, hashes or observer errors. New Q4 PASS must be the conjunction:

```python
q4_bit_identity = bits[0] == bits[1] == bits[2]
q4_finite = all(math.isfinite(x) for triple in triples for x in triple)
q4_input_valid = (
    canonical_candidate_matches_committed_manifest
    and main_v1_seal_matches_committed_initial_seal
    and repeated_physical_numeric_inputs_are_identical
    and changed_inputs_are_exactly_permitted_index_and_declared_metadata_delta
    and actual_call_input_hashes_match_reconstructed_call_arguments
)
q4_metadata_index_valid = (
    actual_state_and_projected_schedule_indices_valid_and_changed
    and declared_q4_probe_reaches_each_actual_table
    and unchanged_numeric_arrays_sources_settings_verified
)
q4_provenance_valid = (
    all_source_hashes_match_pinned_code_base
    and each_completed_q4_run_bem_object_is_mapped_once_by_real_mapper
    and actual_mapper_state_and_hinge_rate_match_source_call
    and reported_evaluations_match_actual_finite_mapped_outputs
)
q4_pass = bool(q4_bit_identity and q4_finite and q4_input_valid
               and q4_metadata_index_valid and q4_provenance_valid)
```

The one-map-per-object predicate applies to the completed Q4 comparison run,
not to preserved earlier scratch-observer attempts (7 BEM/6 mapper in total).
Those failures remain visible and are not relabelled successful Q4 evidence.

Undefined, missing or unresolved constituent checks are not truthy defaults;
record `UNRESOLVED / BLOCKED`. Differing report IDs alone are insufficient.
Replay may reconstruct the captured call-input hashes from unchanged manifest,
state/condition/settings and exact permitted metadata delta. If captured
summaries lack needed input/provenance data, that subproof remains BLOCKED;
no new BEM runs or invented evidence fill it here. Keep recorded raw flags
and measured bit triples unchanged; separate replay-derived successor flags.
No change to Q4's numerical bit-identity gate or other Q1–Q5 gates is proposed.

## 8. Initial assessment only, sequence and prerequisites

1. Commit this complete prospective declaration, including capsule and fixed
   proof plan; obtain independent exact-HEAD mathematical review before any
   new captured replay or neighborhood certification.
2. After that review only, replay the committed captured JSON and literal
   manifest, verify their immutable hashes and all original comparison rows.
   Construct the source-operation provenance DAG from the pinned source and
   captured numeric operands; certify the exact closed Theta0 and every branch
   through rigorous outward represented-operation enclosures/case proofs.
3. Use a uniform **actual runtime** trig enclosure only when independently
   justified. A real cosine Taylor enclosure may supply a mathematical
   sublemma, and a coarser c in[7/8,1] can quantify conditional source algebra;
   neither alone bounds emitted libm values throughout Theta0. Publish both
   conditional algebra results and unresolved actual-runtime obligations.
4. Record all rows, identity proofs, distinct-class center gates, signed
   neighborhood bounds, actual query/midpoint/kernel paths, branch/guard cases,
   original terminal provenance and conjunctive Q4 replay. Overall prospective
   PASS requires **every** stated obligation proved for actual Theta0. Any
   unresolved runtime/coverage/identity/ownership predicate remains BLOCKED;
   passing sublemmas must not bypass it. Original v1 remains FAIL.

No new motor/BEM calls, trajectory, ordered selector, production implementation,
future v2 seal or policy freeze is authorized by this assessment plan. The
initial neighborhood certificate does not cover later dense intervals. Later
source/dense intervals need their own complete continuous/represented execution
proof; interior crossing, tangency or uncertain ownership stays BLOCKED or
INCONCLUSIVE even with safe endpoints. No sampling-only clearance, suppression
of failures or candidate substitution.

Affected sections: PR-C11 partition/selection-record fields (explicit prospective
replacement for partition comparison only); PR-C15 Q3 closure (historical closure
unchanged, proposed dependency); PR-C13/16 evidence/manifest provenance (new
policy/certificate binding, immutable candidate); Radau source/domain/ledger
and continuous interval audit dependencies (no method/contact/timestamp change).
Original numerical scales, row Q2, Q4 identity, DOP853 A/B levels, controls,
trajectory gates, fixture ordering and work limits remain unchanged. Historical
acceptance records and normative sections are not overwritten. Later independent
approval/freeze and separately authorized implementation/verification are required;
no accepted PR-C evidence follows from publishing or assessing this proposal.

## 9. Declaration capsule and initial status

Declaration-time assessment: **NOT ASSESSED**. No new replay, source evaluation
or interval certification before independent committed-declaration review.
Capsule digest rule: sorted compact ASCII JSON, UTF-8 without final newline;
all stored floating values below are exact hexadecimal strings, not decimal
float reserialization. Candidate/source/old-measurement digests are unchanged.

Prospective declaration capsule SHA256 `783cfe0cdb1482c85fbc219c181b07d989529776955ac27a0e19b3623aa0f373`.

```json
{
  "Theta0_lower_fraction": "-1888948576541780995587/9444732965739290427392",
  "Theta0_upper_fraction": "-1888944609753935385085/9444732965739290427392",
  "candidate_draft_sha256": "b3d3fd8e58a2476937607e04ecd2651b91cfb4c95c44ea026a39eff57dc167d6",
  "candidate_id": "C2V09-29",
  "candidate_manifest_sha256": "0b37fb45c005d7a046dee6541d1a89e4a0a5cead7434621718c90d191843b7a4",
  "captured_numeric_record_sha256": "183eb23a8bac8c4add42f76539f219c5726b36a613297d5bb7e4c83a331780c9",
  "code_base": "4cf0d0ea017fa824ba8d4a063ceddd015dae09d6",
  "future_v2_seal_authorized": false,
  "initial_assessment_scope": "captured replay plus full-neighborhood source-path proof; every unresolved proof BLOCKED",
  "main_v1_initial_seal_sha256": "389d5565d179358b4530bc98038f3046291594615d1acb0d3873655f678595b9",
  "new_source_calls_authorized": false,
  "policy_id": "prc_c2v09_partition_provenance_neighborhood_v2_proposed",
  "prior_documentation_head": "79100ad0e08fb4549fb232c49ad7cc23ec9a782d",
  "selection_authorized": false,
  "status": "PROPOSED / NOT FROZEN / NOT IMPLEMENTED",
  "stored_S_theta0_binary64": "0x1.c2f8b88dfb80cp-23",
  "theta0_binary64": "-0x1.999999999999ap-3",
  "trajectories_authorized": false,
  "uniform_transcendental_enclosure_requirement": "actual pinned runtime emitted cos/sin paths throughout Theta0; mathematical cosine or center observations alone insufficient"
}
```
