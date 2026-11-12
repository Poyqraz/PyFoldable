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

* Prescribed shaft speed (constant, or a smooth ramp, §13): MBDyn `axial rotation` between ground and hub.
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
* A second NACA2412 family (`research_axial_800_deploy_xfoil_v3`, version `2026-11-12-deploy-v3`)
  widens the same attached-flow angle grid to Re 100k–400k and Mach 0.07–0.36 (separately built
  XFOIL 6.99; §13 and `reports/coupled_deploy_polars_20261112/`). With two versions of one
  profile the application no longer auto-selects; the user picks the version. It does not
  extend α, so spin-up from rest is still outside every admitted table.

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
continuous-line coupling nodes are in the exchanged window data. Checksums identify content;
they do not prove physical validity.

**Storage bound vs simulated duration.** The record keeps every accepted window (no thinning),
so its size grows linearly with the number of windows. The canonical record is bounded at
24 MiB because restoration parses and re-verifies the whole record and the session keeps it
(measured: a 16.6 MB record restores in 2 s at 215 MB peak RSS). This is a storage bound,
not a physical one, and it is stated before a run: preparation reports the planned
revolutions (total and after release), the estimated record size and the longest supported
duration for the chosen step and discretization (`supported_duration`; default continuous
line: 0.319 s / 12.8 revolutions at 5°, ≈ 0.16 s at 2.5°), and refuses a longer run with
`result_too_large` naming that limit.

