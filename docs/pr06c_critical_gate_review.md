# PR-06C critical-gate review and execution roadmap

## Decision

PR-06C is numerically mature but is **not physically qualified**. The implementation
now prevents a boolean or hand-edited metadata field from promoting a polar family,
records every polar query made during root finding, and supports an opt-in,
versioned rotational-lift ablation. The unchanged UIUC gates still fail, so PR-06D
physical qualification remains blocked. The PR-06D software foundation may proceed
only with that non-qualification encoded in its result and evidence contracts.

## What this review verified

| Contract | Result | Evidence |
| --- | --- | --- |
| Annulus and radial integration | Pass | Full test suite plus 80→160 annulus terminal-delta gate |
| Signed forward-flight branch | Pass | 50/50 propulsive benchmark points solve |
| Same spanwise schedule in benchmark and convergence | Pass | Both paths consume `SpanwisePolarSchedule` directly |
| Root-search polar provenance | Pass | Alpha/Re/Mach/source/clamp envelope includes scan and Brent queries, not only final roots |
| Representative-polar promotion | Fail closed | Exact coordinate hash, full provider identity, condition set, query count and reviewed two-capture promotion are mandatory |
| Real E63→APC12 polar coverage | Not available | No reviewed, promoted family covers the complete rotor query envelope |
| Frozen UIUC accuracy gates | Fail | Proxy and Snel screening results below |

The typed, content-derived evidence gate requires all of the following simultaneously:

1. exact E63 and APC12 coordinate source/SHA identities;
2. exact adapter, backend name and backend version identities;
3. complete provider-generated tables and required pointwise confidence;
4. the exact declared operating-condition ID set and final annulus count;
5. `bounds="error"`, zero clamped dimensions, and consumed sources that belong to
   the declared tables;
6. two capture manifests, a reproducibility comparison and an approved promotion
   record whose digest was predeclared by policy.

## Unchanged-policy benchmark

The bundled benchmark uses the approximate UIUC geometry and deliberately
non-representative analytic polar. These numbers are diagnostic and cannot promote
the model.

| Variant | Overall CT WMAPE | Overall CP WMAPE | Static CT / CP | Forward CT / CP | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| QPROP signed + tip loss + proxy | 26.40% | 28.28% | 11.39% / 11.26% | 40.31% / 38.35% | Fail |
| Same + Snel-1993 lift correction | 25.81% | 27.83% | 10.00% / 9.91% | 40.47% / 38.44% | Fail |

The Snel screen improves the static regime but does not improve forward flight. This
is useful negative evidence: a global 3-D lift correction applied to the proxy is not
the missing solution. It must not be tuned to the UIUC target.

The PE0 geometry screen from the prior stage remains the stronger geometry result:
overall CT/CP WMAPE 16.23%/16.98% and forward CT/CP WMAPE 25.68%/23.19%.
The manufacturer file is user-local and was not redistributed.

## Independent physics review

The review isolated the remaining error with unchanged inputs:

- disabling tip loss improves forward CT by about five percentage points but still
  fails and is not a physically acceptable production setting;
- a low-confidence NeuralFoil E63 screen improves CP but does not close forward CT;
- root-radius truncation has less than one percentage point effect;
- proxy zero-lift tuning can fit forward CT while badly damaging static CP, proving
  that target fitting would create a false pass;
- the remaining credible mechanism is the combination of qualified low-Re section
  behavior, rotational separation-delay/lift recovery, and a separately validated
  high-advance-ratio tip/wake model.

## Roadmap from here

| Order | Deliverable | Completion gate | Current state |
| ---: | --- | --- | --- |
| 1 | Representative polar evidence contract | Boolean cannot promote; full identity/query coverage and two-capture promotion required | Implemented |
| 2 | Rotational augmentation foundation | Published formula golden test, default exact no-op, domain failure and provenance | Implemented |
| 3 | User-local E63→APC12 family builder | SHA-pinned coordinates, PE0 thickness-aware sections, XFOIL 6.99 grids, explicit post-stall source | Next critical input |
| 4 | Real-family ablation | `2-D → 2-D+rotation → 2-D+rotation+wake`, no UIUC fitting | Pending step 3 |
| 5 | Tip/wake model review | Independent QPROP/XROTOR/CCBlade comparison at high advance ratio | Pending |
| 6 | PR-06C promotion | All overall/static/forward CT/CP, bias, coverage, convergence and evidence gates pass | Blocked |
| 7 | PR-06D software foundation | Exact fixed-limit plus non-qualifying opening-angle sensitivity | Implemented: 50/50 exact matches and complete 250-case, five-angle screen |
| 8 | PR-06D physical sensitivity | Qualified opening-angle loads and performance | Blocked by step 6 |

The next run must use caller-supplied, license-compatible E63 and APC PE0 inputs. If
any coverage, confidence, reproducibility, physics or accuracy gate fails, the result
remains a diagnostic artifact and PR-06D physical predictions stay non-qualifying.
The separate [fixed-limit evidence](../reports/pr06d_fixed_limit_equivalence.md) and
[opening screen](../reports/pr06d_opening_sensitivity.md) prove software compatibility
and sensitivity plumbing only; neither can promote PR-06C.

The final composite decision is now machine-enforced by
`examples/run_pr06c_physical_gate.py` and preserved in
`reports/pr06c_physical_gate.json`. It binds benchmark identity, the unchanged
policy, typed polar evidence/query coverage, and independent model-form review;
the current decision is `pr06c_blocked`.

## Primary references

- [Snel, Houwink and Bosschers rotational augmentation report](https://publicaties.ecn.nl/PdfFetch.aspx?nr=ECN-C--93-052)
- [XFOIL 6.99](https://web.mit.edu/drela/Public/web/xfoil/)
- [NeuralFoil](https://github.com/peterdsharpe/NeuralFoil)
- [APC engineering information](https://www.apcprop.com/technical-information/engineering/)
- [UIUC airfoil coordinate database](https://m-selig.ae.illinois.edu/ads/coord_database.html)
