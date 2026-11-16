# Browser walkthrough: complete opening–closing cycle and connection loads (2026-11-16/17)

`apps/pyfoldable_research.py` driven in the browser (1280×860 viewport, screenshots downscaled to 800 px), WSL2
Ubuntu 22.04, repository venv. Design: NACA2412, 800 mm, hinge 270 mm, 2 blades, 14 m/s, design stow −179°. Every run
was started from *Analiz → Çevrimi çalıştır*. Mechanism values are exploratory assumptions (30 g distal segment, CG
55 mm, 300 g·cm², stop 200 N·m/rad, e = 0.5), not hardware data. `physical_qualification` is false.

Screenshots 04–06 come from the first walkthrough on 2026-11-16, before the review fixes. Those fixes changed the
release-event definition, the arrow visibility and the line colours, but not these numbers. The rest were taken on
the final code.

| # | File | What it shows |
|---|---|---|
| 01 | `01_cycle_inputs_spring_return_pin_lug_offset.jpg` | Mode table, spring-return preset, pin-and-lug axial offset δ = 30 mm |
| 02 | `02_hinge_view_at_largest_stop_impact.jpg` | Close-up at the largest open-stop impact (t = 0.22245 s, 859 RPM, θ = 5.65° into the stop): force arrow, moment vector, pin axis, open/stowed bounds; N = 109 N, V_t = 344 N, M_z = −25.47 N·m = stop −24.79 + spring −0.46 + damper −0.23 |
| 03 | `03_cycle_timeline_with_cursor.jpg` | θ and RPM, θ̇/θ̈, connection forces and moments, distal thrust on one timeline with the event markers and the selected-state cursor |
| 04 | `04_load_vs_fold_angle_opening_closing.jpg` | Axial pull vs fold angle, opening (blue) and closing (orange) trajectories |
| 05 | `05_peak_loads_and_stop_contacts.jpg` | Peak table (622 N pull in operation; 344 N in-plane shear and 25.5 N·m pin moment at the impact) and stop contacts (impacts vs resting contact) |
| 06 | `06_contact_sensitivity.jpg` | First impact: tighter numerics change nothing. The peak scales with stop stiffness (−17.2/−24.8/−35.6 N·m); the impulse stays within ±4 % |
| 07–08 | `07/08_passive_*` | Passive mechanism (no spring): opens, does not return (final θ 0°). Without an axial offset the surfaces would collide beyond −66.6°, flagged |
| 09–11 | `09/10/11_latch_actuator_*` | Latch + actuator: closed by the actuator; the latch never engages because the blade floats at −0.48° (aerodynamic folding moment) |
| 12–13 | `12/13_coupled_record_*` | Coupled DUST–MBDyn record (−22.5° deployment): MBDyn connection loads. Latched phase −10.6 N·m about the pin; stop impacts up to −34.7 N·m (the table rendering drops the minus sign; the record holds −34.73); 826 N peak pull; start-up transient (12 windows) shaded and excluded; the three balance checks pass at 0.7–1.1 % |

Aerodynamic scope differs between the modes. The mechanical cycle uses an explicit, exploratory strip model
(no induction, no retained polars). The coupled record uses the DUST vortex wake with retained attached-flow polars,
but only for small-fold deployment at ≥ ≈1500 RPM. See `docs/fold_cycle_and_connection_loads.md`.
