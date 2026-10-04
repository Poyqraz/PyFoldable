<!-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0 -->
# Generic mixed-profile sections — API and synthetic declaration v1

**PROPOSED / NOT FROZEN / NOT IMPLEMENTED.** Declaration identities:
`mixed_profile_parent_generic_api_v1`, codec `mpg_canonical_ascii_hex_v1`, method
`mixed_profile_pwl_smoothstep_vertical_thickness_v1`. Starting PR #94 HEAD is
`5f75737d99650d348f4f31ed565d392687821106`; base main is
`6200b050809f7aca3ef3365608eea8cbfd80bd64`.
The coordinator accepts the [use-scope separation](mixed_profile_parent_use_scope_readiness_addendum.md)
as the design basis for preparing this generic contract. That supersedes its
earlier adoption-pending statement for that basis only; it does not freeze the PR,
clear assets or authorize implementation. All earlier files remain unchanged.

The [fixture manifest](declarations/mixed_profile_parent_synthetic_fixtures_v1.json)
is a static documentation declaration, not an executable fixture or measured
output. It was authored from small invented dyadic polygons and six invented SI
rows; only the two public task hinge literals are inherited. It is not a substitute
for E63/NACA4412 or an APC realization. No generator or coordinate parser is run
to create this declaration. Hashing these declared bytes is not a geometry run.

## 1. Exact planned public API and compatible reuse

Planned module: `pyfoldable.application.mixed_profile_parent_geometry`.
These signatures/types are declarations, not present implementation:

```python
def parse_mixed_profile_request(raw: bytes) -> MixedProfileParentRequestV1: ...
def evaluate_mixed_profile_parent(
    request: MixedProfileParentRequestV1, *, execution: GeometryExecutionV1
) -> MixedProfileParentReportV1: ...
def render_mixed_profile_table(report: MixedProfileParentReportV1) -> str: ...
```

All request/record dataclasses are frozen, slots-based and recursively immutable;
sequences are tuples. Wire objects below map one-for-one to those DTO fields.
No filesystem path, catalog lookup, URL fetch, solver, callback or implicit unit
conversion is part of this service. `execution` supplies identities, not numerical
controls. The hard limits/model methods are fixed by this declaration and its
parent policy, not caller-tunable budgets/tolerances.

Reuse `application.blade_stations.StationPoint(radius_m, chord_m, twist_rad)` and
`StationProvenance(kind, reference, locator, revision, parent_sha256)` as value
records. Restrict provenance kind to existing `declared_design`,
`literature_geometry`, `project_measurement`, `derived_geometry`; the latter
requires a parent digest. First-party fixture kind is `declared_design`, explicitly
non-measured. Do not manufacture a single-profile `StationBundle` or `BladeGeometry`.
Use `core.airfoil.parse_airfoil_coordinates(..., file_format="selig")`,
`validate_airfoil_definition` and `airfoil_coordinate_sha256`, with owned
`AirfoilDefinition` snapshots internally. Its metadata is not the request schema
and cannot override any declared identity. Existing sparse services remain unchanged.

| Request DTO / exact wire fields | Type and meaning |
| --- | --- |
| `MixedProfileParentRequestV1` | `schema_id: str` exactly `mixed_profile_parent_request_v1`; `scenario_id: str`; `endpoint_A/B: EndpointInputV1`; `scalars: tuple[ScalarKnotV1,...]`; `scalar_provenance: StationProvenance`; `scalar_use_scope: UseScopeV1`; `model: ModelV1`; `hinges_m: tuple[float,float]`; `section_requests_m: tuple[float,...]`. |
| `EndpointInputV1` | DTO `identity: str`, `raw_bytes: bytes`, `file_format: str` exactly `selig`, `expected_raw_sha256: str`, `use_scope: UseScopeV1`. Wire substitutes `raw_text: str` for `raw_bytes`, encoding exact ASCII bytes without newline conversion; no second alias. |
| `UseScopeV1` | `kind: str` one of `FIRST_PARTY_SYNTHETIC`, `CALLER_LOCAL_DECLARED_PERMITTED`, `CALLER_LOCAL_UNCLEARED`; `reference: str`. Records caller claims, not independently granted rights. Unresolved rights are retained separately from numerical validity. All output is local; no automatic publication. |
| `ScalarKnotV1` | `index: int` original nonnegative strictly increasing source index; `point: StationPoint`; `tau: float`, `Y_m: float`, `Z_m: float`. Wire `point` has exactly its three existing field names. Source indices need not be contiguous. Two to 64 knots. |
| `ModelV1` | `method_id: str`; `domain_m: tuple[float,float]`; `transition_m: tuple[float,float]`; `frame: str`; `stack_fraction: float`; `hardware_offset_m: tuple[float,float,float]`; `hinge_axis: str`; `deployed_transforms: tuple[str,str]`; `actual_joint_modifications: str`. |

