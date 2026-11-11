# Research release candidate — one design, explicit numerical runs

## Start

Source-checkout release, Linux/POSIX (including compatible WSL2):

    python -m venv venv
    ./venv/bin/python -m pip install -e ".[ui,plot]"
    ./venv/bin/python -m streamlit run apps/pyfoldable_research.py

This is the normal research entry point. The older dashboard remains an archive/
advanced workspace, separate from this walkthrough. The wheel alone does not
contain all apps/configs/data. No merge of the stack into main is implied.

The app defaults to the bundled immutable numerical store under
data/research_reference/axial_800_store. No provider executable, credentials,
CAD, polar JSON, manifest or user-entered filesystem path is required.
An operator may set PYFOLDABLE_PROVIDER_STORE to a different store. An explicit
missing/corrupt override fails without fallback. The inherited store uses POSIX
filesystem APIs; native Windows operation is not claimed.

## Actual owner walkthrough

1. Select the800mm axial research template and NACA0012.
2. Inspect diameter800mm,hub90mm,declared physical root100mm,hinge270mm,
   proximal170mm/distal130mm,chord/twist table,2400RPM,14m/s inflow. The root
   is an explicit study declaration, not inferred from hub or first station.
3. Select the retained NACA0012 version. Check its alpha/Re/Mach domain and
   conditional initial-query hint. Selection/rerender launches no solver.
4. Click **Analizi çalıştır**. Inspect thrust,shaft torque/power,radial loads,
   alpha/Re/Mach,actual trial coverage and radial span. The retained execution
   produced33.421707752866034N,2.4880853705679464N·m,625.3240577344399W
   over144–388mm; all616queries were inside bounds.
5. Download the full result JSON and radial CSV. Change only profile to NACA2412,
   select its stored version and explicitly run. The retained second run produced
   43.647174413635845N,3.277371908165304N·m,823.6934007818944W;
   all690queries were covered, over the same radial span.
6. Select both saved records for comparison: distinct coordinates,shared parent
   planform/pose/conditions,executed BEM policy/implementation,provider policy/grid,
   observed executable hash,root and template are checked. This is equalRPM/inflow,
   not equal shaft power. No qualified winner is selected.
7. Export comparison JSON/CSV. Each run is individually recoverable through
   **Önceki uygulama sonucunu aç** using its downloaded result JSON. Restore is
   read-only, checks content/report/draft consistency and never runs a solver.
   Imported content is labelled; hashes establish consistency, not authenticity.

Design,mechanics,selected-version or retained-record changes invalidate the active
result/download. Saved JSON strings stay immutable. In-memory history is limited
to12results and session-scoped; durable recovery is export/import, not a new
database or hidden autosave. Provider records persist across restarts.

## Saved result correspondence

Restore reads retained content, without consulting the current store, rebuilding
with today's defaults or invoking a solver. It checks outer dimensions and
conditions against the retained draft; the root, template identity and annulus
count against the retained selection; derived geometry against that declared
pose and root; and successful/failed BEM records against their corresponding
request or attempted selection. Computed mechanism reports must correspond to
the retained mass/CG/inertia, drive, friction, stops and initial state. A
contradictory or malformed record is rejected before it can enter history.

New exports retain the template TOML to independently check chord and twist
scales. Older v1 exports did not retain those source bytes, so their scales
remain historical input declarations; the retained station geometry is checked
where repeated in the request. Their older geometry summary and optional
mechanism status are supported. Checksums identify content; they are not
authentication, solver replay or validation of the underlying measurements.

## Supported inputs and independent outputs

Six coordinate-bound profiles remain selectable:NACA0012,NACA2412,NACA23012,
NACA4415,NACA63-412,NACA4412. Switching changes actual coordinates while retaining
entered parent geometry and operating conditions.

Controls expose diameter,hub,physical root declaration,hinge,proximal/distal lengths,
blade count,chord/twist template/scales,fold preview,declared travel limit,
centerline stow target,RPM,inflow,rho,mu,T,p and4–80annuli.
Geometry/centerline outputs derive from the same design.

Aerodynamics is always fully deployed,zero-offset,positive-loading station-span
BEM. Moving the hinge alone leaves ideal BEM inputs unchanged when parent geometry
and conditions are unchanged. Fold preview is not sent to a folded aerodynamic
model. No joint loss is inferred.

The axial_800 template explicitly permits either length ordering. The separate
historical project_250 template retains **proximal longer**:
h−r_root>R−h,equivalently h>(R+r_root)/2. Shaft-origin h>R/2 is distinct.
The250mm root is not filled silently. Historical requirements/screens are preserved.
The declared physical root cannot be outboard of the first retained aerodynamic
station. Such a conflicting span blocks preparation; it is not trimmed or extrapolated.

Legacy centerline minima assume a hypothetical full−180°fold. Those fields are
labelled; the new result separately reports the envelope at the declared lower
travel limit. Neither is surface clearance or manufacturing qualification.

