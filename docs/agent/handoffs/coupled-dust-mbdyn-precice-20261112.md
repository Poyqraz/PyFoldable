# Handoff: optional DUST–MBDyn–preCICE dynamic route (development record)

Branch `feature/dust-mbdyn-precice-coupling`, created from PR #113 revision
`5d9a51754557bdb3b95037080938da8b7bf8054b` (tree `3a60841dae7834aa6f847e8b5c6fc2400b8c3eaf`).
`pr113-integration-prep` and the PR branch are unchanged; nothing merged. The archived CSV
line-ending artifact (`reports/foldable_v2_engineering_design/report_key_results.csv`) is
deliberately not part of this work. Design/verification: [coupled dynamic analysis](../../coupled_dynamic_analysis.md).

## Environment and budgets (WSL2 Ubuntu 22.04.5, 28 CPUs, 7.6 GiB RAM, 2 GiB swap)

No sudo. Builds at `JOBS=2` (MBDyn later `-j4`): peak 1.6 GB RSS per job, system ≤ 2.4 GB used.
Toolchain root `~/pyf-work` (src 287 MB, build 1.9 GB, opt 338 MB; not in git). Each coupled run:
4 OpenMP threads, ≤ 1 GB, wall budget 3600 s. Engineering-run budget ≤ 11 coupled runs; executed
as listed below. No `.wslconfig`, MCP, credential or Serena change.

## Implemented

* `pyfoldable/coupled/`: `model` (declared case, units, validation), `c81` (admitted tables →
  DUST C81, DUST interpolation re-implementation for tests), `deck` (DUST/MBDyn/preCICE text),
  `frames`, `toolchain` (manifest, readiness), `supervisor` (detached orchestration),
  `mbdyn_output`, `postprocess` (alignment, channels, coverage, checks, status, sealed record),
  `participants/adapter.py` (MBDyn↔preCICE, coupling venv), `participants/extract_dust.py` (h5py).
* `pyfoldable/application/coupled_analysis.py` (prepare/start/poll/cancel/load/restore),
  `coupled_views.py` (plots, 3-D playback, VTK, CSV), `coupled_ui.py` (Turkish UI);
  `research_ui.py`: Analysis section, Results view switch, History + import dispatch, invalidation.
* `tools/coupled/build_toolchain.sh`, `write_manifest.py`; tests `tests/coupled/`,
  `tests/ui/test_coupled_ui.py`, fixture `tests/fixtures/coupled/release_30w` (recorded run).

## Decisions taken (with evidence)

1. preCICE **2.5.0** + pyprecice 2.5.0.4: DUST uses the v2 Fortran API; DUST issue #65.
2. MBDyn develop built `--disable-netcdf` (develop needs netcdf-cxx4); text outputs parsed.
3. DUST rigid coupling, `CouplingNodeOrientation = I`, MBDyn node orientation carries fold and
   azimuth; distal node on the hinge axis; preCICE vertices offset 10 mm per blade along z.
4. MBDyn `ms` ρ∞ = 0.6: ρ∞ = 0 gave a spurious spinning-rotor drive torque ∝ dt³ (1.22 N·m at
   10°); ρ∞ = 0.6 gives 0.0023 N·m at 5°. Steps ≤ 5° (MBDyn large-rotation velocity error ≈ 0.8 %
   at 10°). 2.5° for contact (≥ 8 steps per contact half-period with k_c = 500 N·m/rad).
5. Convergence on kinematics only (Aitken on Force+Moment). A Force relative measure produced
   Aitken 0/0 NaN with latched kinematics (run `20261112T005151_ac99b124d6`, failed_solver).
6. Adapter sends converged-iterate loads with the converged flag (upstream re-sent the previous
   iterate). Supervisor uses fresh run directories (stale `precice-run` aborted a dev run).
7. Window acceptance at max-iterations is read from `precice-MBDyn-iterations.log`.
8. Latch flag means "latched during part of the window" (release inside window 144 at 5° made
   the hinge-balance stencil span an acceleration jump).
9. **Aerodynamic topology `continuous_rbf` (default).** Root cause of the post-release thrust
   rise: per-segment lifting lines leave free end vortices at the hinge that cancel only when
   coincident (design doc §9 "Resolved"). One continuous DUST lifting line per blade, `rbf`
   coupling to a uniform grid of massless MBDyn nodes, each fully constrained to its segment's
   body node. Earlier records restore as `split_rigid` via `LEGACY_CONTROL_DEFAULTS`; legacy decks
   are byte-identical to the previous generator (8 cases incl. non-zero fold and fold rate).