Model values: method ID above; frame `shaft_radial_tangential_axial_v1`; stack
fraction exact binary64 0.25; hardware offset all positive zero; axis
`positive_shaft_axial`; both deployed transforms `identity`; actual joint
modifications `UNDEFINED`. Domain endpoints must be the first/last knot's stored
radii. Require domain-start < a < b < domain-end. First scope supports exactly
hinges `(0x1.a027525460aa6p-4, 0x1.04189374bc6a8p-3)` in that order and both
strictly inside the domain. Requested sections are strictly increasing finite
stored radii in the closed domain, at most 68. They may coincide with knots,
anchors or hinges; the resulting exact union is deduplicated by numeric identity,
not proximity. Radial zero is not in this first scope's positive knot domain.

All schema keys are exact: missing/extra/duplicate keys rejected. IDs are nonempty
ASCII of at most 256 bytes; provenance/use-scope strings are nonempty ASCII at most
2048 bytes. Raw coordinate text is bounded ASCII, preserves LF/CR exactly and is
not stripped/rewritten. Canonical JSON escapes controls. The whole request JSON
is at most 2 MiB; each endpoint remains at most 256 KiB. Version one accepts no
arbitrary JSON metadata. ASCII bounds are a new generic API boundary, not a change
to the old parser's behavior for its other callers.

## 2. Ownership, validation order and failure boundaries

Parse/constructor does not acquire external data. DTO fields are exact builtin
types (bool is not an int/float); a copied `StationPoint` uses exact builtin floats.
The service takes an owned snapshot before work and never mutates inputs. Core
metadata is copied into internal records and cannot retain caller containers.

Decoder: bounded bytes, strict ASCII JSON, duplicate-key hook before schema checks,
then exact fields/types and canonical finite hex decoding. Reject JSON floating
tokens, NaN/Infinity, surrogate strings and noncanonical hex spellings. Decode
failure raises `MixedProfileDecodeError(code: str, field: str, raw_sha256: str | None)`;
there is no fabricated request/report digest. Decoder codes are `INVALID_JSON`,
`DUPLICATE_KEY`, `UNSUPPORTED_SCHEMA`, `FIELD_SET`, `FIELD_TYPE`, `INVALID_F64_HEX`,
`REQUEST_BYTES_LIMIT`, `INVALID_ASCII`. An oversized input is not hashed; raw
digest is null. No unbounded decoded input is allocated. Wrong root types supplied to
public functions raise `TypeError` before work. A typed request with invalid data
returns the deterministic BLOCKED report described below, not a silent repair.

Validation stage order is fixed; first failure wins, with one primary diagnostic:

1. `REQUEST`: own fields, sizes/types/texts, finite floats, supported model/frame/
   offsets/hinges, execution-context structure. Invalid data: `INVALID_REQUEST`,
   `NONFINITE_INPUT`, `UNSUPPORTED_MODEL` or `UNSUPPORTED_HINGES` as applicable.
2. `HASHES`: actual endpoint byte SHA versus claimed digest, A then B;
   `RAW_HASH_MISMATCH` on mismatch. Compute request canonical identity once finite
   typed representation is available, even if later numerical admission fails.