*Transport and upload.* Exports are lossless encodings of the same canonical JSON: `.json`,
`.json.gz` (gzip, immediate, ≈ 3×) and `.json.xz` (xz preset 6, CRC64, ≈ 3.6×, prepared only on
request because encoding takes seconds). Import accepts all three and inflates with bounds
(≤ 12 MiB compressed, ≤ 24 MiB inflated, one complete stream with its integrity check, no
trailing data, xz decoder memory ≤ 16 MiB) before the unchanged verification. Streamlit's upload
endpoint caps every request at `server.maxUploadSize` (5 MB = 5 MiB in this repository's
`.streamlit/config.toml`; on 1.40 the Tornado server applies it to the whole multipart body,
so the "uploadable" verdict keeps a 64 KiB margin); a per-widget `max_upload_size`
(Streamlit ≥ 1.53) changes only the browser-side check and could not raise that cap — an
earlier 26 MB uploader setting was therefore misleading (an actual browser upload of the
5.64 MB main `.json.gz` returned HTTP 413) and has been removed. The uploader and the export
state the limit in force. Measured on the main record: `.json.gz` 5,641,917 bytes (refused),
`.json.xz` 4,603,084 bytes (uploads and restores to the identical `result_sha256`). Records
whose `.json.xz` exceeds the limit (roughly above 18 MB of JSON) open from the local run folder;
raising the server-wide limit would change every uploader's bound and is left to the owner.
Version facts: per-widget `max_upload_size` from Streamlit 1.53.0; `AppTest.file_uploader`
(used by this repository's upload UI tests since before this route) from 1.56.0, so the full UI
test suite needs ≥ 1.56 while the coupled route and its tests run on the declared floor 1.40.
Result views label the history as a short analysis window (revolutions in total
and after release) and show last-full-revolution means instead of last-window values. Runs
longer than the bound (e.g. tens of revolutions at 2.5°) would need chunked histories with
lazy views; that is a stated limitation, not implemented. Resource note: the session keeps up
to 12 records as canonical JSON and re-parses them on each render, so several large imported
records raise memory use and page latency. The import peek rejects inputs above the research
reader's limit unless they start with the canonical coupled header, so nothing larger than a
research record is fully parsed before the coupled reader's own bounds.

## 9. Verification performed (actual executions; details and run ids in the handoff)

| Check | Result |
|---|---|
| Upstream coupled LL vs standalone | 2e-10 … 1e-8 rel. L2, 11/11 converged |
| Standalone DUST, open rotor 2400 RPM/14 m/s, last of 6 revs, two-line layout (historical) | NACA2412 38.67 N / 3.114 N·m (10°), 38.37 N / 3.073 N·m (5°), spanwise ×2: −0.8 % T; NACA0012 29.72 N / 2.354 N·m. The earlier "DUST ≈ −11 % T vs BEM" figure belongs to this layout; the current comparison is in §11 |
| MBDyn mechanics vs independent ODE | spring+centrifugal pendulum: 0.005–0.015° max error; stop restitution 0.515 vs ODE 0.510 vs declared 0.5 |
| Drive torque vs dH_z/dt (aero-free) | 0.005 N·m RMS after start transient (ρ∞=0.6) |
| Coupled locked open rotor 5° vs standalone 5°, `split_rigid` | +0.6 % T, +0.5 % Q; drive 3.0899 vs aero 3.0876 N·m |
| Same, `continuous_rbf` (6 revs) | 37.11 N / 3.012 N·m vs standalone continuous line 37.65 N / 3.039 N·m: −1.4 % T, −0.9 % Q (located below); drive 3.0145 vs aero 3.0121 N·m |
| Coupled geometry and timing (`continuous_rbf`) | DUST's written lifting line at every result is a rigid rotation of the standalone geometry (residual ≤ 2.4e-16 m); its azimuth equals MBDyn's state at window k+1 (alignment rule of §8 confirmed); during fold motion (θ −5…+0.77°, 120 windows) DUST's written points equal the RBF reconstruction from exchanged node states to 1.1e-16 m; nodes stay on their rigid segments to 2.7e-8 m |
| RBF node spacing ×0.5 / ×2 (aero discretization fixed; release −5° at 0.01 s, 2.5°, 259 windows; diagnostic driver override, records intentionally do not restore) | max Δθ 0.0015° / 0.011°, max Δthrust 0.019 / 0.018 N, max Δ hinge aero moment 0.0008 / 0.005 N·m (peak 0.54 N·m), last-revolution thrust ±0.002 %, identical first contact |
| MBDyn node speed vs Ωr (rigid windows) | +0.113 % at 5°, +0.0283 % at 2.5° (∝ step²); exchanged angular velocity exact (1e-14); integrated azimuth leads Ωt by 0.0019°/step at 5° |
| Topology, standalone (6 revs, 5°) | continuous line 37.65 N vs two segments 38.37 N (−1.9 %; the split layout also carries a 2 mm element next to the hinge) |
| Static −0.5° fold, latched, 5° (topology check) | `split_rigid` ≈ 47.7 N vs 38.7 N open (+23 %); `continuous_rbf` 37.17 N vs 37.25 N open (−0.2 %) |
| Release −5° at 0.05 s, 5°: last rev | `split_rigid` 42.75 N (rise from 37.9 N); `continuous_rbf` 37.05 N (flat), hinge history identical to 0.01° |
| RBF load reduction vs DUST node loads | force 2e-7…3e-6, moment 9e-7…3e-6 relative (closure checks of every continuous-line run) |
| Toolchain after Ubuntu security update (python3.10, libgfortran5) | the one repeated case (`split_rigid` locked open, 432 windows, `…004422` before vs `…070700` after): the adapter window log (all exchanged loads and kinematics), MBDyn's .mov/.jnt/.out and the DUST extraction are byte-identical; the HDF5 result files differ only byte-wise (file metadata; extracted data identical); the preCICE configuration differs by an XML comment; record digests and derived checks differ because the request records the toolchain identity and later controls and post-processing changed between the runs (review package `toolchain/replay_comparison.json`). This is evidence for that case, not proof that every result is invariant to the update. Each run is bound to the manifest it ran with (`toolchain/run_environment_binding.json`). Exception: the standalone topology row above compares the two-line run (before the update) with the continuous-line run (after); its −1.9 % carries the unquantified update effect. All RBF-gap and coupled comparisons use one environment |
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

### Located: coupled continuous line vs standalone (−1.4 % T, locked open, 5°)

Diagnostic budget fixed in advance: existing outputs plus one diagnostic standalone DUST build
and run, three coupled spacing runs. Raw evidence, scripts and the diagnostic patch are in
`reports/coupled_closure_20261112/` (see its README). Findings, in the order they were checked:

1. *Generated geometry* — identical: the two DUST inputs differ only in the coupling lines;
   all 63 preprocessed geometry datasets match; the coupled line at every step is a rigid
   rotation of the standalone line (≤ 2.4e-16 m). Section frames reconstructed from the
   written geometry reproduce DUST's own projected velocity exactly (|up·b| ≈ 1e-16).
2. *Adapter transformations and timing* — exact: positions sent equal MBDyn's states; DUST's
   written geometry equals MBDyn's state of the aligned window; the one-step label lag is the
   documented alignment rule.
3. *Evaluation-point velocities* — the only input difference. In DUST 3b1d2e61 the lifting-line
   angle of attack uses the element body velocity `ub`. Standalone DUST evaluates it at the
   control point (`ctr_pt`, half a chord behind the leading line); rigid coupling at the vertex
   mean (same point); the `rbf` branch (`mod_precice.f90`, element-centre block) at `loc_cen`,
   the leading-line midpoint. Observed: the spanwise velocity component changes by exactly
   Ω×(chord offset) (−7.824 m/s predicted and observed at the root element); the rigid-coupled
   pair keeps the standalone value (7.604 vs 7.609 m/s).
4. *Positive reproduction* — a standalone DUST build whose only change evaluates lifting-line
   `ub` at the leading-line midpoint (`dust-ubcen.diagnostic.patch`; never used for production)
   run on byte-identical inputs gives 36.972 N / 3.0025 N·m (stock 37.646 N / 3.0387 N·m,
   −1.79 %); coupled rbf 37.112 N / 3.0121 N·m. Per element, the α gap to the coupled run falls
   from 0.007…0.22° (stock) to 0.003…0.013° (diagnostic), and the spanwise velocity agrees
   (−0.137 vs −0.137 m/s).
5. *Remainder (+0.38 % above the diagnostic run)* — not isolated. The coupled sectional speed is
   ≈ 0.1 % higher and MBDyn's node speed exceeds Ωr by 0.113 % at 5°; a speed error of that size
   alone would explain roughly +0.23 % (thrust ∝ speed²), so part of the remainder is unexplained.

Status: the dominant cause is DUST's rbf-branch evaluation point for the lifting-line body
velocity (a pinned-implementation behaviour, established by reproduction, not by
elimination); a smaller opposite remainder (+0.38 %) is not isolated (MBDyn's step-dependent
node speed is a candidate for part of it). No correction or
multiplier is applied, and DUST is not modified. **Observed bounds:** −1.42 % thrust, −0.88 %
torque for the locked-open rotor at 5° steps; spacing of the coupling nodes changes released
results by ≤ 0.05 % in thrust. **Assumptions, not observed:** at 2.5° steps the MBDyn offset
is ≈ 4× smaller, so the net bias is expected nearer the −1.8 % of the diagnostic build; during
fold motion the hinge rate adds ω_fold × (chord offset) to the same term (fold rates up to
≈ 40 rad/s vs Ω = 251 rad/s), so the bias may vary transiently by a fraction of itself; its size
during motion has not been measured. Comparisons within the continuous topology (latched vs
released, step or spacing studies) share the bias; absolute levels carry it.

### Unresolved observations (not hidden)

* **Grazing contact.** MBDyn's Newton iteration can cycle at a grazing contact of the
  piecewise penalty law (observed once at 5° steps without vortex stretching, step 299);
  the run fails closed with its accepted prefix. A smoothed contact law is a candidate
  improvement.

## 10. Supported cases and limitations

Supported: 800 mm research template (and other templates whose hinge lies inside the
station span, axis ∥ shaft), any catalog profile with a complete admitted stored
version (today NACA0012 and NACA2412; NACA2412 in two versions), prescribed shaft speed (constant
or ramp), releases inside the fold envelope and the admitted table envelope (§13). Not supported / not claimed: spin-up from rest,
fully folded start, torque-driven shaft, dry friction, applied hinge torque, joint loss,
gap aerodynamics, CFD pressure fields, structural stress, fatigue, clevis–tang strength,
manufacturability, latching or seating beyond the declared penalty law, the 250 mm /
7100 RPM case (no admitted data), the four profiles without data. Contact phases need
≥ 8 steps per contact half-period (reported as a diagnostic).

What the current evidence supports, and what it does not:

* *Demonstrated:* small-angle coupled motion (release from −5°, stop contact, rebound,
  settling oscillation around −0.5°) with every window converged, inside the admitted table,
  with exact kinematic/geometric correspondence and closed load/power transfer.
* *Short-window load predictions:* histories of 1.6–6 revolutions (main case: 2 latched + 3
  after release); per-revolution means still drift by ≈ 0.04 % between the last two locked-open
  revolutions. They are not long-term settled performance, and absolute levels carry the
  located rbf bias (≈ −1.4 % at 5°).
* *Unresolved numerical effects:* rbf lifting-line velocity point (above), MBDyn step-dependent
  node speed (+0.11 % at 5°, +0.03 % at 2.5°), azimuth lead 0.0019°/step at 5°, grazing-contact
  Newton cycling.
* *Deployment (§13):* releases from −15…−22.5° at 1600–2400 RPM completed with the same checks;
  the hinge response is model output from demonstration-assumption mechanics.
* *Unsupported:* folds beyond −23°, folded start, spin-up from rest, torque-driven shaft (no
  admitted table coverage or model); runs longer than the record bound. Mechanical properties are declared
  demonstration assumptions; `physical_qualification` is false.

## 11. Numerical summary (current topology; NACA2412, 800 mm template, 2400 RPM, 14 m/s)

All DUST values use the same admitted C81 table, the same canonical stations and 16
lifting-line elements per blade (8 per segment); means are over the stated windows. Run ids
and sealed digests are in the review package.

| Case | Step | Window | Thrust [N] | Torque [N·m] | Power [W] |
|---|---|---|---|---|---|
| Standalone DUST, one continuous line per blade (stock 3b1d2e61) | 5° | rev 6 of 6 (0.125–0.150 s) | 37.646 | 3.0387 | 763.7 |
| Coupled `continuous_rbf`, hinge locked open (`…073117`) | 5° | rev 6 of 6 | 37.112 | 3.0121 aero / 3.0145 drive | 757.9 aero / 757.6 drive |
| Coupled, latched at −5° (main `…071200`) | 2.5° | rev 2 (0.025–0.050 s) | 36.369 | 2.9555 / 2.9558 | 743.0 / 742.9 |
| Coupled, released at 0.05 s, rev 1 after release | 2.5° | 0.050–0.075 s | 36.934 | 2.9931 / 2.8134 | 753.6 / 707.1 |
| Same, rev 2 after release | 2.5° | 0.075–0.100 s | 36.765 | 2.9815 / 3.3628 | 749.6 / 845.2 |
| Same, rev 3 after release (last) | 2.5° | 0.100–0.125 s | 36.761 | 2.9808 / 2.9669 | 749.4 / 745.7 |
| Coupled, released at 0.05 s (`…071157`), rev 3 after release | 5° | 0.100–0.125 s | 37.049 | 3.0094 / 2.9864 | 757.3 / 750.6 |
| Fully deployed BEM (retained, 40 elements, ideal full open) | steady | — | 43.647 | 3.2774 | 823.7 |

After release the drive torque differs from the aerodynamic torque by the hinge's inertial
exchange (the distal segment's opening and oscillation), not by a model error; the power
check of §9 closes per window. Under matched geometry, tables, operating point and blade
discretization, standalone DUST with the continuous line gives −13.75 % thrust and −7.28 %
torque relative to BEM (method difference: unsteady free wake vs momentum theory, 16 vs 40
radial elements; not tuned). This replaces the earlier −11 % / −5 % figure, which belonged
to the two-line layout.

## 12. Flow and response view (wake, induced velocity, loads and hinge on one timeline)

**What is shown and where it comes from.**

| Layer | Source | Status |
|---|---|---|
| Vortex particles (position, strength vector α, core radius) | DUST result file of the accepted window | computed by DUST |
| Implicit panel-wake rows | DUST result file | computed by DUST |
| Velocity on the meridional plane y = 0 (lab frame) | `dust_post` flow_field (DUST 3b1d2e61 kernels: lifting lines, panel wake, particles, free stream) | computed from the vortex model; not a CFD field |
| θ, thrust, torques, hinge moments | the sealed record (MBDyn states, exchanged loads) | computed |
| Blade surfaces | catalog sections placed at MBDyn states | reconstructed |
| Boundary layer, surface pressure, viscous core below the particle radius, hub/spinner and hinge-gap flow, structural deformation | — | not resolved by this model |

DUST's lifting-line panel ends one chord behind the quarter-chord line: the first wake row lies
0.250 c behind the drawn trailing edge (measured at six sections, window 720 of the main case).
The blade geometry at a given state is exact (§9). Circulation, particle strength and induced
velocity carry the located rbf bias of the continuous line (≈ −1.4 % thrust at 5° locked open;
root circulation a few per cent low); particle positions are DUST outputs convected by that
velocity, so they are indirectly affected; the bias during folding has not been measured.

**Workflow.** Results → *Dinamik bağlaşık* → *Akış ve tepki*. If the record's run folder is on
this computer and the toolchain is attested, *Akış verisini hazırla* extracts the flow
companion from the retained DUST outputs (no solver; main case ≈ 35 s, ≈ 34 MB in
`<run>/flow/`). The view then offers an event jump (release, first stop contact, largest
opening, second-swing minimum, last window) and a window slider; for the selected accepted
window it shows the 3-D scene (reconstructed blades, DUST particles coloured by log₁₀|α|, panel
wake, velocity plane), the downward axial velocity on the plane, the near-wake strength by
radius against the last latched frame, and θ, thrust, torques and hinge moments on one time
axis with the window cursor and event lines. *ParaView akış paketini hazırla* writes
`particles.pvd`, `plane.pvd` and `rotor.pvd` (binary legacy VTK; validated with VTK 9.3.1
readers) plus the companion manifest.

**Frames.** A regular stride (≤ 81 frames, always the last window) plus every third window from
just before release to 72 windows after it, and the event windows themselves (main case: 110
frames; events are exact frames).

**Storage, binding and restoration.** The companion (`flow_companion.json` + `.npz`) stays in
the run folder and is not part of the sealed record (it is tens of MB; the record stays
restorable within the upload bound). It is accepted only if its manifest names the record's
`result_sha256`, every frame's source is that window's own DUST result file with exactly the
sha256 the sealed record lists in `raw_outputs` (and so is the geometry file `dust_post` reads),
each frame's DUST time label equals the window time minus one step, the array file matches its
digest and the manifest's shapes and counts, and every frame is an accepted window of the valid
prefix; any mismatch fails closed with a stated reason. The extractor re-hashes its inputs after
`dust_post` and refuses a redirected or stale work folder. Residual trust: the array digest is
declared in the same local folder, so the checks prove consistency with the record's sources,
not who wrote the arrays. The run folder itself must lie inside the runs root and hold this very
record, so a forged record naming another run cannot read or overwrite that run's flow data. A record opened from an
uploaded file has no run folder and therefore no flow view (the page says so). `dust_post` is
identified by name and sha256 in the manifest.

**What the main case shows** (NACA2412, 2400 RPM, 14 m/s, release from −5° at 0.05 s, 2.5°;
near wake = particles within 0.5 R below the disk; hinge band = r_h ± 15 mm):

| Window (event) | θ [°] | Thrust [N] | Particles | Hinge-band Σ\|α\| | Tip-band Σ\|α\| | max −w at z = −R/2 [m/s] |
|---|---|---|---|---|---|---|
| 288 (last latched) | −5.00 | 36.11 | 9 184 | 0.081 | 1.43 | 17.84 |
| 309 (first contact) | 0.28 | 38.70 | 9 856 | 0.087 | 1.47 | 18.51 |
| 312 (largest opening) | 0.81 | 36.21 | 9 952 | 0.088 | 1.48 | 18.68 |
| 338 (second-swing min.) | −2.70 | 36.76 | 10 784 | 0.090 | 1.44 | 18.60 |
| 720 (last) | −0.53 | 36.89 | 17 192 | 0.090 | 1.76 | 17.94 |

Around first contact thrust peaks briefly (38.7 N) and the slipstream half a radius below the
disk is ≈ 0.7–0.8 m/s faster; thrust and that slipstream speed are back near their settled
values about one revolution later (36.8–37.2 N, 17.9 m/s from window 360 on). The tip-band
strength does not return: it grows from 1.43 to 1.76 by the end of the run, which mixes the
response to opening (larger tip radius) with continued wake development, since the latched
reference frame itself is not yet a developed wake (particle count still rising). The hinge band
carries about 2 % of the near-wake strength throughout: the continuous line sheds no
concentrated hinge vortex. These are observations of the vortex model; causes are not separated.
The same view applied to the earlier two-line record (`…005547`, same case) shows why that
layout was replaced: its hinge band carries 46–60 % of the near-wake strength (3.4 while
latched, growing to 5.9–7.7 after release) and its inboard strength grows from 1.13 to 2.65
while thrust rises to 42.8 N — the junction vortex pair diagnosed in §9, now visible in the
genuine particle wake. Evidence: `reports/coupled_flow_20261112/`.

## 13. Deployment from larger folds and shaft acceleration

**Assessment (what limits a larger deployment today).** Three questions were checked before any run
(`reports/coupled_deployment_20261112/`):

1. *Hinge geometry of the continuous line.* DUST moves each line point as a weighted average of two
   rigidly moving nodes; across the hinge the averaged chord shortens by up to 1 − cos(θ/2). On the
   main mesh only the station just outboard of the hinge is affected: 1.3 % at −20°, 2.9 % at −30°,
   6.5 % at −45°, 25 % at −90°. The folded distal span is also swept against the local radial
   direction: 16.5° at −20°, 37.5° at −45°, 78° at −90° (span nearly aligned with the flow; a lifting
   line with 2-D polars no longer represents it). The run showed no concentrated hinge vortex in the
   particle wake at −20° (hinge band ≤ 2.7 % of the near-wake strength through release and rebound).
   Envelope: worst-case junction chord distortion ≤ 2 % and distal sweep at mid-distal radius ≤ 25°
   (near the hinge the sweep equals |θ|) → fold ≥ −23.0° for
   this design (chord-limited); enforced when the case is built and on every accepted window
   (`failed_geometry_envelope` ends the valid prefix).
2. *Aerodynamic coverage.* The retained NACA2412 table (XFOIL captures, attached flow) covers α −6…8°,
   Re 165k–330k, Mach 0.10–0.31. At 14 m/s the no-induction section states leave it below ≈ 2200 RPM
   (root Re < 165k) and below ≈ 1500 RPM also in α; at rest the sections sit at α −64…−77° (deep
   stall) and Re 42k–66k. The binding limit for deployment at speed is Mach: the opening swing adds
   θ̇·(r − r_h) to the distal speed. Released from −20° at 2400 RPM, the tip reached the table's
   Mach 0.31 seven windows after release (θ̇ = 95 rad/s and rising) and DUST stopped (fail-closed;
   accepted prefix kept, run `…191618`). An energy bound, θ̇_max = Ω √(2 m r_h c_g (1 − cos θ₀)/J_h)
   (aerodynamic and damping moments neglected; −5°: 42 vs 38.9 rad/s solved; −20° at 2200 RPM: 154 vs
   149 rad/s solved) estimates this before a run.
3. *Shaft acceleration.* A prescribed speed history needs no motor data and makes the drive torque an
   output (the torque that history requires). A torque-driven motor needs a measured torque–speed
   law, controller behaviour and rotor/hub inertia, none of which exist here. Order chosen: the
   prescribed ramp now; the motor law after measurements.

**What changed in the model.** *Drive:* `drive_profile = "ramp"` prescribes a smooth half-cosine rise
from `ramp_start_rpm` to the design RPM (MBDyn `cosine … half` drive on the axial-rotation joint;
nodes start at the ramp-start speed); the time step is defined at the design speed. Constant-speed
decks are byte-identical to before (pinned by test). *Hinge dynamics in post-processing:* the
centrifugal moment uses the instantaneous speed, and the rotating-frame acceleration moment
−(J_h + m r_h c_g cos θ) Ω̇ is a new derived channel included in the independent hinge balance; on the
−20° ramp run it peaks at 0.37 N·m (aerodynamic hinge moment 0.20 N·m) and the balance closes to 1.0 %
with it versus 4.7 % without it. *Preparation:* refuses folds beyond the envelope and planned speeds
whose section Reynolds or Mach leave the admitted table (robust to induction); reports α and the
opening-swing estimate as warnings (the bound is conservative; DUST and the per-window audit stop a
run that actually leaves the table).

**Runs** (NACA2412, 800 mm template, 14 m/s, demonstration-assumption mechanics: 30 g, CG 55 mm,
J_cg 3e-5 kg m², stop 500 N m/rad, e = 0.5; 2.5° steps at 2400 RPM; latched until 0.05 s):

| Case | Status | Peak θ̇ [rad/s] (θ̇/Ω) | Impact rate | 2nd swing | Mach max | Thrust: last latched rev → last rev |
|---|---|---|---|---|---|---|
| −5°, constant 2400 RPM (`…071200`) | completed | 38.9 (0.15) | 34.0 | −2.70° | 0.296 | 36.37 → 36.76 N |
| −20°, constant 2400 RPM (`…191618`) | stopped at the table's Mach limit, window 296 | ≥ 95 (0.38) | — | — | 0.306 accepted | 30.74 N latched |
| −15°, ramp 2200→2400 RPM over 0.05 s from release (`…203052`) | completed | 111 (0.48) | 99.4 | −8.06° | 0.296 | 23.93 → 36.93 N |
| −20°, same ramp (`…203049`) | completed | 149 (0.65) | 133 | −10.56° | 0.308 | 22.12 → 36.90 N |
| *deploy-v3 table:* −22.5°, constant 2400 RPM (`…220252`) | completed | 184 (0.73) | 167 | −11.54° | 0.342 | 29.49 → 36.76 N |
| *deploy-v3 table:* −20°, ramp 1600→2400 RPM over 0.06 s from release (`…220255`, 0.15 s) | completed | 105 (0.62) | 94.3 | −12.27° | 0.290 | 2.23 → 36.92 N |
| *deploy-v3 table:* −20°, ramp 2200→2400 (`…220258`, control) | completed | bit-identical to `…203049` | | | | |

All completed windows converged and stayed inside the admitted table; load, moment and power transfer
close to ≤ 6.5e-6 relative; hinge balance 1.0 %; contact resolved with 8.7 steps per half-period.
Folded −20° at 2200 RPM the rotor gives 22 N; first contact comes 3.6 ms after release; thrust then
oscillates with the hinge (34 → 25 → 27 → 33 N) and settles with the ramp (36.6–37.6 N at 2400 RPM);
the slipstream half a radius below the disk speeds up from 17.0 to 19.2 m/s with RPM. The prescribed
(infinitely stiff) drive reacts the stop impact with drive-torque spikes up to 285 N·m at −20°: a
consequence of prescribing speed (an impulse spread over one step, so its peak depends on the time
step), not a shaft-load prediction.

**RBF bias during motion.** The located rbf evaluation-point error scales with the body angular
velocity of the distal elements, Ω + θ̇. At the peak opening rate it is up to 1.65 × its steady size
on the distal elements (θ̇/Ω = 0.65 at −20°) for a few milliseconds — an estimate from the error's
form, not a measurement.

**Widened attached-flow polars (deploy-v3).** The binding limits above were the table's Mach 0.31 and
Re 165k, not the solver. XFOIL 6.99 was built locally from MIT's archive (pinned sha256, the CI
recipe) and a declared NACA2412 grid captured through the operator protocol
(`examples/research_deploy_polar_data.py`, `configs/polars/RESEARCH_AXIAL_800_DEPLOY_V3.json`):
Re 100k, 165k, 245k, 330k, 400k × Mach 0.07, 0.10, 0.31, 0.36, α −6…8° (unchanged; attached flow
only). The first two declarations (V1, V2) stopped on a genuine XFOIL non-convergence at Mach 0.05 /
Re 330k, α 6° (V2 with 300 instead of 160 iterations, same point); both stay retained as failed
evidence. A diagnostic convergence map of this executable then showed four isolated non-converging
states in the 2° sequence; V3's levels avoid them, so three of them (Mach 0.10/Re 130k, 0.20/165k,
0.20/400k) lie inside the table and are bridged by linear interpolation; the application states
this next to the version choice. At the six cells shared with the 2026-11-11 family the new build
reproduced CL/CD/CM exactly (GNU Fortran 11.4 vs 14.2); this does not show build independence
elsewhere. Evidence and limits:
`reports/coupled_deploy_polars_20261112/`. More XFOIL coverage is not validity in separated flow.

