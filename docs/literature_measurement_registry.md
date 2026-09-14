# Provisional literature measurement registry

Reviewed 2026-09-09. The machine-readable index is
[`measurement_sources.json`](../data/literature/measurement_sources.json).
It records published measurements, their observable and acquisition state. It
does not override project inputs or physical gates. New prototype measurements
must receive their own source, hardware, run and calibration identities; retain
the literature baseline for comparison rather than replacing its provenance.

| Source | Available evidence | Permitted use now | Remaining integration gap |
| --- | --- | --- | --- |
| [UIUC Volume 1 V3](https://m-selig.ae.illinois.edu/props/volume-1/propDB-volume-1.html) | Existing APC SF 10x4.7 coefficient fixture; local bytes hashed in registry | Reuse existing fixed-propeller benchmark | No raw sensor streams or run-specific atmosphere; do not manufacture dimensional thrust/torque from assumed density |
| [Yang dataset V1](https://data.mendeley.com/datasets/fnw2jrwwhx/1) and [primary article](https://www.sciencedirect.com/science/article/pii/S2352340922005856) | Published five-test modal table; named raw acceleration and spring torque-angle files | Nonrotating modal-method reference | Raw bytes not obtained; acceleration is not a measured hinge-angle history |
| [Goli et al. dataset V1](https://data.mendeley.com/datasets/69hhwc3fd3/1) | 30-inch hover campaign including a folding type; 100 Hz, 60 s per case, 1500–3500 RPM | Cross-scale measurement-workflow reference | Raw manifest/channel units not obtained; geometry, paired-run compatibility and calibration records unverified |

Yang's article reports a four-hinge aluminium rig, inertia 0.0051 kg m² and
200 Hz acceleration acquisition. Its tabulated damping is calculated **per
hinge**; modal frequency and damping ratio describe the assembled system.
Spring slopes 0.10 and 0.07 N m/rad are quasi-static fits. The existing PY-05
effective modal demonstration remains separate from those individual springs.
The raw dataset has a CC BY 4.0 declaration; the article's PMC copy declares
CC BY-NC-ND 4.0. These are distinct rights scopes.

The five published modal summaries are retained with table row identities in
the registry. They are neither time-series samples nor a reserved holdout set:
all five contributed to the published aggregate. A later acceleration adapter
must audit sensor geometry, units, filtering, gravity contribution, initial
conditions and run segmentation before comparing model observations. Integrating
acceleration twice would create a derived estimate, not a direct angle measurement.

Run `python examples/run_literature_modal_audit.py` to use the five published
experimental summaries now. It recomputes system damping `2*I*omega_n*zeta`,
per-hinge damping divided by four, and the residual against the rounded published
values. `I*omega_n^2` is labelled effective modal stiffness; it is not substituted
for the measured quasi-static spring slopes. The output retains the registry hash
and never changes prototype parameters or generates pseudo-measured angles.

SciSpace and Consensus were queried for experimental folding/propeller data.
Consensus identified Yang's data paper and its full record was fetched; SciSpace
returned adjacent or irrelevant work and supplied no admitted measurement values.
Values and licenses above were checked against publisher/data-repository pages.
Mendeley page metadata and Yang filenames were readable through web retrieval;
the raw-data API request returned HTTP 403. No new raw file, checksum, uncertainty
bar or thrust value is claimed. The UIUC checksum binds the existing normalized
fixture, not the official archive or original sensor data.

Next acquisition work: retrieve and hash original files; preserve unmodified
copies under their source rights; audit channels and physical run identities;
add a source-specific adapter and independent-run split only where the data
support it. Published summaries can guide bounded research examples now, but
cannot establish the prototype's 85% thrust target, PA-CF strength, transient
deployment performance or 250/140 mm packaging feasibility. GEOM-01 therefore
proceeds from explicit geometry while those physical evidence gaps remain open.
