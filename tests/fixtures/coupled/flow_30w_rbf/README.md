# Flow companion of a recorded coupled run (regression fixture)

`result.json` is the unmodified sealed record of run `20261112T074237_2a6ad5bd14` (the same
30-window `continuous_rbf` run as `release_30w_rbf`; NACA2412, 800 mm template, 2400 RPM,
14 m/s, release from −5° at 1 ms, demonstration-assumption mechanics). Its `raw_outputs`
manifest lists the sha256 of every DUST result file of that run.

`flow/flow_companion.{json,npz}` were produced by
`pyfoldable/coupled/participants/extract_flow.py` from that run's retained DUST outputs
(no solver run): 12 accepted windows (every third window plus the release, contact, opening
and second-swing events), all vortex particles of those windows, the implicit panel-wake rows,
and the velocity that `dust_post` (DUST 3b1d2e61) computes on a 21 × 21 meridional plane. The
manifest binds each frame to its source file by the sha256 the sealed record lists. The DUST
HDF5 files themselves are not copied (`dust/Output/` is an empty placeholder so the folder looks
like a run folder to the application).

`dust_post_window30_9x7.vtr` is an unmodified `dust_post` flow-field output (9 × 7 points,
window 30) used to test the VTK reader.

The wake is undeveloped after 30 windows: software regression input, not engineering evidence.