10. Coupling nodes are dynamic, not static: MBDyn's external structural force with accelerations
    rejects static nodes (`StructExtForce(700): ... is not dynamic`, runs `…070651_69c3972b66`,
    `…070657_e65d989b79`, failed_solver at set-up). A massless dynamic node under a total joint was
    checked in a stand-alone MBDyn deck (|v| 50.33 vs Ωr 50.27 m/s).
11. Record size: node states keep ground, hub and body nodes only; preparation refuses runs whose
    estimated record exceeds the 24 MiB restore limit (`result_too_large`; previously a long run
    could produce an unrestorable record). The estimate is 1.19–1.23 × the actual record size for
    rebuilt 360/432/720-window `continuous_rbf` records and the 720-window `split_rigid` record
    (main: 16.6 MB actual, 19.8 MB estimated). Restore binds saved coupling nodes/bodies to the case.
    Independent review (read-only agent, two passes): no confirmed defect; size cap, restore binding,
    legacy byte-identity and an rbf record fixture were added in response.
12. Toolchain re-attested after Ubuntu unattended upgrades (2026-11-12 06:58–07:00: python3.10
    3.10.12-1~22.04.12 → .18, libgfortran5) changed the coupling interpreter hash; readiness
    failed closed (`toolchain_invalid`) until `tools/coupled/write_manifest.py` was re-run. Prior
    manifest kept at `~/pyf-work/coupled_toolchain.pre-ubuntu-upgrade-20261112.json`; a repeated
    `split_rigid` locked-open run (`…070700_c891c455ae`) reproduces `…004422_676d3c8c65`: exchanged window data, MBDyn outputs and DUST extraction byte-identical (HDF5 metadata and record digests differ; `toolchain/replay_comparison.json`).

## Actual executions (run ids under `outputs/coupled_runs/`, raw outputs kept locally)

| Id | What | Result |
|---|---|---|
| upstream | DUST `sym_test/coupled/ll` vs `static/ll` | 2e-10…1e-8 rel. L2, 11/11 converged |
| standalone | DUST open rotor, NACA2412 10°/5°/nel16, NACA0012 10°, 6 revs | see doc §9 |
| mech | MBDyn M1/M2, spin artifact study, ρ∞ sweep | see decisions 4 |
| `20261112T003819_46b457acea` | coupled locked open, 10°, 6 revs | 39.56 N, Q_aero 3.18 vs Q_drive 4.41 → artifact found |
| `20261112T004422_676d3c8c65` | coupled locked open, 5° | 38.60 N, Q_aero 3.0876, Q_drive 3.0899 N·m |
| `20261112T005343_c07845ca72` | release −5° at 1 ms, 30 windows (fixture) | completed, contact, hinge balance 0.9 % |
| `20261112T005554_32f9e3b7d0` | release −5° at 0.05 s, 5°, tol 1e-6 | completed, θ_max +0.735° (penetration), 2–8 iterations |
| `20261112T005601_e9e1ec9212` | same, tol 1e-8 | identical to 6e-8° / 6e-6 N |
| `20261112T010645_7d61b1a49c` | −15° latched start, 5° | failed_solver: DUST α outside table at window 1 (fail-closed) |
| `20261112T005547_39a32f06ef` | **main**: NACA2412, −5° release at 0.05 s, 2.5°, 0.125 s | see "Main results" |
| `20261112T010638_68279430ef` | NACA0012, same as main | completed 720/720; contact 3.47 ms after release at 39.7 rad/s, e_eff 0.518, settles −0.28°; Mach max 0.296 |
| `20261112T012130_6307e9790a` | release 5°, DUST vortex stretching off | identical θ history and thrust within ~1 % up to window 298; MBDyn Newton cycled at a grazing contact (step 299) → failed_solver with 298-window valid prefix |
| `20261112T011303_d503584a80` | started from the browser UI (5°, 173 windows) | completed; see "UI path" |
| `20261112T064218_36285ecfd1` | E1 `split_rigid`, −5° latched all run, 5° | steady 37.4 N: no rise without hinge motion |
| `20261112T064223_a564b2a131` | E2 `split_rigid`, damped release | rise still present (≈ +30 %) |
| `20261112T064948_aba91dea80` | E3 `split_rigid`, static −0.5° latched | ≈ 47–48 N from the first revolution vs 38.7 N open |
| `20261112T064957_1a28302b46` | E4 station merge near hinge | worse; approach reverted |
| `20261112T070917_55f6aea26f` | E3 condition, `continuous_rbf`, 0.075 s | 37.17 N (open: 37.25 N, `…070920_67c85e4108`) |
| `20261112T073117_fab3a9a152` | `continuous_rbf` locked open, 6 revs | 37.11 N / 3.012 N m; standalone continuous `sa_cont_s5_d150` 37.65 N / 3.039 N m |
| `20261112T070700_c891c455ae` | `split_rigid` locked open repeated after the OS update | exchanged data, MBDyn outputs and DUST extraction byte-identical to `…004422_676d3c8c65` (evidence for this case only) |
| `20261112T071157_91efdf9841` | `continuous_rbf` release −5° at 0.05 s, 5° | completed; last rev 37.05 N (split: 42.75 N) |
| `20261112T071200_20d4a1092d` | **main**, `continuous_rbf`, 2.5°, 720 windows | completed, 2280 s; see "Main results" |
| `20261112T074237_2a6ad5bd14` | `continuous_rbf` 30 windows | fixture `tests/fixtures/coupled/release_30w_rbf` |
| `20261112T104303_5d5d234081`, `…104306_fc454dbf5a`, `…104309_3578a648d8` | closure: rbf node spacing ×1 / ×0.5 / ×2 (diagnostic driver override), release −5° at 0.01 s, 2.5°, 259 windows | completed; ≤ 0.019 N, ≤ 0.011° differences; records intentionally do not restore (decks differ from the generator) |
| `20261112T104628_964ec74da3` | closure: started from the browser (0.04 s) and cancelled with *Durdur* | `cancelled`, 78/115 windows kept as labelled partial history |
| `~/pyf-work/diag/runs/sa_cont_s5_d150_ubcen` | closure: standalone DUST **diagnostic build** (lifting-line `ub` at the leading line; patch in the review package), same inputs as `sa_cont_s5_d150` | 36.972 N / 3.0025 N m (stock 37.646 / 3.0387; coupled rbf 37.112 / 3.0121) |

