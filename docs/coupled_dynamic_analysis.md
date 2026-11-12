# Optional dynamic aero-mechanical route: DUST – MBDyn – preCICE

Status: implemented on branch `feature/dust-mbdyn-precice-coupling` (base PR #113 revision
`5d9a51754557bdb3b95037080938da8b7bf8054b`). Proposed, not independently reviewed.
`physical_qualification` is always `false`. Development record and run ledger:
[handoff](agent/handoffs/coupled-dust-mbdyn-precice-20261112.md).

The fully deployed BEM route is unchanged and remains the fast default. This route is
optional: without the external toolchain the research workspace shows an explanation
and every other workflow is unaffected.

## 1. What the user does

Research workspace (`apps/pyfoldable_research.py`) → **Tasarım**: choose a catalog
profile and template, dimensions and operating condition (unchanged) → **Analiz**: select
the stored polar version (the same admission as BEM) → section *Dinamik aero-mekanik
analiz*: enter distal-segment mass, CG, inertia, hinge spring/damping, stop law, initial
fold angle and latch-release time (or press *Gösterim varsayımlarını doldur* for
clearly labelled demonstration assumptions) → *Dinamik analizi başlat*. Progress is
polled; *Durdur* cancels. **Sonuçlar → Dinamik bağlaşık** shows status, metrics, hinge,
load, power, coverage/convergence and radial plots, a time-aligned 3-D playback and
downloads (result JSON, time-series CSV, radial CSV, ParaView VTK series). Records are
kept in the session and re-opened read-only from exported JSON (**Karşılaştırma /
kayıtlar**). Normal users never prepare CAD, polar files or solver decks.

## 2. Resolved toolchain (exact identities)

| Component | Identity | Why |
|---|---|---|
| DUST | `public.gitlab.polimi.it/DAER/dust` master `3b1d2e61f0b74a3c9fdde9c850951c73f8c6ad3e` (0.8.2-b), `WITH_PRECICE=YES`; also a `WITH_PRECICE=NO` build | Latest release line; `src/precice/mod_precice.f90` uses the **preCICE v2** Fortran API (`precicef_action_*`, `get_mesh_id`, `read_bvdata`) |
| preCICE | v2.5.0 source, sha256 `76ec6ee0…f796c00`, PETSc mapping off, Python actions off, MPI on | DUST issue #65: port to v3 not done; maintainers specify 2.5.0 + pyprecice 2.5.0.4 |
| pyprecice | 2.5.0.4 (Cython < 3, mpi4py 3.1.6, setuptools < 70 needed to build) | Matches preCICE 2.5.0 |
| MBDyn | `public.gitlab.polimi.it/DAER/mbdyn` develop `55c86cc6ec7ff8d69d31271c8f23220a43d996b6`, `--enable-python --with-lapack --disable-netcdf` | DUST `install.md` requires develop + Python (`mbc_py`); develop's NetCDF needs netcdf-cxx4 (absent, no sudo) — text output is used instead |
| CGNS | 4.3.0, sha256 `7709eb7d…a032` | DUST link dependency (tested 3.4/4.3) |
| Coupling venv | separate Python 3.10 venv: numpy 1.26.4, pyprecice 2.5.0.4, mpi4py 3.1.6, h5py 3.11.0, swig 4.2.1 (PyPI) | Keeps solver bindings out of the application venv |

Coupling route: **DUST's own route** — DUST links preCICE directly; MBDyn is driven
through its external-structural-force socket (`coupling, tight`) by a Python adapter
derived from DUST `utils/adapter/mbdynAdapter.py`. This is distinct from the preCICE
project's own MBDyn adapters. Build: `tools/coupled/build_toolchain.sh` (user space, no
sudo, `JOBS=2`; observed peak 1.6 GB RSS per MBDyn compile job, ~15 min total).
Manifest: `tools/coupled/write_manifest.py` → `~/.pyfoldable/coupled_toolchain.json` (or
`PYFOLDABLE_COUPLED_TOOLCHAIN`); readiness verifies versions and executable hashes.

