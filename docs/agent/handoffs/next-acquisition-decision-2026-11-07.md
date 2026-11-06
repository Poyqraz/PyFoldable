# Astra-A → Astra-B: one next acquisition decision

Prepared 2026-11-07. **No execution is authorized or performed.** This is a separate
documentation revision stacked on #108, not a new provider implementation.

The owner relayed independent Astra-B **APPROVE** for #108's bounded store/app/UI
at `df9571542594c5f51206a4bce3cc5ff9bf107b63`, tree
`1773d9bb2146efda7b90a284654410779b09b9eb`, base
`8f2d38a826b6118ab97273dbd26ef6bbf43d23ae`. That exact implementation approval
is preserved; it does not approve this proposal or genuine numerical evidence.
#103–108, their dependency branches, main, scientific gates and historical evidence
are unchanged. The non-blocking publication clarification is in the
[store contract](../../provider_design_analysis.md#scoped-independent-approval-and-documentation-clarification--2026-11-07)
and appended original handoff. Only failures before the manifest's atomic
`os.link` guarantee no new version. A post-link error can coexist with a complete
readable **storage snapshot**, not an admitted polar family; failed directory
fsync acknowledges no crash durability. Runtime behavior is unchanged.

## Preferred decision: one cell, ITER 80 →160

Recommend only **`xfoil_cell00_iter160_control_v1`**: one new NACA0012 request at
Mach`0.040507164718475736`, Re`26030.624179244653`, with all 37 retained angles
in their exact descending order, +32° through−40°. Change only the provider Newton
iteration cap from 80 to 160; use common family scenario
`baseline_250mm_7100rpm_iter160_v1` for attribution. This is a new experiment,
not a retry/repair/continuation of the once-authorized experiment.

The [machine proposal](../../decisions/xfoil-cell00-iter160-v1/proposal.json),
[exact canonical preimage](../../decisions/xfoil-cell00-iter160-v1/request-preimage.json),
[reviewed-adapter script](../../decisions/xfoil-cell00-iter160-v1/script.txt) and
[checksums](../../decisions/xfoil-cell00-iter160-v1/SHA256SUMS) are prepared. The
[one-call operator recipe](../../decisions/xfoil-cell00-iter160-v1/operator-recipe.py.txt)
is retained as proposal text, not deployed application behavior.

| Identity | SHA-256 |
| --- | --- |
| Proposal bytes | `cbc78390576b9273db8ef5221f3cde4c664cc3df8e630c127718ba0773a2fc18` |
| Requested cell preimage/cache key | `bf1af202aeec9030456de270cfa3e8753bdb587e564843e076d61a6a824706b7` |
| XFOIL command script | `e8f9b71f806d08139139c64362e4befeb25d67400d11d75334ae5ece0ea92cc1` |
| Operator recipe bytes | `475fafd26551909a4ebd34ac32d97081999b6c9609991bdae0fb814d457bb78c` |
| New common provider policy | `e5879a01d671e50604537455ba0bd3a619d47e8bc2ff3eedac5a1779256925a4` |

Why this bounded control: the original cell returned 35/37; +32° and−38° remain
unavailable, and seven successor cells were NOT_LAUNCHED, with zero retries/BEM.
Archive SHA-256 remains
`e779bb00158571541a10419ecccb011fc1c8a5ea32cad40a59e005c59f9082e9`.
The retained script sets ITER 80. The raw−38° trace repeats the same visible residual
at iterations 76..80 before failure (`stdout.bin`, lines5105–5146, retained SHA
`841c9445758529ff1d81c70343e97da97f7d87f398ed9467afb6a7546cccbfc2`).
That stagnation makes the extra budget a **low-confidence hypothesis**, not a
promised remedy. Raw intermediate CL/CD text is not a usable polar row and is never
copied into the ledger; per-angle iterations/confidence there remain unavailable.

160 is a predeclared finite doubling, not a validated physical threshold or a new
default. Unlike blindly repeating eight cells, this spends at most one launch on
one changed numerical control at the known blocked corner, retains both missing
angles, and stops whatever happens. Removing +32° alone cannot address−38°.
It would also leave the retained upper angle at+30°, below the conditional
annulus0 initial alpha+30.65875° under bounds=`error`.
Same binary/build, paneling, cold initialization, order, Ncrit9, XTR1/1 and90s timeout
are retained to limit confounding. Runtime drift must be recorded and prevents an
ITER-only causal claim. No INIT, VACC override, warm-start seed, repeated ALFA,
angle deletion, coefficient replacement, fallback, or old-result stitching occurs.

## Exact baseline and the four different query concepts

Reuse #104's accepted [cause map](../../../reports/polar_query_feasibility/report.md)
at `8ba282e49ecf3c7ac96ada100c2721fa28a5803f`; read its retained JSON, do not call
`build_polar_query_feasibility` (that also runs synthetic BEM). JSON SHA-256:
`e741e8a37ba0e778e060799711a76b61d6a7c07e100f0eefaa1418abfbd7ed1f`.

| Bound input | Retained identity/value |
| --- | --- |
| Coordinates | Catalog NACA0012, SHA`ab62d56cc86a591da4f83c1980ea5b07743c4e47bdb0eb63a8e166e190a96d42`; exact coordinates in the preimage |
| Source template | `configs/designs/TIP_HINGED_250_CANONICAL.toml`, SHA`a3852e5d14f433528fa9ad63bae26dd076b5136eacf4a7860ef76971eec2afdc` |
| Shared parent geometry | SHA`9f28067fdd4a59b25da36d5d2e916e5804927232cd629c572e17880990644902`;250mm,2blades, hub18mm, retained hinge100mm, same global chord/twist/stations |
| NACA0012 draft | `d993635db17360f767cff4f26226b3f238de9cd3fb7657c8180247366f2b4d4f` |
| Condition | SHA`875469fb9e0b3383ec262bc31617be0707611c5e45e2e33a5588bad80a4392d1`;7100rpm, hover0m/s, density1.225kg/m³, viscosity1.81e−5Pa·s,288.15K,101325Pa |
| BEM policy | SHA`f5a59ab1b9d487e0fa8478558f66d0b54e55c2670097d33134acb8abc39da8ae`;40 station-span annuli,128 bracket samples,100 BEM iterations, bounds=`error`, positive_only, augmentation disabled; exact tolerances/loss flags in proposal |
| Root declaration | **Absent in the historical baseline.** Do not borrow20mm from inert tests or infer it from hub18mm/first station25mm. Future app preparation needs value/unit/meaning/declaration kind/source. |

Retaining the baseline hinge is not a new hinge/design selection. With an explicit
root, require `h-r_root > R-h`, equivalently`h > (R+r_root)/2`; the shaft-origin
comparison`h > R/2` is separate. No CAD upload is introduced. The APC13-inch
scenario is separate from this250mm baseline.

| Concept | What is known |
| --- | --- |
| Padded rectangle | Re endpoints26030.624179244653/88107.31488200535; Mach endpoints0.040507164718475736/0.2649894145852458;37 angles−40°..+32°. Corners/samples are not correlated annulus states. |
| Correlated potential image | Retained40annulus maps parameterized by psi; alpha/Re/Mach move together. Global alpha approximately−39.72917°..+30.65875°. This is a possible search image, not observed queries. |
| Conditional initial query | Annulus0: alpha0.5350961320458115rad, Re36812.86174948416, Mach0.05728578171528503; annulus39: alpha0.09199339599053441rad, Re51798.58930567484, Mach0.2649894145852458. Conditional on reaching the annulus. |
| Actual genuine solver queries | **Unavailable**: zero genuine BEM calls. Neither the padded request nor the old constant-coefficient trace supplies this history. |

## What unchanged admission and interpolation actually require

Inspect [application admission](../../../pyfoldable/application/provider_design_analysis.py)
`_prepare_provider_design_analysis`/`_capture`, [polar preparation](../../../pyfoldable/application/polar_upload.py)
`prepare_polar_run`/`run_polar_run`, [interpolation](../../../pyfoldable/core/polar.py)
`PolarFamily.query`/`_at_mach`/`_table_coefficients`, and [BEM](../../../pyfoldable/core/bem.py)
`solve_bem_annulus.evaluate`/bracket scan. Their byte hashes are in the proposal.

The application rechecks every declared cell, exact coordinates/request/provider,
common angle order/scenario/policy, raw input/script/receipt/header/point evidence,
and complete results before `to_polar_table(require_complete=True)`. It requires a
complete declared rectangular Mach×Re plan. The **chosen baseline family has four
cells**, declared before this gate; it must not be narrowed to the one success.
Admission can accept a separately declared complete1×1 rectangle in principle;
that is not proof of solver coverage. A Mach0.040507 singleton cannot supply the
conditional first Mach0.05728578 query with bounds=`error`.

Angle and Mach interpolate linearly; Re interpolates in log(Re). An interior query
can read four Mach/Re-corner tables, each needing alpha support at that query.
Sparse correlated samples cannot replace these tables under the current interface.
BEM first evaluates no induction, then scans psi until a bracket/root or failure;
the path depends on actual coefficients. `prepare_polar_run` explicitly retains
`solver_envelope_complete=false`. No changed bounds, BEM policy or admission rule
is needed to consume a complete new four-cell family; the requested provider160
policy is explicit and must be uniform across that new family. No old ITER 80
record is admitted as an ITER 160 cell. Complete table coverage still cannot promise
a bracketed/converged rotor solution.

## Provider/build, applicability and bounded outputs

Use the original retained executable SHA
`2b952bd21705d4d4147aa6b3e7db14f833a91dd9e1c9279261203f1cef1432ce`
and OSMAP SHA
`2f6b3c63461d71da9b6cb9ca1340d77cff0cfbe767679d15b5b8556b45d948c4`.
Source archive SHA
`5c0250643f52ce0e75d7338ae2504ce7907f2d49a30f921826717b8ac12ebe40`;
observed build GNU Fortran14.2.0/Debian14.2.0−19 with inherited
`-O2 -fdefault-real-8 -fallow-argument-mismatch`, no solver-source patch.
The [proposal](../../decisions/xfoil-cell00-iter160-v1/proposal.json) pins the
build-script/config-diff/log/library-record hashes from original preflight archive
`058a91997442d42df0859a373df1bbb00005fcd882c86616ef5707590f45331a`.
No new build or substitute binary is proposed. Current compatibility must be
rechecked before a future launch using static ELF/loader checks, not a banner.
Retain actual Python/dependencies/platform/library identities and command. File
hashes around calls are not process-image attestation.

Primary source: [Drela/Youngren XFOIL primer](https://web.mit.edu/drela/Public/web/xfoil/xfoil_doc.txt),
also read in the pinned archive as`Xfoil/xfoil_doc.txt`, SHA
`c36482e92f6cab424e965ccb48d0d81ebc030204ebf44a4205b366b9d7db3bea`.
Its viscous formulation treats limited separation; accuracy degrades near/past
stall. Its convergence advice explains the Newton iteration cap and sensitivity
to previous solutions. These support a bounded numerical control, **not physical
applicability of−40°/+32° at this low Re**. The under100000 VACCEL suggestion is
not an available reviewed adapter option (only repanel is supported), so no hidden
VACC/INIT modification is made. The current standalone NeuralFoil adapter rejects
nonzero Mach and its records have no accepted application admission adapter here.

If physical evidence at a separated state is required, the smallest defensible
alternative is independently resolved **section evidence at the same NACA0012
coordinates, Re26030.624179244653, Mach0.040507164718475736, alpha−38°**, retaining
Cl/Cd/Cm, unsteady averaging/convergence and uncertainty/source information. This
is an engineering inference from the model limitation, not an imported coefficient
or a claimed qualified replacement. No matching validated dataset/service is
established here. A separated-flow-capable numerical/experimental protocol and
its source-bound admission contract need separate review; arbitrary CFD, a rotor
curve, incompressible substitution or extrapolated coefficients are not drop-ins.
That contingency is **not an additional experiment recommended for execution now**.

The sole proposed launch runs the whole 37-ALFA script once, at most90s subprocess
time (not promised total wall time). It cannot stop at the first bad angle inside
that script. Then STOP unconditionally: no next cell, retry, INIT, point repair,
workflow or BEM. Preserve intent/outcome timestamps, exact invocation/runtime,
canonical attempted preimage, returned document/metadata, all seven available
capture files, provenance/checksums and exceptions. Missing outputs stay missing.
If process/evidence retention fails, preserve that attempted output; never rerun
in a fresh directory to obtain cleaner evidence.

Success requires exactly 37/37 usable finite coefficient triplets and all existing
raw capture/binding checks, not a claimed success/hash alone. The command below
uses those checks without family admission or BEM. Failure supports only failure
of this exact request/cap/order/build/environment; it does not prove impossibility
of other protocols, the correlated image, either profile or the project. Success
supports one complete attributable **new cell**, no physical qualification.

## Exact operator invocation for a later authorization

Do not run this recipe during documentation review. The old `launch_probe.py` and
`run_declared_probe` are tied to the old experiment/eight-cell contract and must
not be relabeled or reused. The linked Python recipe is a separate one-call operator invocation
using the existing provider API. Resolve `DECISION_DIR`, `PINNED_PACKAGE` and
`NEW_OUTPUT` to the actual prepared files/package and a new approved output path;
use the Python environment importing this source checkout. The source hashes and
prepared byte identities must match. Capture external stdout/stderr without
clobbering old evidence. No build, banner or solver call belongs in preflight.

```bash
( set -C
  status=0
  python "$DECISION_DIR/operator-recipe.py.txt" "$DECISION_DIR" "$PINNED_PACKAGE" "$NEW_OUTPUT" \
    "cbc78390576b9273db8ef5221f3cde4c664cc3df8e630c127718ba0773a2fc18" >"${NEW_OUTPUT}.launcher.stdout.bin" 2>"${NEW_OUTPUT}.launcher.stderr.bin" || status=$?
  printf '%s\n' "$status" >"${NEW_OUTPUT}.launcher.exit-status"
  exit "$status"
)
```

The recipe and shell command were not executed here; Python text was only parsed/compiled.
The recipe checks captured prelaunch AND postlaunch executable observations against
the pinned binary, not merely against each other. Retain the actual launcher exit
status, command/recipe hash, allowlisted loader/thread/Python environment and Python
executable file hash. These remain file/runtime observations, not process attestation. Before a later authorization retain/review the
exact recipe text and its hash, resolve paths, repeat static dependency checks and
compare actual runtime identities with the preserved 2026-11-06 runtime record.
A detected preflight hash/identity mismatch blocks before `generate`; no rebuild
or substitution. A mismatch observed in retained pre/post-call receipts fails that
attempted run after launch, without repetition; it cannot retroactively block launch.
A whole-package checksum list and durable execution archive are then retained by
the operator without overwriting the original archives. Failed/partial output
remains attributable even if final retention is incomplete.

## From this gate to a real application result

1. If this cell is complete, retain it under the **new four-cell plan**, not a
   singleton pretending to cover BEM. Other required cells (not authorized here):
   `(Mach0.040507164718475736, Re88107.31488200535)`,
   `(Mach0.2649894145852458, Re26030.624179244653)`,
   `(Mach0.2649894145852458, Re88107.31488200535)`; exact digests are in the proposal.
   They need separate acquisition authorization with the same160 policy/37angles
   and common scenario. No automatic continuation after this one-call experiment.
2. Operator registration can retain the incomplete observation with source-bound
   unlaunched slots. It does not admit a complete family. After all four complete
   source-bound results exist, publish a **new immutable store version** containing
   the entire declared family and execution/build provenance; use
   `caller_supplied_unqualified`, never inert or physically qualified labels.
3. Supply an explicit template/root declaration through the existing no-upload UI,
   select the exact stored version, and request fresh existing admission/preparation.
   Root missing or any record/policy/coverage failure blocks. Separately authorize
   the explicit genuine BEM action with the unchanged40annulus/default policy;
   keep failure totals null and retain the actual query envelope if returned.
4. Only after a genuine NACA0012 case is attributable, separately acquire the matched
   NACA2412 four-cell family under the same explicit root/template declaration
   identities, shared parent geometry/condition/provider/BEM policies
   and runtime controls. Its coordinate SHA is
   `3f84aba0f9234ed6e9fe4eedebe88ae8701a19ae181d70e21a02b0704916999a`;
   draft SHA`c3200882dbe6c1f0771bb89772ea8becb4ee143dc6929c4f9346fe55da4371ae`.
   Record source/runtime differences; then fresh admission and a separately
   authorized explicit BEM run. Preserve all five profiles; no substitution.
5. Existing [comparison export](../../../pyfoldable/application/profile_bem_comparison.py)
   `comparison_document` retains `BLOCKED_no_matching_real_provider_polar_bundle`;
   admission retains UNESTABLISHED. Even two matching genuine-origin snapshots do
   not automatically promote these hard-coded status gates. Independent evidence
   review and any separately authorized status-closure change remain required.

Comparison history is still session-scoped. Genuine single-case/two-profile
acceptance remains **UNESTABLISHED**; `physical_qualification=false`. No provider,
banner, BEM, qualification, CFD, FEA or transient study was launched by this task.
No scientific gate, runtime behavior, storage layer, UI or geometry selection changed.
Exact documentation HEAD/tree, command/link/identity checks, internal review and
ordinary exact-head CI are recorded in the separate Draft PR, not retroactively
attached to the approved implementation revision. Internal review is not Astra-B approval.

Preparation checks reproduced all canonical request/script/four-cell hashes,
unchanged source/BEM-policy/build/archive pins and130 relative path targets.
The recipe was parsed/compiled only; its isolated pure executable-receipt predicate
accepted an inert matching pair and rejected three mismatch controls. The whole
recipe and every provider/banner/BEM entry point remained unexecuted.
