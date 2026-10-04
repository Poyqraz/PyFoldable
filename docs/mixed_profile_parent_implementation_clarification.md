<!-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0 -->
# Generic geometry implementation clarification v1

**PROPOSED / NOT FROZEN.** Reviewed generic design HEAD:
`a13d662cf3a118b7b3e0f949d87319c11d38397c`; main/base:
`6200b050809f7aca3ef3365608eea8cbfd80bd64`. The coordinator has adopted the
generic caller-input scope and separately authorized its isolated implementation.
This addendum resolves two implementation details before implementation; its
review/closure HEADs are recorded separately in the PR. It does not rewrite the
[API declaration](mixed_profile_parent_generic_api_declaration.md), immutable
[fixture manifest](declarations/mixed_profile_parent_synthetic_fixtures_v1.json),
selected assets, historical assessment or their hashes.

## 1. Byte accounting

`BudgetV1.input_bytes` is exactly the length of canonical request-wire bytes
reconstructed from the structurally validated, finite owned request DTO using
`mpg_canonical_ascii_hex_v1`, including exact raw endpoint text. It is independent
of original transport whitespace/key order and execution metadata. If no valid
wire representation is available at a REQUEST failure, it is zero, not a claim
that an original transport was empty. A validated canonical request exceeding
2 MiB is rejected; a DTO cannot bypass that request-size bound.

The decoder still checks the original transport length against 2 MiB **before**
decoding or hashing. Neither canonicalization nor removal of transport whitespace
waives this bound. Endpoint raw-byte limits remain separate 256 KiB limits per
endpoint; their raw hashes include those exact bytes. Transport length is not a
report-content field or a component of the request identity. Unit regressions
must distinguish compact versus padded transports, direct DTO input, oversized
transport, oversized canonical DTO and endpoint limits.

## 2. R07 and independent support tests

R07 remains byte-for-byte unchanged, including every digest and expected stronger
predicate. Its permitted earlier core-parser `ENDPOINT_INVALID` rejection proves
only that rejection path. It cannot count as proof that both exact graph domains
are [0,1]. No stronger-predicate execution is reported when an earlier gate fails.

Separate exact-graph unit tests must exercise the actual stronger admission helper
independently of the core parser, with finite strictly ordered branch nodes:
one lower branch ending at 3/4 while the upper ends at 1 (reject incomplete support),
one branch beginning at 1/8 (reject missing LE support), complete branches [0,1]
(accept support), repeated branch x (reject strict order), and a nonpositive
interior affine gap (reject branch ordering). These are new first-party unit
identities, not edits/replacements of R07 or admitted selected assets. Whole-cell
sign and support certificates must use exact represented rational endpoints, not
parser PASS, samples, or tolerances. An independent oracle checks those decisions.

Generic software implementation/testing does not clear E63/NACA4412/APC use or
redistribution. Permissions remain UNRESOLVED. No freeze, merge, selected-model
realization, physical evidence or ADR-009 acceptance follows;
`physical_qualification=false`. PR #81/#84/#91 remain outside this task.

## 3. Reviewed clarification closure

Separate independent read-only review APPROVED technical clarification HEAD
`28cc33b37e77ddd9913963137f3c381c40cf22f3`, tree
`570da1161e9f5e63a34908195e6cca6b44ca5526`, parent reviewed design
`a13d662cf3a118b7b3e0f949d87319c11d38397c`. Fixture and all historical files were
independently reproduced/preserved. This later closure record is not that technical
HEAD. The separate stacked implementation remains subject to TDD, independent
numerical review and exact-head checks. No selected-asset permission or freeze follows.
