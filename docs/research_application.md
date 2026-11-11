# Research release candidate — one design, explicit numerical runs

## Start

Source-checkout release, Linux/POSIX (including compatible WSL2). From the
checkout, reuse its existing Python environment:

    # If the working environment is already active:
    python -m streamlit run apps/pyfoldable_research.py

Otherwise call `./.venv/bin/python` or `./venv/bin/python` in place of
`python`, using the directory actually present. Stop the old Streamlit
process before restarting. For a first install only, create an environment
with `python -m venv .venv` and install `".[ui,plot]"` with its Python.

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

1. On **Tasarım**, select the 800 mm axial reference and NACA0012. The
   defaults are 90 mm hub radius, 100 mm declared physical root, 270 mm
   hinge position, 2400 RPM and 14 m/s inflow. The first aerodynamic
   station is at 144 mm. Plan, section and rotatable 3D views use the
   retained geometry at equal scales. WebGL is needed for the 3D view.
2. Choose **Açık çap ve menteşe** to enter diameter/hinge directly, or
   **Parça uzunlukları** to enter lengths. The latter derives
   `h = r_root + L_proximal` and `D = 2(h + L_distal)`. Changing entry
   mode starts from the last consistent geometry. The named 250 mm
   template still requires proximal longer; the 800 mm template allows
   either order. No root is inferred from the hub or station.
3. Open **Analiz**. The sole matching version may be preselected when
   current admission and the conditional initial-query check pass.
   When several versions are available, choose explicitly. A removed or
   rejected selection is not replaced. Missing data, an unselected
   version, an out-of-grid initial query and an admission rejection
   have separate messages. None triggers BEM or creates a failed
   attempt. The initial check cannot predict convergence or trial coverage.
4. Click **BEM’i çalıştır**. The selected record is freshly loaded and
   admitted before one explicit BEM call; there is no provider launch.
   **Sonuçlar** shows thrust, shaft torque/power, the executed conditions
   and station span. Inspect element totals, loads per radius, or α/Re/Mach
   and their table. The original retained 800 mm runs produced
   33.421707752866034 N / 2.4880853705679464 N·m / 625.3240577344399 W
   (NACA0012) and 43.647174413635845 N / 3.277371908165304 N·m /
   823.6934007818944 W (NACA2412). Both modeled 144–388 mm and covered
   616 and 690 trial queries respectively.
5. Download the result JSON for durable recovery and radial CSV for
   further analysis. Return to **Tasarım**, change only profile, then
   explicitly run NACA2412 in **Analiz**. The current design and entered
   controls persist during navigation. Changes invalidate the active result;
   saved records retain their original attribution.
6. On **Karşılaştırma / kayıtlar**, choose two successful BEM records.
   Different coordinate identities and matched declared inputs, polars and
   BEM policy are checked. This pair is at equal RPM and inflow, with
   different shaft powers. Comparison JSON/CSV retains full precision.
   There is no qualified winner. Failed attempts remain inspectable
   separately and never enter the comparison picker.
7. Use **Kaydı Sonuçlar’da aç** to inspect one archive record in the same
   results view. **Önceki sonuç JSON’unu aç** restores a downloaded result
   without solver calls. The 12-record session history is temporary;
   the JSON download is the durable record. The polar store survives restart.

The optional **Mekanizma** controls in Analiz remain off until opened. After
explicit valid declarations, **Mekanizmayı çalıştır** executes only the
bound PY-05 model, even if BEM is unavailable. A mechanics-only record has
no aerodynamic request or totals and is excluded from BEM comparison.
The fold preview is also the optional mechanism initial angle; it does not
change BEM's fully deployed pose.

## Saved result correspondence

Restore reads retained content, without consulting the current store, rebuilding
with today's defaults or invoking a solver. It checks outer dimensions and
conditions against the retained draft; the root, template identity and annulus
count against the retained selection; derived geometry against that declared
pose and root; and prepared and executed requests against each other and their
retained polar data. Failed BEM records remain bound to the attempted selection.

For saved schema v1 with a BEM v5 report, restore checks the ordered midpoint
annuli and station interpolation, convergence and retained policy, finite
outputs, and the ordered element/rotor query envelopes. Each final query must
be in its element envelope and retained polar domain. A pure lookup checks its
polar values and source fields. The rotor envelope must combine the element
envelopes. Differential loads must match the solver's force projection from
the retained section state and its verified effective lift and drag
coefficients. They must give the recorded annular loads after multiplying by
width; the loads must sum to the recorded totals, and shaft power must equal
torque times the executed shaft speed.

Computed PY-05 v2 reports must match the retained mass/CG/inertia, drive,
friction, stops and initial pose. For every sample, the retained drive sets
RPM, shaft speed, its segment derivative and applied hinge torque. An ordinary
internal knot uses the outgoing segment; terminal first contact uses the
segment that reached the stop, including contact at that segment's end knot.
The same instantaneous model checks hinge torque terms, acceleration, energy
and powers from the retained angle and velocity. The report's cumulative
trapezoidal rule over retained sample times and checked powers gives work and
dissipated energy. Completed histories reach the declared end; a stop-contact
history ends at its recorded stop and time. A contradictory or malformed file
is left unchanged and rejected before it can enter history or comparison.

Repeated arithmetic allows four ULPs (units in the last place), including
conversion through the draft's display units. The time-step check uses four
ULPs at timestamp scale because it subtracts recorded times. Polar coefficients
allow 32 ULPs at unit scale or the coefficient magnitude, whichever is larger,
to cover rounding in log-Reynolds interpolation and blends near zero. Domain
bounds stay strict. These allowances concern stored floating-point arithmetic;
they are neither solver acceptance thresholds nor physical uncertainty.

New exports retain the template TOML to independently check chord and twist
scales. Older v1 exports did not retain those source bytes, so their scales
remain historical input declarations; the retained station geometry is checked
where repeated in the request. Their older geometry summary and optional
mechanism status are supported. Checksums identify content, not its author or
origin. The saved envelopes summarize trial queries without retaining their
sequence. Restore does not recreate that sequence, integrate the mechanism,
or validate the underlying measurements.

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