Full ordinary suite after the first commit: 2195 passed, 9 skipped (pre-existing missing generated CSVs),
37 subtests passed (WSL, Python 3.10.12, 398 s). Focused: `tests/coupled` + `tests/ui/test_coupled_ui.py`
23 passed. A compatibility defect (new control field broke restoration of earlier records) was caught
by these tests and fixed with an explicit legacy-default rule (`LEGACY_CONTROL_DEFAULTS`).

## Main results

Current main case `20261112T071200_20d4a1092d` (`continuous_rbf`, otherwise identical to the
record below): completed 720/720, every window converged (2–7 iterations, mean 2.01), α −0.48…2.90°,
Re 187k…305k, Mach ≤ 0.296. Hinge history matches the earlier record (first contact 3.65 ms after
release at 38.8 rad/s, rebound −19.9 rad/s, restitution 0.514, 7 contacts, second swing −2.70°,
final −0.53°). Thrust: last latched rev 36.37 N, last rev 36.76 N / 2.981 N m (drive 2.967 N m),
i.e. no post-release rise. Checks: load transfer 1.5e-6, moment 1.2e-6, power 8.9e-7, hinge balance
1.0 %. Absolute levels carry the ≈ 1.4 % coupled-vs-standalone offset of the rbf route (design doc).

Earlier `split_rigid` record `20261112T005547_39a32f06ef` (NACA2412, 800 mm template, 2400 RPM, 14 m/s,
demonstration-assumption distal segment 30 g / CG 55 mm / J_cg 3e-5 kg m², stop 500 N m/rad,
e = 0.5, latched at −5° for 0.05 s, 2.5° azimuth steps, 720 windows, 2738 s wall):
completed; every window converged (2–6 iterations, mean 2.01); all states inside the admitted
table (α −3.20…3.71°, Re 181k…305k, Mach 0.114…0.296; Mach margin 0.014). Hinge: first stop
contact 3.65 ms after release at 38.7 rad/s, rebound −19.9 rad/s (effective restitution 0.514 vs
declared 0.5), 7 contact events, peak compliant penetration 0.81°, second-swing minimum −2.70°,
settling oscillation around −0.6° (aerodynamic lag moment −0.16…−0.54 N m vs centrifugal
restoring stiffness 28.1 N m/rad). Checks: kinematic closure 1e-16 m, load transfer 6e-7, interface
power 5e-7 (relative), prescribed-speed deviation 5e-13 RPM, hinge balance 1.0 % (smooth windows),
contact 8.7 steps per half-period. Latched-phase rotor (−5° fold): 37.5 N, 3.01 N m (last latched
rev); last rev: 42.63 N, Q_aero 3.323 vs Q_drive 3.321 N m — the post-release rise is the spurious
junction vortex of this topology (resolved by `continuous_rbf`); do not use these post-release levels.

