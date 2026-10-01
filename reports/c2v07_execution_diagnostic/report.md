# C2V-07 execution-difference diagnostic

This report does not change the converter, the acceptance test, or the frozen fixtures. It does not explain the Python 3.10 pass/fail split.

## Preserved outcomes

| Event | Run | Checkout | Result on Python 3.10 |
| --- | --- | --- | --- |
| push | `36888456607` | `3fff759a75573e2c888d11ce99b372847568d957` | 1 failed, 1869 passed. `test_c2v07_presnap_observer_uses_the_cubic_contact` raised `CMM-2 contact time conversion is unresolved.` |
| pull_request | `36888462991` | merge checkout `31c0d4c0ebe37736fadd918e945dba705876d609` | 1870 passed |

The workflow head field for both runs is the PR source head `3fff759a75573e2c888d11ce99b372847568d957`. That is not the merge checkout. Both checkouts have tree `5f615822180f935b395b3cadd2ec2ad3979c08f0`. Python 3.11 passed both events. Both Python 3.10 jobs reported CPython 3.10.21, NumPy 2.2.6, and SciPy 1.15.3.

The failing cubic remains `reports/c2v07_representability/coefficient_replay_inputs.json`. The passing pull-request job did not record its accepted-interval coefficients.

## Local measurements

Host: Linux 6.12.94+, x86_64, 4 CPUs. CPython 3.12.3, NumPy 2.5.3, SciPy 1.18.1, SciPy OpenBLAS 0.3.34 (`USE64BITINT DYNAMIC_ARCH NO_AFFINITY Haswell MAX_THREADS=64`). CPython 3.10 is not installed here, so the CI 3.10 stack was not rerun.

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

Every locally captured call replayed to the same classification as the live call. No local call had the archived `t_old`, `y_old`, and `Q`.

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

## Unresolved

The coefficients from the passing pull-request Python 3.10 job were not captured, so this evidence cannot yet say whether that success and the push failure differed upstream or inside conversion. CPython 3.10.21 was not available for a fresh-process rerun. Thread settings were not recorded by the CI jobs. `OPENBLAS_NUM_THREADS=1` changed coefficients on this other stack and did not reproduce the failure; that is not a cause for the CI split.
