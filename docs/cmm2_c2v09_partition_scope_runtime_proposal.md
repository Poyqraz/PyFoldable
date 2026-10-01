# Prospective partition proof-scope and concrete-runtime clarification

Status: **PROPOSED / NOT FROZEN / NOT IMPLEMENTED**.

Policy identity: `prc_c2v09_partition_geometry_scope_v3_proposed`.
This is a separately versioned prospective clarification of
[partition policy v2](cmm2_c2v09_partition_policy_proposal.md), not a rewrite of
that declaration, its [historical assessment](cmm2_c2v09_partition_initial_assessment.md),
the [frozen PR-C contract](cmm2_numerical_verification_contract.md), or an
accepted obligation. Candidate29 remains unchanged and **NOT SELECTED**.
The [timestamp amendment](cmm2_numerical_feasibility_amendment.md) is unchanged.

## 1. Before / after and why a new version is explicit

The v2 capsule called for actual emitted cos/sin paths; its assessment grouped
uniform projection/query/coverage and BEM convergence under one unresolved
runtime/source blocker. Those words and results remain historical facts.
They do not establish that frozen PR-C section11 inherited a universal
all-angle BEM-success/convergence selection requirement. Its Phase B is an
**initial-state** preflight; its later unresolved-partition and source/domain
failure provisions remain fail-closed, not advance promises of success.

This prospective v3 changes the obligation scope explicitly: the geometric
certificate below requires actual emitted **cosine** and represented geometric
operations, with the stored initial uncertainty unchanged. It does not demand
a universal sine accuracy theorem or universal nongeometric BEM success as a
condition of that geometric certificate. This is a proposed policy dependency
clarification; it is not retroactive v2 PASS and does not weaken any source
rejection, strict distance threshold, work limit, or future failure handling.

## 2. Three separate claims and dependencies

| Claim | Definition and authority | What it does not establish |
| --- | --- | --- |
| A: whole-Theta0 represented geometry | Complete partition, normalized geometry/spanwise-query branches, native terminal guard and mapper ownership under the exact candidate operations and concrete runtime, conditional on a valid returned source object | Existence or convergence of a BEM solution at every angle; numeric load accuracy; later dense-interval clearance |
| B: initial-state source/preflight evidence | Previously captured real initial motor/BEM/map success and individually recorded Q2/detectability/domain/Q4 results under inherited rules; original v1 partition FAIL remains | Every-angle source success, ordered selection, a prospective policy PASS or a v2 seal |
| C: stronger every-angle source success | Uniform Mach/Re/alpha query coverage, other BEM transcendental paths and solver convergence at every angle | This is unproved; it is not inherited from frozen PR-C section11 and is not required merely to certify A |

A valid returned source object means the actual unchanged source code has
returned its finite, internally validated object for the same immutable
candidate inputs, current represented angle and initial non-angle state,
settings/annulus count and provenance. Its geometric fields must be generated
by the pinned operation graph and its mapper must use that same object.
An arbitrary object that merely passes type checks is not this hypothesis.
The hypothesis cannot create source data, mask a rejection, fill a radial gap,
replace numeric loads or turn a failed source call into a successful callback.
A certifies geometric consequences **if** that object exists; B records one
actual successful initial call. A+B do not imply C.

For A, geometric coverage includes station/spanwise anchor coverage and the
actual normalized query branches. Mach/Re/alpha coverage and convergence are
nongeometric source-success questions under C. Bounds remain `"error"` at
every call. A source domain/convergence rejection at initial preflight remains
rejection; an unexpected/provenance/Q4 failure remains a contract block under
the unchanged frozen selector. Later callback/domain/budget failures retain
the existing failure policy. No trajectories or selector execution are
permitted by this clarification.

## 3. Exact neighborhood, unchanged uncertainty and geometric obligations

Use the original stored scale, exactly:

```text
theta0 = Fraction.from_float(stored binary64 -0.2)
s = Fraction.from_float(stored binary64 2.1e-7)
Theta0 = [theta0-s, theta0+s]
```

