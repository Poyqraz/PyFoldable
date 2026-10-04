<!-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0 -->
# Bounded generic mixed-profile section implementation

Implementation in a separate Draft PR, stacked on PR #94; no merge/freeze.
Reviewed design `a13d662cf3a118b7b3e0f949d87319c11d38397c`, separately reviewed
[clarification](mixed_profile_parent_implementation_clarification.md) technical
HEAD `28cc33b37e77ddd9913963137f3c381c40cf22f3`, closure/base
`30b285b2bfd016bc444d43dd553d07020e5751b3`. Main reference is
`6200b050809f7aca3ef3365608eea8cbfd80bd64`. The preserved declaration lineage
branches from PR #93 technical HEAD `1bbd9ccac876d5d612d2ac19e0cc16d492623e99`,
which is the actual merge-base with main. Its tree and the main merge tree are
identical (`136f451a3ace8ae011120c78174c99824508b42f`). The implementation PR targets
the exact clarification closure branch; reviewed history is not rebased to inject
the main merge commit. The generic software scope was explicitly
authorized; historical proposal/selected-model statuses remain unchanged.

## Local service and CLI

The [API declaration](mixed_profile_parent_generic_api_declaration.md) supplies
the exact request/report/codec/model contract. Public module:
`pyfoldable.application.mixed_profile_parent_geometry`; its immutable DTOs, decoder,
service and table renderer are local, synchronous and caller-input only. No catalog,
network, filesystem asset discovery, external CAD or solver is invoked by the service.

```bash
python -m pyfoldable.application.mixed_profile_parent_geometry request.json \
  --json outputs/report.json --table outputs/report.txt \
  --execution outputs/execution.json
```

Caller supplies a declared wire request, not a vendor filename/profile-name alias.
The CLI bounds the read before decoding; output paths are explicit trusted local
paths. Exit 0 is COMPLETE, 2 is a normal BLOCKED report. Decoder/internal exceptions
remain exceptions. Output directories must already exist. CLI/direct service
produce identical geometry-content bytes when given the same request. Execution
metadata has its own bytes/digest; code and loaded interpreter identities are
observations, not an alternate-runtime mathematical certificate.

## Arithmetic and scope

Exact represented PWL branches and scalars, smoothstep weight, camber/half-thickness
blend and continuous thickness maximum use one persistent rational budget. Whole
cell signs establish branch gaps; scalar-cell endpoint ranges and the common
interior denominator witness establish continuous model validity. The independent
strong graph helper is tested without relying on earlier core parser rejection.
All normalization/count/order changes are rejected, not repaired.

Placed coordinates use exact Taylor enclosures of ideal sin/cos propagated through
the complete placement expression. A whole enclosure must belong to the actual
nearest/ties-even cell. Refinement, retries and both reference-only cuts share the
budget. No libm accuracy hypothesis or sampled continuous proof is substituted.
Copied scalar knots retain their binary64 bits and negative zeros; new exact-zero
outputs use positive zero. Decimal rational serialization is bounded by the declared
integer bit limit without modifying global interpreter digit-limit controls.

Both children reference the same immutable parent and once-generated hinge sections.
Generated stations carry bracket indices and fresh identities; retained knots keep
their original indices. No twist reset, span rescaling or synthetic source row.

## Verification and evidence

The immutable [first-party manifest](declarations/mixed_profile_parent_synthetic_fixtures_v1.json)
is unchanged. S01, R01–R09 and R10/R11 budget-unit declarations are used as software
checks. Separate unit cases establish exact full support, affine gap rejection,
ties/subnormal cells, actual retry/child budget exhaustion, partial failures,
canonical DTO versus transport bytes, corrupted report rejection and CLI agreement.
An independent factorial/power oracle checks complete placement enclosures; it does
not use the production interpolation/trig/rounding helper as its expected result.

Initial RED was the missing service import. Three later RED witnesses rejected
rehashed invalid report status, endpoint-limit misclassification and rational
serialization above the interpreter's default decimal digit limit. Their fixes
preserve the declared model and limits. Exact tested HEAD, independent review,
generated content/certificate/work/provenance receipt and fresh CI are recorded in
the PR and later first-party execution receipt. Historical test counts remain history.

Selected E63/NACA4412/APC asset clearance remains UNRESOLVED; no selected-asset
download, bundling or realization occurs. S01 is not a manufacturer replacement.
No mesh/solid, BEM/FEA/trajectory, joint clearance/strength or optimum-hinge assessment.
The 13-inch and 250 mm scenarios stay distinct. Broader hinge/surface proposals
remain proposed; PR #81/#84/#91 and C2V-09 are untouched. No ADR-009 acceptance;
`physical_qualification=false`.

