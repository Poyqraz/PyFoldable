# APC 13x5.5MR experimental candidate — 2026-10-19

Status: **SOURCE CANDIDATE VERIFIED; NUMERIC IMPORT NOT ADMITTED**.
`physical_qualification=false`. This is a bounded source assessment, not a new
aerodynamic calculation. The named preliminary literature-register attachment was
unavailable; no claim is made to have read or reconciled it.

## Sources and access

1. Maier, N., Narsipur, S., and Deters, R. W. (2021), *Parametric Performance Study
   of the Aerodynamics and Aeroacoustics of Small Propellers in Static Conditions*,
   AIAA AVIATION 2021, AIAA 2021-2223, DOI
   [10.2514/6.2021-2223](https://doi.org/10.2514/6.2021-2223).
2. [Embry-Riddle institutional publication record](https://portfolio.erau.edu/en/publications/parametric-performance-study-of-the-aerodynamics-and-aeroacoustic/)
   and [Narsipur group publications](https://shreyas-narsipur.ae.msstate.edu/publications.html)
   corroborate authorship, title, year and DOI. Accessed 2026-10-19.
3. [Author-uploaded paper text](https://www.researchgate.net/publication/353527674_Parametric_Performance_Study_of_the_Aerodynamics_and_Aeroacoustics_of_Small_Propellers_in_Static_Conditions),
   accessed 2026-10-19. The page identifies Narsipur's 2021-09-10 upload and
   exposes the original paper, including its methods, equations, table and figure
   captions. This was read as paper text, not as an AI summary. AIAA's publisher
   endpoint returned HTTP 403. No original PDF byte hash or visual figure
   inspection was obtained; web-extracted plot labels are not digitized data.

## Source-to-claim ledger

The locations below refer to the original paper's section/table/equation labels,
as exposed in source 3. No page number is inferred from a rendered DOCX/PDF.

| Claim checked in original text | Location |
| --- | --- |
| Static thrust/torque data came from the UIUC balance; load cell 111 N, reaction torque sensor 0.706 N-m; laser/phototransistor RPM | II.A.1–2 |
| Density uses measured ambient pressure/temperature; shaft power is `P=2*pi*n*Q`, with `n` in revolutions/s; `CT=T/(rho*n^2*D^4)`, `CP=P/(rho*n^3*D^5)` | II.A.3, equations (1)–(4), nomenclature |
| Only right-handed propellers tested; APC 13x5.5MR listed with true diameter 13.0 in and manufacturer pitch 5.5 in | II.C, Table 1 |
| `CT`/`CP` versus RPM for 13x4.5MR and 13x5.5MR | III.B discussion and Figure 16(a) caption |
| Acoustic records: NC State chamber, 25.6 kHz for 15 s; distinct acquisition from UIUC loads | II.B.1–2 |
| APC 13x5.5MR acoustic figure has 1500/2500/3500 RPM spectral labels; appendix offers data to interested readers | Appendix A, Figure A10; opening paragraph |

## Applicability decision and missing evidence

The candidate is experimental evidence separate from APC's computational PER3
predictions. Its UIUC provenance needs checking against any other UIUC dataset
before counting datasets as independent. APC's own [performance-data page](https://www.apcprop.com/technical-information/performance-data/)
(accessed 2026-10-19) explicitly describes a proprietary vortex-theory computation
and links wind-tunnel experiments separately.

Assessment: suitable to pursue for a static **whole-rotor** comparison. Numeric
admission is still pending: no exact 4000 RPM experimental row, per-run density,
uncertainty, repeat/calibration record, raw loads or traceable digitization was
obtained here. Plot axes or the acoustic labels do not establish an exact 4000 RPM
load sample. Do not interpolate or substitute an experimental load, infer density
from a predicted load, or equate acoustic sampling duration with load averaging.

Before comparison, establish tested specimen/SKU/rotation and its relationship to
the engineer's CAD. Treat the Table 1 diameter as that paper's reference, without
rescaling the CAD or the dated PE0 geometry. Acquire tabulated data with conditions
and uncertainty, or separately declare any future figure digitization and its
error. No author outreach was performed.

Full-rotor curves are not coordinate-bound section polars for any of the five
catalog profiles. They cannot establish our spanwise-joint loss, hinge load
transfer, structural adequacy, forced vibration or controlled folding. Likewise,
root-folding propeller measurements would require a separate applicability case
before use for a spanwise joint; none is admitted here. The 250 mm design and
7100 RPM baseline are not validated by this source assessment.

## Discovery tools and limits

- **Consensus:** accessible. Author/DOI-keyword search first returned unrelated
  rotor/wing papers; exact-title search found the target. Its full record was
  fetched (record ID `7cf0b0d27ab954ec8b5018471e5bdac9`). That record supplied
  metadata/abstract, not run data or proof of the conditions above.
- **SciSpace:** accessible. Two natural-language queries, one naming the DOI and
  authors and one naming the full title, returned other propeller studies; neither
  returned the target DOI. This is a retrieval limitation, not evidence that the
  paper or its experimental data are absent.
- AI summaries and search snippets were discovery aids only. The ledger above
  was checked against the original paper text; neither tool supplied a polar,
  transferable joint-loss factor, qualified design or CFD validation result.