*Results with the widened table.* (1) The control case (−20°, 2200→2400 RPM) on the new table is
bit-identical to `…203049` on the retained one in all seven compared series (thrust, aerodynamic and
drive torque, hinge aerodynamic moment, RPM, θ, θ̇; the result hashes differ because the bound tables
differ): its trajectory stays inside
Re 165k–330k × Mach 0.10–0.31, where both C81 files interpolate the same six source tables
(`table_swap_check.json`). This is a consistency check of the table swap, not a measure of polar
sensitivity. (2) Released from −22.5° at a constant 2400 RPM — the case that stopped at Mach 0.31
from −20° — the rotor now deploys: tip Mach 0.342 and Re 352k in the swing (inside 0.36 / 400k),
first contact 3.3 ms after release at θ̇ = 167 rad/s, rebound to −11.5°, −0.75° at the end of the run; thrust
peaks at 48.8 N after release, and the prescribed drive reacts with up to 340 N·m (impulse
artefact, as above). (3) Released from −20° at 1600 RPM during a 1600→2400 RPM ramp over 0.06 s:
folded at 1600 RPM the rotor gives only 2.2 N at 14 m/s (latched-revolution mean; the run's lowest
section α is −1.8°);
contact after 5.0 ms at 94 rad/s, deepest rebound of all runs (−12.3°), then thrust follows the ramp
to 36.9 N. The rotating-frame acceleration moment peaks at 1.24 N·m against an aerodynamic hinge
moment of at most 0.18 N·m: at low speed with a fast ramp the shaft acceleration, not aerodynamics,
dominates the hinge moments (the global hinge balance closes to 1.0 % with that term; a dominant
term makes that relative residual easier to meet). The run's lowest section states (Re ≈ 135k,
Mach ≈ 0.085, run-wide minima) lie in the interpolation cell Re 100k–165k × Mach 0.07–0.10, whose
Mach 0.10 edge passes the bridged non-converging Mach 0.10 / Re 130k state. All three runs: every
window converged (at most 3 coupling iterations, read from the run records) and inside the admitted
table; load/moment/power transfer close to ≤ 6.5e-6 relative; hinge balance 1.0–1.1 % overall and
16–18 % in contact phases (`hinge_balance_contact_phase_relative_residual`, as for the earlier runs);
contact 8.7 steps per half-period. Wake metrics and flow
manifests for all runs are in `reports/coupled_deployment_20261112/`.

