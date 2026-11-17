# Browser walkthrough of the research application (2026-11-16)

Screenshots of `apps/pyfoldable_research.py` driven in a browser (Streamlit, port 8765, 1280×860 viewport,
downscaled to 800 px wide), on WSL2 Ubuntu 22.04 with the repository venv. Each run below was started with
the UI's own buttons. These are software demonstrations, not qualification evidence
(`physical_qualification` stays false).

Revision: screenshots 01 and 03–05 were taken at `d6e7119`. The rest were taken on the working tree
committed right after it (see the PR history): that commit adds the test isolation, the full-width
capability table, the figure title fix, equal-thrust/power matching and the corrected comparison caption.
Before the walkthrough, `outputs/research_results` was moved to
`outputs/research_results.test-pollution-20261116`, because earlier test runs had filled it with fixture
results. It was set aside, not deleted.

| # | File | What it shows |
|---|---|---|
| 01 | `01_design_six_profile_inventory.jpg` | Design page: all six catalog profiles have stored data versions |
| 02 | `02_analysis_capability_ready.jpg` | Analysis page: per-method status (steady BEM ready; time-dependent analysis needs mechanical inputs) |
| 03 | `03_bem_result_naca4415.jpg` | NACA4415 (catalog V2 family) BEM, 2400 RPM, 14 m/s: 54.62 N, 4.254 N·m, 1069 W |
| 04–05 | `04/05_bem_rotating_playback_*.jpg` | Rotating-propeller playback of the steady result: thrust arrow, +Ω arc, time slider, speed buttons; frame text t, RPM, ψ, slow-motion factor |
| 06 | `06_bem_momentum_flow_reconstruction.jpg` | Momentum-theory slipstream from the BEM induction (stream tubes; disk and far-wake axial and swirl velocity), labelled as a reconstruction, not a wake or CFD |
| 07 | `07_matched_comparison_naca0012_naca2412.jpg` | Matched pair on the 2026-11-11 v1 families: NACA0012 33.42 N / 625 W, NACA2412 43.65 N / 824 W at 2400 RPM |
| 08 | `08_equal_thrust_comparison.jpg` | NACA2412 rerun at the RPM giving NACA0012's thrust (2216.6 RPM, 4 BEM solves): 33.42 N at 610 W vs 625 W; only the RPM differs |
| 09 | `09_unmatched_comparison_named_fields.jpg` | NACA2412 (v1) vs NACA4415 (catalog V2): data version, scenario, XFOIL build and Re/Mach grid named; a common capture is needed for a matched pair |
| 10 | `10_local_dynamic_and_bem_results.jpg` | Records page after an app restart: local coupled runs and saved BEM results, reopened without recalculation |
| 11 | `11_coupled_deployment_hinge_history.jpg` | Saved DUST–MBDyn–preCICE deployment (NACA2412, −20°, released during the ramp): latch, release, stop contacts, rebound |
| 12 | `12_coupled_playback_first_contact.jpg` | Coupled 3-D playback jumped to "İlk temas": t = 55.21 ms, 1615 RPM, θ = 0.41°, ψ = 170.2° |
| 13 | `13_dust_velocity_plane_streamlines.jpg` | dust_post y = 0 plane (axial component) with instantaneous in-plane streamlines and particles; ≈ 0.5 m/s induction at 7.5 N, as expected right after release |

Observations during the walkthrough:
- Redrawing the WebGL mesh took roughly 0.3–0.5 s per frame in the small embedded browser pane, so
  playback ran slower than its nominal frame time.
- The slider label can lead the frame text by one frame while a frame is still drawing; they agree once
  it settles.