3. `SCALARS`: original index/radius order, all declared finite range/positivity
   guards, exact domain/anchor/section membership. Any violation: `SCALAR_INVALID`.
4. `ENDPOINT_A`, then `ENDPOINT_B`: pinned core parse/validator, source counts and
   correspondence, no reversal/deduplication/hidden repair, exact stronger branch
   support/order/gap proofs. Expected `AirfoilGeometryError` or failed stronger
   predicate becomes `ENDPOINT_INVALID`, retaining the actual core failure if it
   occurred first; never claim a later proof ran. Parser PASS alone is insufficient.
5. `PROOFS`: scalar-cell bounds, convex-blend gap and denominator certificates;
   unresolved/failed reference proof: `PROOF_UNRESOLVED`.
6. `SECTIONS`: deterministic sorted union; certify each complete section before
   retaining it. Ambiguous output rounding: `ROUNDING_UNRESOLVED`; nonfinite output:
   `NONFINITE_OUTPUT`. Retry is inside the same stage/counters.
7. `CUTS`: create both complete child views atomically from parent section identities.
8. `SERIALIZATION`, then `COMPLETE`: output limit checks and canonicalization.

Resource failure at any stage is `BUDGET_EXHAUSTED`, `INTEGER_BITS_EXCEEDED`,
`INPUT_LIMIT` or `OUTPUT_LIMIT`. `MixedProfileInternalError(partial_report)` wraps
unexpected `Exception` after snapshot with the original cause, never COMPLETE.
Before a usable snapshot its partial report is None. `KeyboardInterrupt`,
`SystemExit` and inability to allocate a bounded failure receipt propagate; no
success report is promised for operating-system failure. Expected blocked cases
are normal return values; exception text/tracebacks/addresses never enter content.

On BLOCKED, retain verified input receipts, proof records and only fully certified
completed sections in ascending-radius prefix, budget counters and the first
diagnostic. No unfinished section or cuts are presented as accepted. A missing
request/parent identity is null. Failure serialization must stay within 16 MiB:
drop completed sections from the end until it fits, recording `omitted_sections`
and preserving completed-section count; never relabel omissions as measured zero.
At most 68 such size passes, under the same counters. No external file is written.

## 3. Canonical bytes, exact values and digest scope

Codec `mpg_canonical_ascii_hex_v1`:
`json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
allow_nan=False).encode('ascii')`; no BOM, whitespace or terminal newline.
Object keys are ASCII and lexicographically sorted. Arrays retain schema order;
they are never generically sorted. Raw text is a JSON string preserving its exact
bytes. JSON primitives are strings, bool, null and integers only, never float tokens.
Integers have normal base-10 JSON syntax; count values are nonnegative and bounded.
All binary64 quantities are lowercase exact Python `float.hex()` strings, and a
decoder must round-trip to that identical spelling, including `-0x0.0p+0`.
All nonfinite representations are forbidden.

`RationalV1 = {"n": str, "d": str}` is a reduced exact fraction, n decimal signed
integer (no `+`, leading zeros or `-0`), d positive decimal integer; gcd=1 and zero
is `{"n":"0","d":"1"}`. Integer bit limits apply. Rationals are mathematical
values and do not carry a zero sign; copied zero sign lives in the binary64 field.

`sha256` means lowercase SHA-256 of these canonical bytes. No digest includes its
own field: each identified record is `{"sha256": digest, "content": payload}`.
Request identity hashes the exact wire request payload (including raw text,
expected raw digest, input identities, provenance and use claims). Input/scalar
hashes have their own explicitly scoped payloads, not an ambiguous name-only hash.
The legacy coordinate `.17g` pair digest remains separate from this hex-JSON codec.