Upstream check: DUST `tests/sym_test/coupled/ll` (coupled MBDyn-clamped wing) vs
`static/ll` (standalone): relative L2 differences 2e-10 … 1e-8 on wake/solution
datasets, 11/11 windows converged (the upstream script's nominal 1e-10 would not be met
by the wake datasets; recorded, not hidden).

## 3. Architecture

```
research_ui (Streamlit) ── coupled_ui ── application/coupled_analysis (prepare / start / poll / cancel / restore)
                                              │ same ResearchDesign + prepare_aero admission as BEM
                                              ▼
pyfoldable/coupled: model (case), c81 (tables), deck (DUST/MBDyn/preCICE text), toolchain
                                              │ run directory (fresh, outputs/coupled_runs/<id>)
                                              ▼
supervisor (detached process): dust_pre → MBDyn ∥ DUST ∥ adapter (process groups)
   timeout · cancel file · stop-all-on-failure · extract (coupling venv, h5py) · postprocess → result.json
```

No solver bindings are imported by the application process. Raw outputs, logs, partial
and failed runs stay in the run directory (git-ignored `outputs/`).

## 4. Frames, signs and coupling mathematics

* Global: shaft +Z; rotor angular velocity +Ω about +Z; free stream (0,0,−V); thrust +Z.
* Blade body frame = DUST parametric lifting-line frame: x chord LE→TE, y span, z lift
  normal; blade *b* is `Rz(2πb/N)`; LL line on the quarter chord, twist about it
  (same stacking as `visualization/propeller_25d.py`).
* Fold θ: rotation of the distal segment about the hinge axis (parallel to +Z) relative
  to the proximal segment; 0 open, negative folded back (trailing side), as in
  `docs/foldable_conventions.md`.
* Aerodynamic topology (`controls.aero_topology`):
  * **`continuous_rbf` (default since 2026-11-12):** one continuous DUST lifting line per
    blade (canonical stations only, `2 × elements_per_segment` elements), `coupling_type =
    rbf`, coupled to massless MBDyn nodes on a uniform spanwise grid of spacing
    `d = (r_last − r_first)/(2·elements_per_segment)` placed at `r_h + (k + ½)d`, so exactly
    one spacing straddles the hinge. Each node is dynamic (MBDyn's external structural
    force with accelerations rejects static nodes), has no body element and is fully
    constrained by a total joint to its segment's body node (100+b proximal, 200+b
    distal): it adds no mass and only carries exchanged loads. DUST (`mod_precice_rbf.f90`)
    moves every aerodynamic point with the inverse-distance weights of its two nearest
    nodes in the norm `√(dᵀ diag(10⁻³, 1, 10⁻³) d)`; points on one segment move rigidly
    with it, only the elements inside the straddling spacing blend the two motions, and
    the line has **no free vortices at the hinge**. Loads go to the nodes with the element
    centre weights: `F_j = Σ w dF`, `M_j = Σ w (dM + (c − x_j) × dF)`, `c` the moved
    quarter-chord centre (`mod_precice.f90`). PyFoldable re-implements this reduction
    independently for the closure checks and the hinge moment (sum over the distal nodes
    about the hinge point); radial rows are labelled proximal, distal or *junction*.
  * **`split_rigid` (records written before 2026-11-12):** one lifting line per segment,
    DUST rigid coupling to the body node (`c_ref = R0ᵀ(r − x0)`, `r = x + R(φ)c_ref`,
    `F = Σ dF`, `M = Σ (dM + (R c_ref) × dF)`), distal node on the hinge axis. The two
    components' free end vortices at the hinge cancel only when exactly coincident; see
    §9 for the spurious vortex pair this produces at any non-zero fold. Kept only so that
    earlier records restore with identical decks.
* `CouplingNodeOrientation = I` and each MBDyn node carries `Rz(θ)·Rz(ψ_b)`, so no offset
  or rotation is applied twice. MBDyn applies global force and moment with the node as
  pole (external structural element, no offsets). preCICE vertices are DUST-local
  coupling coordinates with a 10 mm per-blade offset along the hinge-axis direction
  (one-to-one nearest-neighbour mapping).