Optional mechanics require equivalent tip mass,CG offset,intrinsic CG inertia,
source,spring/rest/damping,initial state,linear RPM ramp,applied hinge moment and
friction law. Existing PY-05 binds these to the same design and stops at first
contact. No aerodynamic hinge load,shaft feedback,impact reaction,latch,FEA or
vibration qualification. Missing/invalid mechanics leave independent geometry and
aerodynamic results available.

## Acquisition and model scope

Existing source-bound data were inspected first: promoted200k/Mach0 NACA0012 has
only one Re/Mach point; historical250mm experiments remain incomplete.
Neither covers a varying rotor query domain and a second profile. The new case
does not repair or narrow those experiments.

Independent800mm reference:advance ratio14/(40·.8)=.4375,two blades,declared
70→44mm tapered chord,twist at each station atan2(14,Omega*r)+5degrees.
Linear station interpolation is retained. This is a moderate-Re attached-flow
research layout, not a measured rotor or optimized design. rho1.225kg/m³,
mu1.81e−5Pa·s,T288.15K are declarations. No3D applicability is established.

Per profile:Re165000,245000,330000;Mach.1,.31;angles−6,−4,−2,0,2,4,6,8°.
Ncrit9,XTR1/1,PANE,ITER160,cold isolated processes,ascending ALFA,one30s attempt
per cell. Mach ascending then Re ascending. Maximum12provider calls and two
explicit application BEM calls; all completed with96/96points,no retry.
Phase2 followed the successful first NACA0012 application result. No INIT,VACCEL,
panel changes,symmetry substitution or model fallback.

Canonical requests/scripts and full plan were frozen before launch.
For positive psi scanning,phi=(psi+psi0)/2 and W=W0*cos((psi−psi0)/2) bound the
scan through its first alpha≤−4°sample, conditional on independently checked
lift-sign conditions. That potential path fits the declared rectangle.
Actual trial queries, not this conditional guard or nominal stations, establish
executed coverage. Equations,bracketing,loss models and bounds="error" are unchanged.
No clamping,extrapolation,branch substitution or tolerance relaxation.

Provider:xfoil-subprocess adapter2,XFOIL6.99.
ExecutableSHA256:2b952bd21705d4d4147aa6b3e7db14f833a91dd9e1c9279261203f1cef1432ce.
Pinned preflight/source/build and OSMAP bytes verified; runtime shared-library
hashes,Python/dependencies/platform,streams,captures,preimages/scripts retained.
File hashes are not process-image attestation. No banner or qualification run.

The original MIT XFOIL6.99 xfoil_doc.txt (Viscous Formulation,Transition Criterion,
Numerical Accuracy sections) describes2D viscous/inviscid coupling,e^n transition
and limited separated-flow capability. Numerical completion does not establish
physical applicability or experimental agreement. The low-Re historical failures
remain evidence for those different states.

## Operator recovery and finite reproduction

Runtime uses provider_record_store.py and current provider_design_analysis.py
admission; no weaker cached approval. Bundled records reload without acquisition.
To reconstruct from the execution bundle, an operator may run:

    PYTHONPATH=. python examples/research_reference_data.py install --evidence /operator/extracted-evidence --profile NACA0012 --store /operator/new-store
    PYTHONPATH=. python examples/research_reference_data.py install --evidence /operator/extracted-evidence --profile NACA2412 --store /operator/new-store

Install only validates/registers retained bytes; no XFOIL/BEM calls. Paths are
operator examples, never normal UI fields. Freeze/capture are separate explicit
acquisition actions; do not invoke them just to start the app. Do not overwrite
old evidence directories. Failures before atomic manifest publication expose
no new version; an error after os.link may coexist with a readable complete
version. Failed directory fsync does not acknowledge durability.

Actual application execution revision:ff7c20f2bd0870cfbb8b2b17fe03a694f358d1f0,
tree4d6f0211601b4128f7ab607227711f5bb646adcf. Later archive/guard/UI hardening
does not change the BEM kernel,adapter or captured request.
The archive retains the execution checkpoint and original caller.
Moving the store changes path-bound preparation/request identity, not its content
version. Prepare freshly; no stale active reuse.

## Separate statuses

| Boundary | Status |
|---|---|
| Software | Single-screen no-upload route,persistent provider data,explicit modules,immutable export/import and comparison implemented |
| Genuine numerical execution | Two matched captured-provider/BEM reference runs observed; pending Astra-B review of this release |
| Other four profiles /250mm/7100RPM | Selectable geometry; no corresponding genuine numerical completion established |
| Reference agreement | NOT_ASSESSED; no matched measurements or independent solver agreement |
| Joint loss | NOT_MODELED; hinge alone does not modify ideal open BEM |
| Physical qualification | false |

No full CFD/FEA/vibration qualification is made a prerequisite to presenting
honestly scoped research predictions. A0 and MorphoCopter remain separate.