`ParentManifestV1` payload has exactly `schema_id`, `method_id`, `policy_ids`,
`endpoint_A`, `endpoint_B`, `scalars`, `scalar_provenance`, `scalar_use_scope`,
`model`. Each endpoint manifest has `identity`, `raw_sha256`,
`canonical_coordinate_sha256`, `normalized_points_hex`, `use_scope`.
`policy_ids` is the ordered tuple `(mixed_profile_parent_generic_api_v1,
mixed_profile_parent_use_scope_v1, mixed_profile_parent_endpoint_model_v1)`;
the last denotes inherited numerical-method/limit clauses only, **not** selected
assets/scalars or a certificate for the new inputs. Parent SHA binds the complete
normalized represented inputs/model, not requested cuts, runtime or outputs.
Changing an input/model/method/provenance changes parent identity. Request SHA also
binds hinges/requests. Normalized points retain original order/count and hex bits.

Execution context `GeometryExecutionV1` has exactly `run_id: str`, `started_utc: str`,
`python_build: str`, `platform: str`, `code_sha256: tuple[(path,str),...]`,
`binary_sha256: tuple[(path,str),...]`, `rounding_mode: str`. ASCII bounds above;
digests validated; sorted unique path pairs. It is a caller/runtime observation,
not an alternate-runtime certificate. The sidecar contains this context plus
`content_sha256`; its own canonical bytes/digest are separate. Run IDs, wall times,
host/library labels and timestamps are excluded from deterministic content.
At most 32 code and 16 binary identity pairs, with each path at most 2048 ASCII
bytes; no unbounded arbitrary environment inventory is accepted.
Code identity belongs to execution provenance; the method/policy identity belongs
to parent content. Equal content hashes do not waive code/permission validation.

## 4. Exact report DTOs and wire layout

`MixedProfileParentReportV1` has `canonical_json: bytes`, `sha256: str`,
`execution_json: bytes`, `execution_sha256: str`. The renderer takes that report,
checks identities/schema and renders only deterministic content; readable decimal
values use `.17g`, with a separate exact hex column and explicit negative-zero
label. The table is descriptive, not a second numerical evaluator/oracle.
Corrupt report/schema/digests raise `MixedProfileReportError(code,field)`, code
`INVALID_REPORT`; rendering cannot repair a report or recompute geometry.

Deterministic report content has exactly:

| Key / record | Exact fields and ordering |
| --- | --- |
| Root | `schema_id` = `mixed_profile_parent_report_v1`; `request_sha256` nullable; `status` = `COMPLETE` or `BLOCKED`; `stage` from §2; `diagnostics`; `inputs`; `proofs`; `parent`; `sections`; `cuts`; `budget`; `completed_sections: int`; `omitted_sections: int`; `qualification`. |
| Diagnostic | `code`, `field` (JSON pointer), `predicate` (stable identifier), `details` (bounded ASCII, no raw exception repr). Zero on COMPLETE, one on BLOCKED. |
| InputReceipt | `role` = `A`, `B`, `scalars`; `raw_sha256` nullable for scalars; `canonical_sha256` nullable before validation; `point_or_row_count: int`; `use_scope: UseScopeV1`. A/B/scalars order; only observed/verified fields filled, no copied unchecked claim. Scalar digest is canonical bytes of the complete ordered scalar wire array. |
| ProofRecord | `kind`, `content`. Kinds: `branch_cell` with `role,cell_index,x_l,x_r,gap_l,gap_r`; `scalar_cell` with `cell_index,field,lo,hi`; `denominator` with `x_star,gap_A,gap_B,lower_bound`; `normalization` with `role,input_count,returned_count,raw_sha256,normalized_sha256,reversed: bool,removed_count: int`. Fractions in RationalV1; field names from scalar records. Order normalization A/B, branch A/B increasing cell, scalar cells then fields c/beta/tau/Y/Z, denominator last. |
| Parent | null until proofs complete, otherwise identified ParentManifestV1 (`sha256,content`); input declaration/identity without proof is not a successfully admitted parent. |
| SectionContentV1 | `schema_id` = `mixed_profile_section_v1`, `parent_sha256`, `global_radius_m` hex, `station_kind`, `source_index` nullable, `bracketing_indices` nullable pair, `scalar_hex` (c/beta/tau/Y/Z), `scalar_certificates` in that field order, `blend_weight` RationalV1, `points`. Each retained section record is `{sha256,content}`. |
| SectionPointV1 | `branch` upper/lower, `x_hex`, `v_reference` RationalV1, `xyz_hex` triple, `xyz_certificates` triple. Order upper increasing exact common x then lower increasing x; duplicate LE across sheets is deliberate and counted. No TE closure/solid/caps. |
| CutContentV1 | `parent_sha256`, `hinge_m` hex, `hinge_section_sha256`, `fixed_section_sha256s`, `tip_section_sha256s`, `hardware_offset_m` hex triple, `deployed_transforms`, `actual_joint_modifications`. Identified `sha256,content` records, hinge order. Arrays in global-radius order. |
| BudgetV1 | `rational_limit`, `rational_used`, `integer_bits_limit`, `max_integer_bits`, `max_trig_terms`, `input_bytes`, `output_bytes`, `unique_sections`, `output_points`, `retry_count`; all ints. `output_bytes` is the explicitly projected byte count defined in §5; the actual final byte limit is checked separately. |
| QualificationV1 | exactly `physical_qualification: false`, `manufacturer_equivalence: "UNESTABLISHED"`, `as_built: "UNESTABLISHED"`, `solid: "UNESTABLISHED"`, `clearance: "UNESTABLISHED"`, `strength: "UNESTABLISHED"`, `optimum_hinge: "UNESTABLISHED"`. |

