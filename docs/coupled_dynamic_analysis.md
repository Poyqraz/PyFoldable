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
* DUST rigid coupling (`mod_build_geo.f90`, `mod_precice.f90`): `c_ref = R0ᵀ(r − x0)`,
  `r = x + R(φ)c_ref`, `v = ẋ + ω × R c_ref`; loads reduced to the node:
  `F = Σ dF`, `M = Σ (dM + (R c_ref) × dF)` (moment about the **displaced** node).
  `CouplingNodeOrientation = I` and each MBDyn node carries `Rz(θ)·Rz(ψ_b)`, so no offset
  or rotation is applied twice. MBDyn applies global force and moment with the node as
  pole (external structural element, no offsets).
* preCICE vertices are DUST-local coupling coordinates with a 10 mm per-blade offset
  along the hinge-axis direction (one-to-one nearest-neighbour mapping; the distal node
  stays on the hinge axis, so its axial aerodynamic moment *is* the hinge moment).
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
and status consistency. Checksums identify content; they do not prove physical validity.

## 9. Verification performed (actual executions; details and run ids in the handoff)

| Check | Result |
|---|---|
| Upstream coupled LL vs standalone | 2e-10 … 1e-8 rel. L2, 11/11 converged |
| Standalone DUST, open rotor 2400 RPM/14 m/s, last of 6 revs | NACA2412 38.67 N / 3.114 N·m (10°), 38.37 N / 3.073 N·m (5°), spanwise ×2: −0.8 % T; NACA0012 29.72 N / 2.354 N·m. BEM (retained): 43.65 N / 3.277 N·m and 33.42 N / 2.488 N·m. DUST ≈ −11 % T, −5 % Q for both profiles (method difference; not tuned) |
| MBDyn mechanics vs independent ODE | spring+centrifugal pendulum: 0.005–0.015° max error; stop restitution 0.515 vs ODE 0.510 vs declared 0.5 |
| Drive torque vs dH_z/dt (aero-free) | 0.005 N·m RMS after start transient (ρ∞=0.6) |
| Coupled locked open rotor 5° vs standalone 5° | +0.6 % T, +0.5 % Q; drive 3.0899 vs aero 3.0876 N·m |
| Coupling tolerance 1e-6 vs 1e-8 (release case, 5°) | θ_max differs 6e-8°, final thrust 6e-6 N |
| Hinge balance (smooth windows) | 0.9–1.5 % relative residual |
| Main coupled case (NACA2412, −5° latched 0.05 s, 2.5°, 720 windows) | completed; contact 3.65 ms after release at 38.7 rad/s, restitution 0.514 (declared 0.5), peak penetration 0.81°, 7 contacts, settles near −0.6°; Mach max 0.296 |
| Time step 5° vs 2.5° (release case) | opening converged (contact time 3.82 vs 3.65 ms, impact rate +0.3 %); rebound needs ≥ 8 steps/contact (restitution 0.61 vs 0.514) |
| −15° latched start | fail-closed: DUST α outside table at window 1 |

### Unresolved observations (not hidden)

* **Post-release thrust rise.** In every release run (5° and 2.5° steps, coupling tolerance
  1e-6 and 1e-8, DUST vortex stretching on and off) the rotor thrust rises by ~10 %
  (≈38 → ≈42.5 N) about 0.04 s after release, while the hinge oscillation has already
  decayed to ±0.4° around a small lag angle; near-rotor wake vorticity grows by ~40 %.
  The locked open rotor shows no such change. The origin (DUST near-wake/implicit-panel
  handling under abrupt hinge motion and repeated grazing contact, or wake-box truncation
  interacting with the released-blade wake) is not established. Post-release thrust and
  torque levels after ~0.035 s must therefore not be read as converged rotor performance;
  the hinge kinematics before that time are unaffected (identical across the variants).
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
