# Research release candidate — Astra-B review handoff

## Run and reproduce the owner journey

    python -m pip install -e ".[dev,plot,ui]"
    python -m streamlit run apps/pyfoldable_research.py

Use the800mm axial template,NACA0012,explicitly select its bundled version,click
Analizi çalıştır,inspect/export; switch only profile toNACA2412,select its version,
explicitly run,select the two saved results and export the matched comparison.
Full walkthrough/operator details: ../../research_application.md.
No normal-user CAD,polar JSON,manifest,path or solver executable input.
The source checkout bundles the actual immutable provider store; no acquisition
runs on app startup,selection or rerender. Explicit operator override never falls back.

Observed genuine numerical results from two actual AppTest-triggered Streamlit
actions (real configured disk loader,current admission,unmodified BEM,no seams):

| Profile | T [N] | Q [N·m] | Pshaft [W] | Radial span [m] | Actual polar queries |
|---|---:|---:|---:|---|---:|
| NACA0012 |33.421707752866034|2.4880853705679464|625.3240577344399|.144–.388|616|
| NACA2412 |43.647174413635845|3.277371908165304|823.6934007818944|.144–.388|690|

All actual query envelopes lie within the separately frozen grid. No clamps.
Forty radial elements retain local alpha/Re/Mach,loads and per-element envelopes.
SameRPM/inflow,not equal shaft power. No winner,reference agreement or physical
validation is inferred. Raw individual trial-query lists are not exported by the
existing kernel; per-element/global envelopes and counts plus strict error bounds
are retained. Do not invent unavailable per-query data.

## Stack and identities

Release is stacked on reviewed PR112:
d86ce3b2cd790ff37c8d5e806959352c86aa505d,
treeb2262a990f269dbb2bfdf000b982445201d77ca0.
Main022b466303c59b8c0adb02f935f9c2f065b0e2b5 and PR112 were verified live.
Prior PRs/integration bases/archives stay unchanged; no merge.

Executed local implementation checkpoint:
ff7c20f2bd0870cfbb8b2b17fe03a694f358d1f0,
tree4d6f0211601b4128f7ab607227711f5bb646adcf.
Final release adds guards,restore consistency,default bundled data,readiness and
scope labels without changing the kernel,adapter or captured requests.
Published commit/tree and exact-head CI are reported with delivery rather than
embedding a self-referential future commit here. Git-data publication can have
a different commit identity while preserving this exact tested tree.

Frozen planSHA256:
8505fa362136496d83340123a3f65045caffdcf94843e7e27d427a192090cab2.
Provider calls12,failures0,96/96usable points; genuine BEM calls2,failures0.
An AppTest wrapper initially used a relative app path and failed before any
engineering invocation; its log is retained,not represented as a failed BEM trial.
No retry,point repair or numerical fallback.

## Changes to inspect

- New research_design.py boundary binds one source template/current profile to
  geometry,existing retained-provider preparation/execution,optional existing
  PY-05 and sealed exports. research_ui.py is the coherent screen.
- New apps/pyfoldable_research.py default store is the bundled unqualified
  reference. The older dashboard is preserved as the advanced/archive workspace.
- ProviderDesignSelection adds explicit length_order_policy; legacy default is
  proximal_longer and its attempted-selection representation is preserved.
  The new research template permits either_order. Historical project250 remains
  proximal-longer,with no silently populated root. Hub/root/first station differ.
- DesignDraftInputs optionally declares travel limit/centerline stow target.
  Existing callers default unchanged. Fold preview is separate from open BEM.
- No BEM equation,bounds,branch,tip/root-loss or augmentation-policy change.
  Moving hinge alone cannot change ideal fully-deployed loads with fixed parent.
- Optional mass/CG/inertia/spring/friction/drive is explicit and source-bound.
  Missing/invalid mechanics does not erase independent aero/geometry.
  No aerodynamic hinge coupling,stop-reaction,contact/strength/vibration claim.
- Archive restore validates both success/failure draft linkage,report/request/
  snapshot checksums,nested provider shape and mechanism binding. It is read-only,
  not authentication. Imported records are labelled.
- Comparison requires distinct coordinates,matched geometry/conditions,executed
  policy and BEM implementation/runtime,provider settings/grid/build,root/template.
  It creates no qualified ranking. The legacy global scientific gate is not promoted.
- Session history is capped at12; durable user recovery is per-result JSON
  export/import. Provider records persist independently. No extra database/scheduler.

## Evidence/model declaration

The800mm/2400RPM/14m_s reference is a new declared research layout,not the unresolved
250mm/7100RPM schema example,the APC13in reference or330mm housing proposal.
Station span.36R–.97R; declared root100mm,hub90mm; chord70→44mm and twist
atan2(14,Omega*r)+5degrees at source stations. No measured/optimized design claim.

Grid per profile:Re165000/245000/330000,Mach.1/.31,alpha−6:2:+8degrees.
Same catalog coordinates and pinned807480-byte XFOIL6.99 executable,
SHA2562b952bd21705d4d4147aa6b3e7db14f833a91dd9e1c9279261203f1cef1432ce.
Natural transition Ncrit9,XTR1/1,PANE,ITER160,fresh isolated process per cell,
ascending ALFA,one30s attempt. Mach then Re ascending,firstNACA0012 thenNACA2412
only after first application success. Original binary/build/OSMAP/runtime records
verified and retained. Hashes around a call are not process-image attestation.

All six catalog geometries remain selectable; only two have this real numerical
reference data. Existing35/37negative fixture,missing+32/−38and sevenunlaunched
cells remain byte-identical/rejected. No old dataset is stitched or narrowed.

## Verification and remaining limits

Focused tests use isolated explicitly inert records/inert BEM seams; genuine
provider/BEM/banner entry points are blocked. Full ordinary suite and Streamlit
startup/root/health are separate checks; exact counts/CI are in delivery evidence.
No qualification/reproducibility workflow is dispatched.

Internal reviewer reproduced the observed load sums,QOmega,query-domain bounds and
fresh admissions without another engineering call; required import/phase2/stow
scope repairs were addressed. This is not Astra-B approval.

Software and observed genuine numerical milestones are separate from reference
agreement (NOT_ASSESSED),joint-loss modeling (NOT_MODELED) and physical_qualification=false.
BEM predictions need no full CFD/FEA qualification to be presented honestly.
The250mm baseline and four other profiles remain numerically unresolved.
A0 maintenance and MorphoCopter hypotheses are separate; no geometry selection,
new XFOIL diagnostic,CFD/FEA or merge is part of this release.