**Supported operating envelope (this design).** Folds to −23° (geometry, enforced). *Retained
2026-11-11 table:* planned speeds with section Re ≥ 165k and Mach ≤ 0.31 without induction (≈ ≥ 2200
RPM at 14 m/s, enforced at preparation). *Deploy-v3 table:* section Re 100k–400k and Mach 0.07–0.36
(enforced). The lower limit is then set by α, which is only a warning at preparation: without
induction the root reaches −5.6° at 1500 RPM (0.4° inside the −6° table edge) and −11.6° at 1200 RPM
(`section_state_map_deploy_v3.txt`). So the *estimated* floor is ≈ 1500 RPM at 14 m/s, untested; the
lowest tested start is 1600 RPM; DUST and the window audit stop a run that crosses α −6°. In both
cases α −6…8° and the table Mach hold during the opening swing, audited per window. Evidence
(completed): −5° and −22.5° released at a constant 2400 RPM; −15° and −20° released at 2200 RPM in a
2200→2400 ramp; −20° released at 1600 RPM in a 1600→2400 ramp. −20° at a constant 2400 RPM was run
only on the retained table, where it stopped at the Mach limit; it was not rerun on deploy-v3.
Margins are single runs (−22.5° at 2400 RPM: Mach 0.342 of 0.36, 5 %; the fold envelope is −23°).
Not supported: spin-up from rest or below ≈ 1500 RPM (root α < −6°: −11.6° at 1200 RPM, ≈ −77° at
rest; deep stall — needs data and a separately identified post-stall treatment, see the handoff),
folds beyond −23° (lifting-line geometry), torque-driven shaft (no measured motor data).