Time step 5° vs 2.5° (same case, `…005554_32f9e3b7d0`): first contact 3.82 vs 3.65 ms, impact rate
38.63 vs 38.74 rad/s, restitution 0.61 vs 0.514 (5° under-resolves contact, 4.3 steps), second-swing
minimum −3.17 vs −2.70°. Opening phase converged; post-contact rebound needs ≥ 8 steps/contact.

UI path: run `20261112T011303_d503584a80` (173 windows, 5°) was started from the browser in the
research workspace (fill demonstration assumptions → advanced duration 0.06 s, release 0.03 s →
start → progress → automatic navigation to results); re-opened after an app restart through
*Yerel çalıştırma klasöründen aç*; all result tabs, downloads and 3-D playback inspected.

Fully deployed BEM route unchanged: the UI reproduced 43.647 N / 3.277 N m / 823.693 W.

## Release-closure pass (2026-11-12, after `6f9f0a7`)

* RBF gap: geometry, frames, adapter transformations and timing checked first (all exact);
  the only input difference is the lifting-line `ub` evaluation point; a diagnostic standalone
  DUST build with that single change reproduces the coupled deficit (−1.79 % vs −1.42 %); the
  remainder matches MBDyn's +0.113 % node speed at 5°. No multiplier, no DUST change.
* Mapping verification during motion: DUST written geometry = RBF reconstruction from exchanged
  node states (1.1e-16 m); node rigidity 2.7e-8 m; spacing ×0.5/×2 ≤ 0.05 % thrust.
* Persistence: supported duration reported in preparation and in the over-limit refusal;
  bounded `.json.gz` transport; coupled import uploader bound 26 MB (the app's 5 MB default had
  blocked restoring records above ~5 MB by upload); result views show revolution counts and
  last-full-revolution means.
* Browser check on the working tree after `6f9f0a7`: BEM 43.647 N / 3.277 N m / 823.693 W;
  preparation caption and over-limit refusal; start, progress, cancel → labelled partial;
  restore from the run folder before and after two app restarts; all result tabs; 3-D playback
  frames equal the record (window, time, θ, thrust at windows 288/297/306/342/720); diagnostic
  spacing record refused ("Saved decks do not match"). Not exercised in the browser: uploading
  a `.json.gz` file (the browser pane cannot attach files; covered by tests and by verifying the
  archive bytes the download button serves).
* Toolchain: each run bound to its manifest (`toolchain/run_environment_binding.json`). The
  replay `…070700` vs `…004422`: exchanged window data, MBDyn outputs and DUST extraction are
  byte-identical, HDF5 files differ only in metadata, record digests differ by design
  (`toolchain/replay_comparison.json`); evidence for that case only. libgfortran5 is not hashed
  by the manifest. The standalone two-line vs continuous comparison (−1.9 %) spans the update.
* Independent read-only review of this pass: no defect in the bounded inflation; findings
  addressed: environment-mixing claim corrected, import peek size-gated (and RecursionError
  handled), per-uploader limit applied only when Streamlit supports it, caption wording at the
  duration-control limit, attribution of the +0.38 % remainder softened, replay evidence packaged.
* Review package: `reports/coupled_closure_20261112/` (README, SHA256SUMS).

## Next concrete items

1. The ≈ 1.4 % offset is located (design doc §9 "Located"): DUST's rbf branch evaluates the
   lifting-line body velocity at `loc_cen` (leading line). Options, none taken here: report
   upstream with the diagnostic patch and evidence; measure the bias during fold motion with a
   diagnostic coupled build; or change the pinned DUST revision after review.
1a. Longer histories need chunked records with lazy views (the 24 MiB bound is reported as a
   supported duration before a run).
2. Smooth contact law (or event handling) to avoid MBDyn Newton cycling at grazing contact.
3. Independent review of the coupled route (Astra-B or equivalent); PR creation was not
   requested.
4. Genuine provider data for wider α/Re/Mach (declared protocol) before any larger release,
   spin-up or folded start; or a separately documented post-stall model.
5. Torque-driven shaft option (motor law) as a distinct boundary condition.
6. Data for the 250 mm / 7100 RPM project case and the four other profiles.
