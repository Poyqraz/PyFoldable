# C2V-07 execution-difference diagnostic

This report does not change the converter, the acceptance test, or the frozen fixtures. The CI execution-variation investigation is closed as inconclusive. No further experiments are required for the timestamp-representability proposal.

The archived cubic’s representability obstruction under the current converter remains established. A passing run does not remove it.

## Latest exact-head CI

Head `272911b2c2533f3227874f62ca4c68bd32441cd6`.

| Event | Run | Python 3.10 | Python 3.11 |
| --- | --- | --- | --- |
| push | `36922057688` | fails C2V-07: 1 failed, 1870 passed, 9 skipped. CPython 3.10.21, NumPy 2.2.6, SciPy 1.15.3 | passes: 1871 passed, 9 skipped. CPython 3.11.16, NumPy 2.4.6, SciPy 1.17.1 |
| pull_request | `36922064664` | passes: 1871 passed, 9 skipped. CPython 3.10.21, NumPy 2.2.6, SciPy 1.15.3 | fails C2V-07: 1 failed, 1870 passed, 9 skipped. CPython 3.11.16, NumPy 2.4.6, SciPy 1.17.1 |

Both failures are only `test_c2v07_presnap_observer_uses_the_cubic_contact`. Both print the archived cubic and `CMM-2 contact time conversion is unresolved.`, including `t_old` `0x1.7f9db22d0e567p-1` and `h` `0x1.0624dd2f1aa00p-9`. The diagnostic test passed in those jobs. The cause of which job emits that cubic remains unknown.

## Historical outcomes

These earlier records stay as history. They are not replaced by the table above.

## Preserved outcomes

| Event | Run | Checkout | Result on Python 3.10 |
| --- | --- | --- | --- |
| push | `36888456607` | `3fff759a75573e2c888d11ce99b372847568d957` | 1 failed, 1869 passed. `test_c2v07_presnap_observer_uses_the_cubic_contact` raised `CMM-2 contact time conversion is unresolved.` |
| pull_request | `36888462991` | merge checkout `31c0d4c0ebe37736fadd918e945dba705876d609` | 1870 passed |

The workflow head field for both runs is the PR source head `3fff759a75573e2c888d11ce99b372847568d957`. That is not the merge checkout. Both checkouts have tree `5f615822180f935b395b3cadd2ec2ad3979c08f0`. Python 3.11 passed both events. Both Python 3.10 jobs reported CPython 3.10.21, NumPy 2.2.6, and SciPy 1.15.3.

The failing cubic remains `reports/c2v07_representability/coefficient_replay_inputs.json`. The passing pull-request job did not record its accepted-interval coefficients.

## Independently replayable committed evidence

These files are the raw records. `isolated_a.json` is byte-identical to the original `isolated-a` process capture, SHA-256 `a01a5e51cf4d2e5fbabd07dcb96ac99957e350baaee1ee312a3c067747ce86c9`. It supports that successful path and the archived-cubic replay stored inside it.