Retained station label is `RETAINED_INPUT_STATION`, not automatically manufacturer
data; generated label is `GENERATED_SECTION`. Source index exists only at an exact
stored knot. Generated sections carry their actual enclosing original index pair,
including declared anchor/hinge requests, not invented source rows. Child arrays
reference the one parent section record; hinge record is shared by both children.
No coordinate duplication/re-evaluation to make children appear equal. Cut map
restrictions remain structural r<=r_h and r>=r_h, with local s=r-r_h only a label;
no chord/twist rescaling, distal reset or root replay. Parent/section/cut hashes
have no self-reference. Changing execution sidecar alone leaves content unchanged.
Parent manifest schema ID is `mixed_profile_parent_manifest_v1`. InputReceipt's
A/B canonical digest is the legacy `.17g` coordinate digest; scalar digest is the
new codec's ordered scalar-array digest. Execution sidecar has exactly
`execution` (the context) and `content_sha256`; its digest hashes that whole payload.
Proof denominator uses exact x_star=1/2, with lower_bound=min(gap_A,gap_B)>0.

## 5. Shared budget and rounding certificate records

All limits of immutable declaration §5 remain unchanged. One owned budget counts
before every exact-rational add/subtract/multiply/divide/compare across validation,
proofs, caching, retries and cuts. Charge even exact-zero/fast comparison paths;
cached reuse performs no charged arithmetic unless it actually executes arithmetic.
No counter reset. Parsing/hash/serialization loops are bounded by existing byte,
row, point, section and output limits, not disguised rational work. Predict/bound
integer allocation from operand bit lengths before multiplication/addition and
check reduced results; normalization/gcd cannot bypass the 65,536-bit bound.
The private budget primitive is `GeometryBudgetV1.charge(operation) -> None`,
operation one of add/subtract/multiply/divide/compare. It increments used by one
only when used<limit; otherwise raises `GeometryBlocked(code="BUDGET_EXHAUSTED")`
before work, leaving used unchanged. Production starts at zero, with the fixed
limit; only a unit harness may prime it. Caught GeometryBlocked becomes the
normal service BLOCKED report. Inputs are never given a priming control.
Report maximum intermediate bit size and retry counts. First trig order is 80,
then 96,112,128 if needed; term ceilings and reference equations are unchanged.