## 2026-10-04 first-party execution and independent review

Implemented code technical HEAD `a70134889603beec3f974a7536e1448269ff5c11`, tree
`a80768ba9478215553812cfeec0e9f419de36cd0`, was independently APPROVED FOR THE
BOUNDED FIRST-PARTY GENERIC GEOMETRY SLICE. This subsequent receipt commit has its
own HEAD and final review/CI coverage, recorded in Draft PR #95. It does not replace
reviewed design or clarification identities. PR #94 remains Draft/unmerged.

The committed [compact execution receipt](../reports/generic_mixed_profile_first_party_execution.json)
binds all actual input/content/parent/section/cut digests, exact source-file and
runtime observations, work counts and R01–R11 results. Its byte SHA-256 is
`b73f830ff1cff88dfbf19af361e7d57e42c42c061f52c1c8b8eee688ba37b7e5`;
canonical receipt SHA-256 is
`5d7522b3a96e2dd7b2a8ed76acab659960a544b6a7223978f2ae8088e8aaf07d`.
The full reproducible S01 JSON contains every rounding certificate; no clipped
excerpt is substituted for that actual output. Commands above use the unchanged
declared S01 request. Private vendor assets are not part of this run or receipt.

| Actual S01 observation | Result |
| --- | --- |
| Geometry content SHA-256 / actual byte length | `4384536470719379fc928d794533b528d7fd43388ed95490bb476303a2e1b2dd` / 1,925,127 |
| Parent manifest SHA-256 | `03e4db350bb26722f0895759aa4edef7dc32ba4858fa1b958201f2480899ab32` |
| Canonical input bytes / projected output bytes | 3,191 / 1,925,124; final bytes separately satisfy 16 MiB |
| Completed sections / coordinate points | 8 / 144 (432 coordinate components) |
| Rational operations / maximum intermediate bits | 25,439 / 19,702 |
| Maximum trig terms / retries | 80 / 0 |
| Local runtime | CPython 3.12.14, Clang 22.1.3, Linux x86_64/glibc 2.39; exact executable and called source identities in receipt |
| Execution sidecar SHA-256 | `cc017b08ca91b0ebc746431cce550350f72b0356b29e4f103f55a63598409951` |

The independent reviewer reconstructed all 432 coordinates using separate
Fraction interpolation/blending and 100-term factorial/power bounds, then checked
actual neighbor cells and complete-expression rounding ownership. Report content
reproduced byte-for-byte. This is bounded synthetic arithmetic evidence, not a
certificate for other runtimes, selected assets, a complete solid or physical safety.

R01/R02 fail SCALARS; R03 fails HASHES; R04/R05 fail REQUEST; R06 fails ENDPOINT_A;
R07/R08 fail ENDPOINT_B. R09 raises the declared duplicate-key decoder exception.
R10/R11 reproduce shared primitive exhaustion without reset. R07's actual earlier
core rejection is retained; separate direct graph regressions prove the stronger
support decisions. Fixture literal bytes and every input hash remain unchanged.

Review RED/GREEN also closed rehashed malformed sidecars, negative certificate
error bounds, coordinate/certificate disagreement and malformed normalization
proof metadata. A valid large escaped ASCII execution context was initially
rejected by an overly small byte bound; its RED witness is now GREEN under a
conservative bound derived from the declared 48 paths, 2,048 ASCII bytes per path
and six-byte JSON control escapes. No accepted input alphabet was narrowed.
Renderer schema/certificate checking owns a separate bounded report-audit
transaction, does not reset the recorded evaluator counter, and does not parse
source coordinates or evaluate parent geometry again.

Final focused checks: 31 passed. Affected airfoil/station/sparse generator/comparison/
license regressions: 137 passed on the local CPython 3.12 runtime. Compile/whitespace,
links, fixture/digest and immutable inherited-file checks pass. CI Python 3.10/3.11
results must cover the final publication HEAD, not this local runtime or an earlier
technical HEAD. The ordinary pull_request workflow filters to main, so the stacked
PR may have no PR-triggered run; exact-head cursor/** push CI is required instead.
Workflows remain unchanged. Final GitHub feedback is checked after successful CI.

No merge/freeze is performed. This is a separately authorized generic software
implementation, not accepted selected-model realization, complete parent surface,
CAD/mesh, clearance, strength, performance or optimum-hinge evidence.
