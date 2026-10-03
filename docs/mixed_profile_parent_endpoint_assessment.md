# Endpoint/model v1 — initial admissibility and readiness receipt

**PROPOSED / NOT FROZEN / NOT IMPLEMENTED.** This is endpoint/scalar assessment,
not a generated-parent or surface execution. Both endpoints are admitted under
the stronger graph conditions; implementation authorization and freeze readiness
are **NOT GRANTED**, with required endpoint permission/use-scope decisions unresolved.

## 1. Declaration committed before assessment

Immutable declaration commit:
`790d110734e0db5c1e09d3d9f4e9e8a0fe52061f`, tree
`1476a92fa5c11e6f183e6293e49d97b32e8d42dc`, parent
`1bbd9ccac876d5d612d2ac19e0cc16d492623e99` (reviewed PR #93).
The [declaration](mixed_profile_parent_endpoint_declaration.md) and
[manifest](declarations/mixed_profile_parent_endpoint_model_v1.json) were committed
before recording these results. They remain byte-identical to that commit.

| Content identity | SHA-256 |
| --- | --- |
| Declaration Markdown bytes | `7009fea028b06548fd7017ce6fcce457dde0fee4c65e96622334a84b1b1fe159` |
| Manifest JSON bytes | `007c7a9a437f4d5f86a5cd1c42109edb54ccd611a095736c5be211a3a9c3a83f` |
| Manifest sorted compact ASCII JSON | `92ece791b316da1b502d7a2aca6ccab579b6161d8b41c55faa1d0de75ac9ff08` |
| Input-identification observer script | `949126576c5939c211f14611bfc9cc80a41cea10a239d166cb29200c2f47e7ba` |
| Completed endpoint assessment observer script | `cc2d60ea1702be4eb5c042aeec5f1a1414b589920065448ac4af6c4ea645d834` |
| Private exact replay record | `1577e6247266e949cad650fcf5c9e15d71392937432fcc45f34770f0c0a6f490` |
| Supplemental bounded-input check record | `4c626c508fc820e07e6ffbd503cd2f94be28e3807508323e59252764446d2bdc` |

**Explicit API spelling erratum:** declaration §2's `format="selig"` denotes the
data-format label. The actual parser keyword is **`file_format="selig"`**, not
`format`. This receipt supplies that spelling correction; no selected bytes,
normalization expression, model choice or admission predicate changes. The
original declaration remains visible. Actual invocation was:

```python
parse_airfoil_coordinates(raw.decode("utf-8"), airfoil_id=endpoint["identity"],
                          source=endpoint["source_url"], file_format="selig")
validate_airfoil_definition(returned_definition)
```

No silent canonical repair was accepted: returned `.hex()` pairs were compared
with the precommitted normalized candidate, along with hashes and counts.

## 2. Independently checked endpoint admission

The existing parser/validator passed, and their canonical digests equalled the
declaration's normalized candidate digests. Raw and source-order numeric hashes
also matched. Parser sampled metrics were **not** used as the continuous proof.

| Check | UIUC E63 reference | UIUC NACA4412 reference substitute |
| --- | --- | --- |
| Input / returned points | 61 / 61 | 35 / 35 |
| Deduplicated, reversed or repaired | None | None |
| Shared LE source index, point | 33, exact `(0,0)` | 17, exact `(0,0)` |
| Upper / lower graph nodes | 34 / 28 | 18 / 18 |
| Exact graph support | Both `[0,1]` | Both `[0,1]` |
| Strict positive x steps checked | 60 | 34 |
| Union nodes / affine cells | 60 / 59 | 18 / 17 |
| Trailing-edge treatment | Retained closed cusp, exact gap 0 | Retained finite gap |
| Stronger admission | **PASS** | **PASS** |

NACA4412's exact TE gap is
`1498797955988901/576460752303423488`. It was not closed or extended.
The combined grid has **76 exact distinct x values**. Near values were not merged.

For E63 the minimum checked interior gap occurs at x
`2245468774137041/2251799813685248` and equals
`856944439756086661965770927/3169044057938084501740039700480`
(approximately `0.00027041102114359726`, normalized ordinate units).
For NACA4412 it occurs at x `4278419646001971/4503599627370496` and equals
`75170482100366421/4611686018427387904` (approximately `0.0163`).
These are exact rational signs from represented points and PWL interpolation,
not tolerance comparisons. Every branch-gap cell is affine and its endpoint
values are nonnegative, with strict interior separation. The LE zero and E63 TE
zero are explicit supported endpoints. This establishes whole-cell admission;
it is not merely a dense sample of an unspecified curve.

Actual canonical/normalized coordinate SHA-256 values:

- E63: `87e28637ac162d9deeb1dcb2ae90acae067c4b3081d100caddf1841947e3ecb1`.
- NACA4412: `139420a465db2e6ffdf55007795f454dd1345577a81cf2b8183eafb694595d74`.

No endpoint rejection occurred and no replacement was selected. This outcome
establishes only these exact assets under the declared normalization/graph model.
It does not identify APC12 coordinates or a manufacturer's actual 3D section.

## 3. Scalar replay and conditional reference proof

The complete 51×14 retained table hash and complete six-scalar hash reproduce the
declaration. Generated domain indices **10…50** contain 41 strictly ordered radial
knots. Finite scalar/input guards passed, including positive chord/tau and declared
r/beta/Y/Z limits. Source and endpoint byte/pair limits passed. The augmented
radial knot set (source domain, anchors and hinges) has **45 nodes**, within 68;
76 chordwise nodes are within 512. No generated section or output mesh was evaluated.
Future output/work/rounding conformance is not established by these input checks.

Both 101.6 mm and 127 mm hinge stations are **absent** from the manufacturer table.
No source row was synthesized. Rows 0…9 remain retained but outside the proposed
section domain, and the last row stays beyond the footer radius. The old reporting
partitions and missing-station diagnostics remain historical/source facts.

Model b `0x1.381d7dbf487fdp-3` exceeds the retained six-inch conversion
`0x1.381d7dbf487fcp-3` by exactly **`1/36028797018963968 m`**.
No anchor was moved. The pinned literal is the proposal's generated-model choice.

At x*=1/2 both exact endpoint gaps are positive. A uniform denominator bound for
the declared convex blend is the smaller endpoint value:

```text
d(r) >= 54665767083380196365581651241686711600501661
        /1660745550128878177071036978931594811775385600 > 0
```

This follows because the gap at x* is a convex combination and d is at least that
gap. Full branch positivity already follows from the endpoint affine-cell proof,
so this one proof query is not substituted for a whole-domain admission test.
The finite maximum over grid functions is continuous; scaling by positive
continuous tau/d preserves the declared reference's continuity and gives maximum
vertical reference thickness tau. Exact PWL endpoint signs bound all scalar cells.
Stored knot values are endpoints of those exact interpolants, so the copy fast path
matches the reference. Both children are restrictions of that one map.

These are conditional mathematical reference statements, not executed binary64
output, continuous surface/mesh validation, source equivalence or physical results.
The declared correct-rounding/error/resource policy still requires later
implementation and independent exact-head verification after authorization.

## 4. Actual execution provenance and retained observer failure

Initial checks used CPython **3.12.14**, Clang 22.1.3 build, Linux x86_64 with
glibc 2.39. The observed float mantissa width was 53 and `fegetround()` returned 0.

| Observed runtime/code | SHA-256 |
| --- | --- |
| Executed CPython binary | `fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7` |
| Loaded `/usr/lib/x86_64-linux-gnu/libm.so.6` | `f06f2ce1f1833df5f41cf13b6447ff07bea993ad9b27297d3428c2f70ab3f0e7` |
| `core/airfoil.py` | `3079f8cafe962556064efe74f7b9c22ceaae59bfaa5f063bb8a7ab1d2905b196` |
| `core/models.py` | `fec0b429c5201a7e7565205df756d00d344a5d5dd94703b7775d4b74ce17b853` |
| `core/apc_pe0.py` | `e256dae2fc525f4d5ab07a8ae46d394a5ca6351a7cbc9ddf3fdbd0ced1d7e6ca` |
| `application/apc_pe0_geometry_report.py` | `e9b4da0eab63bb3ea28645bdc5930fbc79ba640b6a57f304592fad803f066e32` |

`math` is built into this interpreter. The first receipt attempt incorrectly tried
to read `math.__file__` and failed with `AttributeError` before final serialization.
Its observer script hash was
`2fc3b7a710c04fad57a9a9b74d2e1806163f65b295df0b52c39dd9bc60682edb`.
That failed observer and error record remain private; no completed receipt was
silently replaced. Provenance capture was corrected to record the builtin origin
and actually loaded library; the same unchanged declaration/assets were replayed.
This is an observer error, not an endpoint rejection or a reason to alter fixtures.

These identities describe these parser/arithmetic observations, **not** a runtime
certificate, alternate-runtime clearance or CI proof of generated geometry.
Raw endpoints, complete APC/scalar records and full private replay arrays remain
outside public Git. Public files contain the declaration and bounded summaries.

## 5. Independent readiness review and remaining prerequisites

A separate automated reviewer independently reconstructed endpoint parsing and
exact branch/cell arithmetic from the raw assets, regenerated the 51×14 and
six-scalar identities, and inspected the pinned code and mathematical policy at
declaration HEAD `790d110734e0db5c1e09d3d9f4e9e8a0fe52061f`.
Verdict: **APPROVE FOR DECLARATION/ASSESSMENT PUBLICATION**, with the explicit
API spelling erratum above. Final assessment-head review/CI are separate closure
checks recorded in the Draft PR; a document cannot contain its own future SHA.

| Prerequisite | State and boundary |
| --- | --- |
| Exact endpoint byte/numeric/normalized/canonical identities | **ESTABLISHED** for the two declared assets. |
| Existing parser and stronger whole-graph admission | **ESTABLISHED**, independently reproduced. |
| Source table/scalar/code identities, domain and input limits | **ESTABLISHED** for this captured local source. |
| Anchors, law/grid, frame, thickness and zero-offset assumptions | **ESTABLISHED as explicit generated choices**, not manufacturer facts. |
| Continuous reference/thickness/child proof recipe | **ESTABLISHED conditionally** from the admitted inputs; no generator execution. |
| Per-file permission, attribution and intended endpoint use/distribution scope | **UNRESOLVED**; required decisions before claiming readiness. No vendoring permission inferred. |
| Implementation authorization / design freeze | **BLOCKED / NOT GRANTED** by this task and unresolved required permission decisions. |
| Executable correct-rounding, error/budget conformance and actual generated outputs | **UNRESOLVED / NOT IMPLEMENTED**; reserved for later authorized work, not proof supplied by this receipt. |
| Actual manufacturer blend/stacking/thickness equivalence | **UNRESOLVED**, outside the generated model's claim. |
| Actual joint differences, complete solid and as-built correspondence | **UNRESOLVED**; no hardware/material assumptions supplied. |

Next prerequisite is explicit resolution of endpoint rights/use scope and review
of the concrete generated assumptions/implementation authorization. Later bounded
implementation must independently verify its numerical/resource policy and
parent-child identity; those are later executable gates, not retroactive source
or physical evidence. No endpoint substitution or threshold fitting is proposed.

Neither PR #93 nor this stacked declaration is merged/frozen. External CAD/STEP
remains optional; the 13-inch case stays separate from the 250 mm baseline.
No proposed parent generator, surface/solid, BEM/FEA/trajectory, clearance, strength
or optimum-hinge assessment was run. PR #81/#84/#91 and C2V-09 remain untouched.
ADR-009 remains unaccepted; `physical_qualification=false`.