Prevent self-referential `budget.output_bytes`: store it as the exact byte length
with that field replaced by null **for this byte count only**. This projection is
explicit; the actual 16 MiB limit applies to final bytes including the integer.
There is no fixed-point digest/length iteration. Serialization failure retains a
bounded deterministic prefix as §2, with counters never reset.

`RoundingCertificateV1` has exactly `kind`, `unit`, `reference` nullable RationalV1,
`enclosure_lo/hi` RationalV1, `output_hex`, `predecessor_hex`, `successor_hex`,
`cell_lo/hi` RationalV1, `cell_lo_closed/cell_hi_closed` bool,
`absolute_error_bound` RationalV1, `trig_terms: int`, `zero_rule`.
Kind is `COPIED_INPUT` or `CERTIFIED_ROUNDING`; unit is m/rad/dimensionless.
For exact rational nontrig references, reference is filled. For placed coordinates
with ideal sin/cos it is null and the rigorous complete-expression enclosure is
filled. No intermediate trig rounding or assumed libm correctness. To accept,
prove exact target ownership or whole certified enclosure inside the actual
selected nearest/ties-even cell, plus finite output and relevant zero-sign rule.
Displacement is max of exact output-to-enclosure endpoint differences, not a fitted
tolerance. Remaining ambiguity at 128 terms/shared budget is BLOCKED.

For CERTIFIED_ROUNDING nonzero finite outputs, adjacent values are numerical binary64 neighbors;
cell edges are exact midpoints, closed iff selected significand is even. For zero,
neighbors for arithmetic are -min-subnormal/+min-subnormal. Newly evaluated exact
zero yields +0. Its cell is [0,min-subnormal/2]; negative underflow -0 owns
[-min-subnormal/2,0), endpoints as written. Copied -0 has reference 0 and an
explicit `PRESERVE_INPUT_SIGN` zero rule: it is direct inheritance, not evaluation
selecting -0 at exact zero. Its degenerate copied cell is [0,0], no rounding claim;
COPIED_INPUT certificates use equal enclosure/reference/output numeric value,
zero error and zero trig terms. All COPIED_INPUT cells, including nonzero values,
are the degenerate [v,v], both closed, with actual numerical neighbors recorded;
they assert copying, not nearest-cell evaluation. New zero rule is `EXACT_ZERO_POSITIVE` or
`SIGNED_UNDERFLOW`; nonzero is `NOT_ZERO`. Exponent boundaries and subnormal ties
need actual cells, not a symmetric guessed ULP. The declared coordinate bounds
preclude infinities; overflow or missing finite-cell evidence remains failure.

## 6. Declared-before-assessment synthetic literals and expectations

The static JSON declares S01's complete wire request, exact raw ASCII coordinates,
hex coordinates/scalars, hashes, R01…R11 rejection/unit declarations and symbolic
expectations. No endpoint/profile/scalar was copied from any vendor/database.
These are first-party software-check identities under the Project license, not
source-geometry, performance, strength or optimality evidence. JSON lives under
`docs/declarations`, not executable tests/fixtures. Declarations must be committed
before any future generator measurement. Pure byte/hash/math review is distinct
from executing that generator, which remains forbidden in this task.

S01 uses a nine-point closed A and eleven-point open B, union x grid of nine dyadic
abscissae. Six stations have varied chord, supplied beta, tau and Y/Z; row0/row4
Y contains negative zero. Anchors 1/16 and 1/8 m are existing synthetic knots.
Both requested hinges are missing input stations, with brackets (2,3) and (3,4).
The unique radial set is eight sections; fixed/tip ordinal restrictions are
0…3 / 3…7 and 0…5 / 5…7. These are declared expected indices, not measured results.
Uniform denominator identity is d=(3-w)/16 for these invented graphs: each
endpoint's maximum gap is attained at x=1/2, so the convex weighted sum is the
maximum too. Positive d, exact τ scaling, knot bits and smoothstep endpoint
values/derivatives are decisive expectations. Binary64 placed outputs additionally
require independent rounding certificates; no executed output/report hash exists.