The capsule gives both rational endpoints. Certification covers every stored
binary64 angle in this closed interval and all represented operations, not
center/endpoints/sampling. The candidate's deployed angle is stored +0.0;
its subtraction path must be checked, not bypassed when binding cosine input.

Every geometric obligation of v2 remains: finite positive projection; complete
station ordering; actual `q_i=RN(m_i/t)` geometry and spanwise-anchor branch
predicates; distinct `r_kernel_i=RN(q_i*t)` (the captured one-ULP discrepancy is
preserved); cells and strict `E2<h<E3` ownership; endpoint construction/copy
provenance; identity only for the same represented construction across the
whole neighborhood; all original rows/raw distances and strict v1 flags;
nearest boundaries over distinct identity classes; every unchanged strict
center-distance/uncertainty gate; every signed whole-neighborhood separation;
and unchanged native terminal normalization with original radius/delta/flags.
The prior 62 conditional distinct-class comparisons and represented RN lemmas
may be connected only after their actual-runtime hypotheses are established.
Nothing weakens independent coincidence, equality at the strict threshold,
interior crossing/tangency, changing ownership or unresolved decisions.

The uncertainty is the **captured stored center uncertainty** from the original
initial measurement. Its exact rational value and original provenance are
retained. A does not recompute it at each angle or require all-angle sine
accuracy; no new tolerance is introduced. A real cosine Taylor enclosure is
not a bound on emitted libm cosine; that missing execution link must be proved.

## 4. Concrete-runtime certification plan, declared before assessment

After commitment and independent exact-HEAD review of this complete declaration:

1. Identify a concrete supported CPython runtime (Python>=3.10), `math` extension,
   executable/shared Python and loaded libm/libc/loader; record bytes SHA256,
   ELF build IDs, compiler/build configuration and relevant binary relocations.
   Bind CPU feature/dispatch identity, the resolved cosine entry/body, binary64
   format, rounding mode and SSE/AVX rounding/control state. No runtime is chosen
   for favorable trajectory output; no source or trajectory is evaluated.
2. Inspect the actual math wrapper and resolved scalar cosine path. Prove that
   every represented input from exact Theta0 takes the analyzed branches,
   including range-reduction/table-index/rounding-cell behavior if used.
   Bind all executed constants/table entries and operations to the binary.
   Do not infer execution from a library version alone or substitute a source
   polynomial for a differently built/dispatched binary path.
3. Use exact rational arithmetic and rigorous outward RN/fused-operation bounds
   (whichever the concrete instructions actually use) to enclose the emitted
   output for the **entire** input set. Prove `7/8 <= c <= 1` from that bound.
   No cosine sampling, endpoint clearance, guessed ULP accuracy or assumed
   globally correctly rounded libm theorem supplies this link. A broad bound
   is acceptable if proved from the actual path, not an accuracy claim.
4. Connect it to the existing all-c conditional certificates and check the
   concrete execution's RN semantics for the repository arithmetic. Include
   source-code hashes, actual query/interpolation paths, native guard and every
   required geometric obligation. Preserve all original data and comparisons.
5. Record a narrowly scoped A result and the exact runtime/input/proof bindings.
   If a necessary binary identity, wrapper/dispatch link, instruction semantics,
   operation bound or geometric lemma is unavailable, mark that precise part
   **BLOCKED**. Do not use a library-name conjecture as proof or generalize to
   other runtimes/backends. Keep B as historical evidence and C as unproved.

Permitted work is implementation inspection and pure arithmetic only, with
**zero new motor/BEM/mapper/source or trajectory calls**. Any inspection/runtime
probe must not import/call the source solver. Binding a numerical environment
is not a new production implementation, executable fixture, selection record
or future-v2 seal. Unresolved proof remains BLOCKED, not sampled clearance.

## 5. Limits, affected sections and review/acceptance prerequisites

This changes only the prospective v2 dependency/capsule statements about actual
cos/sin and bundled source-success obligations, by this separately versioned v3.
All v2 geometric constructions/examples/thresholds/Q4 conjunction remain.
Affected dependencies are frozen PR-C11 partition policy and initial selection
record; PR-C13/16 evidence/provenance fields; PR-C15 Q3 proposal linkage; and
the Radau source/domain/ledger and continuous-audit dependencies. Those frozen
normative sections and historical acceptance records are not overwritten.