* Verified on actual runs: DUST result k ↔ window k+1 (DUST's time label lags by dt);
  independent reduction of DUST element loads about MBDyn's displaced nodes reproduces
  the exchanged node loads to 2e-8 N / 2e-9 N·m (converged windows); interface power
  `Σ(F·v + M·ω)` equals the element-load power to ~1e-5 relative.

## 5. Structural model and laws (minimum useful representation)

* Prescribed constant shaft speed: MBDyn `axial rotation` between ground and hub.
  Drive reaction torque is an **output**; torque-driven shaft dynamics are a different
  boundary condition and are not offered (no over-constraint of the same DOF).
* Per blade: rigid proximal body rigidly attached to the hub (`total joint`); rigid distal
  body on an ideal `revolute hinge` (axis ∥ shaft) at the declared hinge radius.
* Hinge law (`deformable hinge`, `double linear viscoelastic` on the hinge axis, verified
  in MBDyn source `constltp_impl.h`): spring `−k(θ−θr)`, viscous `−cθ̇`; beyond the open
  stop (θ > 0) or below the fold limit a unilateral linear spring–dashpot with
  stiffness `k_c` and dashpot `c_c` chosen from the declared restitution `e` for the
  hinge-axis inertia `J_h = J_cg + m c_g²`. The elastic force is continuous; the dashpot
  switches at the boundary (Kelvin–Voigt, can pull briefly at separation).
* Optional release latch: a `driven` total joint holds θ0 until `release_time_s`.
* Centrifugal, Coriolis and Euler effects are **not** added as loads; they arise from the
  distal body inertia. Aerodynamic loads only come from DUST.
* Mass/CG/inertia/spring/damping/stop values have explicit units; demonstration
  assumptions are labelled in every record. Dry friction and applied hinge torque are
  not supported in v1 (rejected/0). Proximal and hub masses are carriers of prescribed
  motion: they cannot affect hinge or aerodynamic response at constant speed.

Integrator: MBDyn `ms` with spectral radius 0.6 (differential and algebraic). A rigidly
spinning rotor shows a spurious drive/hinge torque that scales ≈ dt³ (aero-free locked
study: 1.22/0.15/0.019/0.0012 N·m at 10/5/2.5/1° with ρ∞=0; 0.019/0.0023/0.0003 N·m with
ρ∞=0.6). At 10° steps MBDyn's node velocity of the spinning rotor is ≈0.8 % too high and
the phase advances ≈0.4 % fast (large-rotation discretization), which raised coupled
loads by ~2 %; at 5° this is ~0.5 %. Steps ≤ 5° are required; 2.5° is used for contact.

## 6. Aerodynamic tables and coverage

* Source: the same `prepare_aero` admission as BEM (complete family, stored version,
  request digest). Cells are re-read from the admission and written to DUST C81 with
  `repr` floats: one block per Re (ascending), Cl/Cd/Cm vs α [deg] × Mach; Cm about the
  quarter chord (XFOIL), consistent with the quarter-chord lifting line. No point is
  added, removed, clamped or re-gridded; inert fixture records are rejected.
* DUST semantics (`src/io/mod_c81.f90`): bilinear in (α, Mach); **aborts** outside the α
  or Mach span; **linearly extrapolates** in Re. PyFoldable therefore audits every
  accepted window: per element α (final lifting-line iterate), Re = ρ v₂ c/μ,
  Mach = v₂/a against the admitted envelope. Any exceedance → `failed_aero_coverage`;
  only the prefix before the first exceedance is labelled valid. DUST `ll_stall_regularisation`
  is off, `ll_reynolds_corrections` off; no Reynolds floor, angle clamp or Mach = 0.
* The retained 800 mm grid (α −6…8°, Re 165k–330k, Mach 0.10–0.31) covers the fully
  deployed rotor and small folds. It does **not** cover spin-up from rest (α ≪ −6°) or
  large releases: the opening rate raises tip Mach above 0.31 (DUST abort) and Re above
  330k. Larger motions need new genuine provider data under a declared protocol or a
  distinct, documented aerodynamic model.

## 7. Coupling scheme, checkpoints, failure handling

* preCICE serial-implicit, MBDyn first, Aitken on Force and Moment; convergence on
  Position, Rotation, Velocity, AngularVelocity (absolute limits). A load-based measure
  was rejected after observing Aitken 0/0 → NaN when latched kinematics make two iterates
  identical; the load residual is audited instead (≤ 1e-3 relative, observed ~1e-5).
* Checkpoints: MBDyn `coupling, tight` reads loads at every residual assembly and does
  not commit the step until the adapter sends *converged*; DUST does not convect the
  wake, write output or update Γ/dynamic-stall history before convergence
  (`src/dust.f90`). The adapter sends the converged-iterate loads with the converged flag.
* preCICE v2 accepts a window at max-iterations; its iterations log `Convergence=0`
  turns the run into `failed_unconverged_coupling` with the valid prefix truncated.
* Supervisor: fresh run directory (stale `precice-run` aborts preCICE), process groups,
  wall-clock budget, cancel file, stop-all-on-first-failure, MBDyn's expected
  "interrupted" after the final window is recognised only when all windows finished.

## 8. Records and restoration

`pyfoldable_coupled_result` v1 contains the request (research inputs and draft,
template, root, admission summary with all admitted tables, C81 text, mechanics,
controls, deck manifest, participant-script hashes, toolchain identity), execution
status, accepted series, exchanged window loads/kinematics, MBDyn node states and joint
outputs, per-element radial table, checks and a raw-output manifest (sha256 per file).
`read_saved_coupled_result` re-derives without any solver: request digest, case from the
saved draft, C81 from the saved tables, every deck file, thrust/torque/hinge moments
from exchanged loads, θ/RPM from node states, the coverage verdict from element states,
and status consistency, and requires the saved coupling nodes and bodies to equal those
regenerated from the case. A saved request without `aero_topology` restores as
`split_rigid` (its declared legacy meaning, identical decks); any other missing control is
rejected. Node states keep the ground, hub and body nodes; the kinematics of the
continuous-line coupling nodes are in the exchanged window data. Preparation refuses a run
whose conservatively estimated record exceeds the 24 MiB restore limit
(`result_too_large`; e.g. the default continuous line allows ≈ 0.16 s at 2.5° steps, ≈ 0.3 s
at 5°). Checksums identify content; they do not prove physical validity.

## 9. Verification performed (actual executions; details and run ids in the handoff)

| Check | Result |
|---|---|
| Upstream coupled LL vs standalone | 2e-10 … 1e-8 rel. L2, 11/11 converged |
| Standalone DUST, open rotor 2400 RPM/14 m/s, last of 6 revs | NACA2412 38.67 N / 3.114 N·m (10°), 38.37 N / 3.073 N·m (5°), spanwise ×2: −0.8 % T; NACA0012 29.72 N / 2.354 N·m. BEM (retained): 43.65 N / 3.277 N·m and 33.42 N / 2.488 N·m. DUST ≈ −11 % T, −5 % Q for both profiles (method difference; not tuned) |
| MBDyn mechanics vs independent ODE | spring+centrifugal pendulum: 0.005–0.015° max error; stop restitution 0.515 vs ODE 0.510 vs declared 0.5 |
| Drive torque vs dH_z/dt (aero-free) | 0.005 N·m RMS after start transient (ρ∞=0.6) |
| Coupled locked open rotor 5° vs standalone 5°, `split_rigid` | +0.6 % T, +0.5 % Q; drive 3.0899 vs aero 3.0876 N·m |
| Same, `continuous_rbf` (6 revs) | 37.11 N / 3.012 N·m vs standalone continuous line 37.65 N / 3.039 N·m: −1.4 % T, −0.9 % Q (open item below); drive 3.0145 vs aero 3.0121 N·m |
| Topology, standalone (6 revs, 5°) | continuous line 37.65 N vs two segments 38.37 N (−1.9 %; the split layout also carries a 2 mm element next to the hinge) |
| Static −0.5° fold, latched, 5° (topology check) | `split_rigid` ≈ 47.7 N vs 38.7 N open (+23 %); `continuous_rbf` 37.17 N vs 37.25 N open (−0.2 %) |
| Release −5° at 0.05 s, 5°: last rev | `split_rigid` 42.75 N (rise from 37.9 N); `continuous_rbf` 37.05 N (flat), hinge history identical to 0.01° |
| RBF load reduction vs DUST node loads | force 2e-7…3e-6, moment 9e-7…3e-6 relative (closure checks of every continuous-line run) |
| Toolchain after Ubuntu security update (python3.10, libgfortran5) | `split_rigid` locked-open run repeated: all 432 windows bit-identical |
| Coupling tolerance 1e-6 vs 1e-8 (release case, 5°) | θ_max differs 6e-8°, final thrust 6e-6 N |
| Hinge balance (smooth windows) | 0.9–1.5 % relative residual |
| Main coupled case (NACA2412, −5° latched 0.05 s, 2.5°, 720 windows), `continuous_rbf` | completed; contact 3.65 ms after release at 38.8 rad/s, restitution 0.514 (declared 0.5), θ_max +0.81°, 7 contacts, second swing −2.70°, θ_final −0.53°; latched rev 36.37 N, last rev 36.76 N / 2.981 N·m (no rise); α −0.48…2.90°, Mach max 0.296; hinge balance 1.0 % |
| Same case, `split_rigid` (earlier record) | identical hinge history (contact 3.65 ms, 38.7 rad/s, 0.514, −2.70°); thrust 37.51 N latched → 42.63 N last rev; α −3.20…3.71° |
| Time step 5° vs 2.5° (release case) | opening converged (contact time 3.82 vs 3.65 ms, impact rate +0.3 %); rebound needs ≥ 8 steps/contact (restitution 0.61 vs 0.514) |
| −15° latched start | fail-closed: DUST α outside table at window 1 |

### Resolved: post-release thrust rise (spurious junction vortex)

Every `split_rigid` release run showed thrust rising ~10–15 % about 0.04 s after release
although the hinge had settled near −0.4°. Cause: the two lifting-line components of a
blade end at the hinge with free end vortices that cancel only when exactly coincident.
Evidence: only the 0.26–0.28 m radial bin of the wake differs between locked and released
runs; a −5° fold latched for the whole run stays steady (`…064218_36285ecfd1`), while a
*static* −0.5° fold raises thrust to ≈ 48 N from the first revolution (`…064948_aba91dea80`)
— a small gap between the end vortices leaves a vortex pair in the particle wake whose
counter-swirl raises inboard thrust. It is independent of time step, coupling tolerance
and vortex stretching; merging stations next to the hinge made it worse
(`…064957_1a28302b46`). Fix: the `continuous_rbf` topology (§4). With it the static −0.5°
fold changes thrust by −0.2 %, and the release cases stay flat (table above).

### Unresolved observations (not hidden)

* **Coupled continuous line vs standalone continuous line (−1.4 % T).** With the hinge
  locked open the `continuous_rbf` route gives 37.11 N against 37.65 N for the same DUST
  lifting line run standalone; per element the angle of attack is lower by 0.17° at the
  root, 0.09° at mid-span and 0.01° at the tip, persistent from ~20 steps on, while the
  sectional speed agrees to 0.1 % (the MBDyn kinematic error). DUST's rigid coupling
  agrees with its standalone counterpart to 0.02°, so the offset sits in DUST 3b1d2e61's
  rbf branch for lifting lines (e.g. its quarter-chord element centre/velocity handling
  around the wake update); it is not identified. Comparisons inside one topology (release
  vs locked, latched vs released) are unaffected; absolute levels carry this ≈ 1.4 % offset.
* **Grazing contact.** MBDyn's Newton iteration can cycle at a grazing contact of the
  piecewise penalty law (observed once at 5° steps without vortex stretching, step 299);
  the run fails closed with its accepted prefix. A smoothed contact law is a candidate
  improvement.

## 10. Supported cases and limitations

Supported: 800 mm research template (and other templates whose hinge lies inside the
station span, axis ∥ shaft), any catalog profile with a complete admitted stored
version (today NACA0012 and NACA2412), prescribed constant shaft speed, small releases
inside the admitted table envelope. Not supported / not claimed: spin-up from rest,
fully folded start, torque-driven shaft, dry friction, applied hinge torque, joint loss,
gap aerodynamics, CFD pressure fields, structural stress, fatigue, clevis–tang strength,
manufacturability, latching or seating beyond the declared penalty law, the 250 mm /
7100 RPM case (no admitted data), the four profiles without data. Contact phases need
≥ 8 steps per contact half-period (reported as a diagnostic).