R01 radius order, R02 zero chord, R03 mismatched claimed raw digest, R04 unsupported
frame and R05 wrong hinge literals have exact stage/code expectations. R06…R08
declare malformed endpoint bytes and update their raw hashes deliberately, so
hash rejection cannot falsely satisfy geometry-rejection tests. Their violations
are repeated branch x, incomplete support and crossed branches. If core validation
rejects earlier, retain that actual ENDPOINT_INVALID reason and do not invent a
later stronger-proof measurement. R09 duplicated JSON key tests decoder rejection.
R10/R11 are budget-primitive declarations with primed counters, **harness only**,
never a caller request/control. Both retry and child paths must preserve exhaustion.

No fixture adaptation after measurement is permitted. Any literal/method/expected
predicate change requires a new version/record and review, preserving this one.
Selected E63/NACA4412 permissions and all prior records remain unchanged.

## 7. Bounded readiness decision and first implementation scope

The explicit API, encoding, error boundaries, budget/certificate types, parent/
child lineage and small first-party literal declarations above close the former
unspecified API/fixture design items, subject to independent exact-head review.
The review/receipt will identify a concrete defect rather than claim executed
conformance. This declaration itself grants no implementation or freeze approval.

Proposed first authorized implementation slice: this one synchronous local service,
strict request decoder, owned records/shared budget, exact proofs and rounded
sections plus two reference-only cut reports, renderer and a small caller-input
CLI. TDD only with these first-party manifests and additional separately declared
unit arithmetic cases; independent exact-head numerical/API review and CI. Reuse
existing parsers/value records without changing old sparse reporting behavior.
No mesh connectivity, full solid, asset download/bundling, vendor demonstration,
UI expansion, BEM/FEA/trajectory, clearance, strength or hinge selection. No selected
asset run is included even if the generic software later passes tests.

Remaining implementation evidence is a later authorized task, not a requirement
to implement secretly before readiness review. A review finding on these declared
contracts is a concrete blocker; unresolved selected-asset rights are outside this
software-only route. External CAD remains optional; 13-inch manufacturer and
250 mm project scenarios remain separate from S01. PR #81/#84/#91 and C2V-09 stay
untouched. `physical_qualification=false`; no ADR-009 acceptance, freeze or merge.

## 8. Immutable synthetic content identity ledger

These are input/declaration hashes, not measured output hashes. Every R case
has its complete `case_sha256` (all fields except that field); request overlays
also hash their exact definition object. Overlays are ordered RFC6901 replace
operations on a deep copy of S01; replace requires an existing path, no additions
or implicit coercions. They describe future tests, not an executable selector.

| Payload | SHA-256 |
| --- | --- |
| Fixture JSON file bytes (pretty layout, terminal LF) | `99b2f9f746e799ef03a1eb8dd2c45f2ee6bc606d35b93a9fabdaf50eace363e2` |
| Entire canonical fixture-declaration payload | `4cd0305a09cb2a460f334d0508af45b5b93fccb239fe6b2ad06bc131d386be02` |
| S01 canonical request | `b444f14537c678624f63f734aa4c9cad8137cccd0d96a691185ec6b96c62cfcf` |
| S01 complete ordered scalar array | `6b3187378e5346f1bd25014d87276c08f3a1efe6db88f3989a66abc70c4129fd` |
| S01 A raw bytes | `0a137a1a7bfeec6a0ca421c1abd2e529758a445f08abc192875ddfa0e3c713b0` |
| S01 A source-order / normalized / canonical .17g pairs | `9be4a0ee2f8247fc14d88e1fe3c85150da6ac00fcb5773801b2639221ea93008` |
| S01 B raw bytes | `f68417c98523bdf1faaa5f1db516529b1c06e6b750e09124e9a2c202c9ae6fe2` |
| S01 B source-order / normalized / canonical .17g pairs | `7e5fe0d604d4b97210816a5ff4bccdcd9a374e9350de4d724c95bd9526e9c2ae` |