A PASS for one runtime is not alternate-runtime support, later dense-interval
clearance, C, candidate selection, implementation authorization or accepted
PR-C numerical evidence. Candidate29 stays NOT SELECTED even if A is proved.
Separate independent review/freeze and implementation authorization, all initial
selector predicates and any future actual callback/trajectory evidence remain
prerequisites. Later dense intervals still require their own complete audit;
interior crossing/tangency or unresolved ordering remains BLOCKED/INCONCLUSIVE.

Original v1 FAIL/four raw zeros, candidate/source/draft/seal hashes, captured
source evidence/observer failures, Q4 conjunction replay and timestamp amendment
remain unchanged. Main/base4cf ships RK45/v1; PR81/84 are untouched. No candidate30,
tuning, numerical threshold, production/test/workflow/ADR change, merge or freeze.
Independent numerical verification NOT ESTABLISHED; ADR-009 NOT CREATED /
NOT ACCEPTED; physical_qualification=false; PR-06C unresolved; GEOM/calibration/
experimental validation NONE.

## 6. Prospective declaration capsule

Declaration-time result: **NOT ASSESSED**. The complete declaration must be
committed and independently reviewed before concrete-runtime reassessment.
Digest rule: sorted compact ASCII JSON, UTF-8 without trailing newline.

Capsule SHA256 `a90af561107b3691655b32094cd1525f3fbc8de918d257786d512fedf85b5cf5`.

```json
{
  "Theta0_lower_fraction": "-1888948576541780995587/9444732965739290427392",
  "Theta0_upper_fraction": "-1888944609753935385085/9444732965739290427392",
  "candidate_manifest_sha256": "0b37fb45c005d7a046dee6541d1a89e4a0a5cead7434621718c90d191843b7a4",
  "captured_center_uncertainty": "unchanged stored uncertainty; no uniform sin theorem required",
  "captured_numeric_record_sha256": "183eb23a8bac8c4add42f76539f219c5726b36a613297d5bb7e4c83a331780c9",
  "code_base": "4cf0d0ea017fa824ba8d4a063ceddd015dae09d6",
  "future_v2_seal_authorized": false,
  "new_source_calls_authorized": false,
  "policy_id": "prc_c2v09_partition_geometry_scope_v3_proposed",
  "prior_documentation_head": "2a3167393a4000c2895cf349fa845dcf66a2f158",
  "prior_policy_id": "prc_c2v09_partition_provenance_neighborhood_v2_proposed",
  "runtime_certificate": "one concretely bound CPython/math/libm binary and dispatched cosine path only; unavailable identity/bound BLOCKED",
  "scope_A": "whole-Theta0 actual represented geometry/query/mapper ownership conditional on valid returned source object",
  "scope_B": "inherited successful initial-state source/preflight evidence; original v1 partition FAIL preserved",
  "scope_C": "every-angle BEM success/convergence and nongeometric transcendental source coverage not established or inherited from PR-C11",
  "selection_authorized": false,
  "status": "PROPOSED / NOT FROZEN / NOT IMPLEMENTED",
  "stored_S_theta0_binary64": "0x1.c2f8b88dfb80cp-23",
  "theta0_binary64": "-0x1.999999999999ap-3",
  "trajectories_authorized": false
}
```

## Subsequent concrete-runtime assessment (declaration preserved)

After independent declaration review at7718ea58a6286fa398b2295a5b60e417cb94b04e,
the [concrete-runtime certificate](cmm2_c2v09_partition_runtime_certificate.md)
proved the emitted-cosine enclosure and connected all-c geometric lemmas for
one pinned CPython/math/libm/CPU-dispatch/RN environment. A geometry is proved
conditional on a valid returned source object; B initial evidence is preserved;
C every-angle source success remains unproved and is not inferred as an inherited
PR-C11 requirement. Old v1 FAIL/v2 result and candidate29 NOT SELECTED remain.
No source calls, trajectories, selection, v2 seal, freeze or acceptance followed.