| File | SHA-256 | What it is |
| --- | --- | --- |
| `reports/c2v07_representability/coefficient_replay_inputs.json` | stored coefficient replay | Archived failing cubic. Not a rational proof. |
| `reports/c2v07_execution_diagnostic/isolated_a.json` | `a01a5e51cf4d2e5fbabd07dcb96ac99957e350baaee1ee312a3c067747ce86c9` | Successful 384-call capture, label `isolated-a`, with per-call replays. |
| `reports/c2v07_execution_diagnostic/captures/isolated_b.json` | `a0798a73db361fa6826a7014ce85ebd6cf41e6e24b980ccf19d1afaa6d6125b8` | Second fresh process. |
| `reports/c2v07_execution_diagnostic/captures/after_budget_test.json` | `ac9097e3e3ddedcc0a490a794887ffd2d54d54628c6648a2b4e5f4bd74890964` | Same-process capture after the budget test. Contact records only; it has no replay section. |
| `reports/c2v07_execution_diagnostic/captures/openblas_num_threads_1.json` | `1dce14bb545b94f5008741d72ef1eeb2c249dd10f1ce788a1113ae83d0ae09bc` | Only `OPENBLAS_NUM_THREADS=1`. |
| `reports/c2v07_execution_diagnostic/captures/openblas_omp_mkl_threads_1.json` | `385ce09c5a72366c10bd2b51844d4628c51ab64dfdda90707ea415a866713e01` | `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, and `MKL_NUM_THREADS` set to 1 together. |

`comparison.json` is a summary of those captures and of the CI rows. It is not an independent measurement.

## Local measurements

Host recorded in the captures: Linux 6.12.94+, x86_64, 4 CPUs. CPython 3.12.3, NumPy 2.5.3, SciPy 1.18.1, SciPy OpenBLAS 0.3.34 (`USE64BITINT DYNAMIC_ARCH NO_AFFINITY Haswell MAX_THREADS=64`). CPython 3.10 was not installed for those captures, so the CI 3.10 stack was not rerun. Those captures were copied from the original files; the experiments were not repeated for this closure.

Commands, from the repository root, with `PYTHONPATH` set to that root:

```text
python tests/dynamics/c2v07_execution_diagnostic.py --label isolated-a --out reports/c2v07_execution_diagnostic/isolated_a.json
python tests/dynamics/c2v07_execution_diagnostic.py --label isolated-b --out /tmp/c2v07diag/isolated-b.json
OPENBLAS_NUM_THREADS=1 python tests/dynamics/c2v07_execution_diagnostic.py --label openblas-1 --out /tmp/c2v07diag/openblas-1.json
```

The order check called `test_budget_plus_one_fails_before_the_aero_callback` and then the same capture in that process. Fixture digest `e73a1bc2fa2a0cfe27dfcfda7fcbb2ca3760921316c9a8e92bec9151acd37b17`.

Each fresh-process and same-process run completed: 384 contact-helper calls, 383 `no_contact`, 1 `contact`, 0 conversion failures. `isolated-b` and the after-budget run matched `isolated-a` on every captured input and event. Setting only `OPENBLAS_NUM_THREADS=1` changed `Q` on 287 calls and left every `t_old`, `h`, `start`, and `end` unchanged. The contact call, index 383, kept the same `y_old` and `Q`. Adding `OMP_NUM_THREADS=1` and `MKL_NUM_THREADS=1` on top of that OpenBLAS setting produced no further input difference. None of these runs reproduced the archived failure.

## Converter replay

The unchanged `first_radau_contact` classifies the archived cubic as `CMM-2 contact time conversion is unresolved.` A second replay returned the same string.

In the four captures that store replays, every call’s stored replay matches its live class, and the two archived-cubic replays match each other. `after_budget_test.json` has no replay section. No stored call in `isolated_a.json` has the archived `t_old`, `y_old`, and `Q`.

| Interval | start | end | t_old | h |
| --- | --- | --- | --- | --- |
| Archived failure | 0.7492500000000007 | 0.7512500000000008 | `0x1.7f9db22d0e567p-1` | `0x1.0624dd2f1aa00p-9` |
| Local contact | 0.7480000000000008 | 0.7500000000000008 | `0x1.7ef9db22d0e5dp-1` | `0x1.0624dd2f1aa00p-9` |

The step size matches. The accepted window does not. The difference between this successful execution and the archived failure is already present in the coefficients and step endpoints given to the converter.

## Supported conclusions

- On this 3.12 stack, equal captured inputs receive the same converter classification, including two replays of the archived failure.
- The archived failure is not the contact interval produced by the successful runs above.
- Two fresh processes and one same-process run after another test did not change those successful coefficients.
- One OpenBLAS thread changed other intervals' `Q` without moving the step grid, without changing the contact cubic, and without causing a conversion failure.

## Excluded by this evidence

- The two Python 3.10 CI results are not explained by NumPy 2.2.6 versus another NumPy, or SciPy 1.15.3 versus another SciPy: both jobs reported those versions.
- They are not explained by different source trees: the push checkout and the PR merge checkout share tree `5f615822`.
- A passing job does not erase the archived failure. Replaying that cubic still fails conversion here.
- Converter disagreement on that fixed cubic was not observed: both replays agreed.
- The local successful trajectory did not present that cubic to the converter.

## Closure

The cause of the CI execution variation remains unknown. The same archived cubic and conversion-unresolved certificate appeared on Python 3.10.21 / SciPy 1.15.3 and on Python 3.11.16 / SciPy 1.17.1, while other jobs with those same reported versions passed and did not record their accepted-interval coefficients. Passing runs do not remove the archived cubic’s representability obstruction under the current converter.

No further execution-variation experiments are required before a separately frozen and merged timestamp-representability amendment. This closure does not implement that amendment.
