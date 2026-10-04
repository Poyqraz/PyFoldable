<!-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0 -->
# Bounded generic mixed-profile section implementation

Implementation in a separate Draft PR, stacked on PR #94; no merge/freeze.
Reviewed design `a13d662cf3a118b7b3e0f949d87319c11d38397c`, separately reviewed
[clarification](mixed_profile_parent_implementation_clarification.md) technical
HEAD `28cc33b37e77ddd9913963137f3c381c40cf22f3`, closure/base
`30b285b2bfd016bc444d43dd553d07020e5751b3`. Main ancestry is
`6200b050809f7aca3ef3365608eea8cbfd80bd64`. The generic software scope was explicitly
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
