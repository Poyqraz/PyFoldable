# Recorded coupled run (regression fixture)

Copied without modification (except a truncated `dust/dust.log` tail) from an actual
DUST 3b1d2e61 + MBDyn 55c86cc6 + preCICE 2.5.0 run executed on 2026-11-12 through
`pyfoldable.application.coupled_analysis.start_run`: NACA2412, 800 mm research template,
2400 RPM, 14 m/s, 5 deg azimuth step, 30 windows, distal released from -5 deg at 1 ms
(demonstration-assumption mechanics). The wake is undeveloped after 30 windows: this is a
software regression input for post-processing/restoration, not engineering evidence.
