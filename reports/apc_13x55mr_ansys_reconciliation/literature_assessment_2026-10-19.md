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

## Source receipt and preliminary register reconciliation — 2026-10-19

The actual `PyFoldable_Arastirma_Kaynak_Kaydi_2026-10-16.md` is now available and
was read in full: SHA-256
`fb73ea93c923ee0b7636a7f91b872f89480fbd5d105c35697e24946d32636b8c`.
This supersedes only the earlier inaccessible-register status above. Its ten
entries are an assistant-authored preliminary discovery record, not approved
datasets or a substitute for the originals. Its 2026-10-16 platform-access account
remains history; the successful Consensus and limited SciSpace retrievals recorded
above occurred on 2026-10-19 and are not retroactively attributed to 2026-10-16.

The original Maier source-reading scope above already checks R03's exact title,
model, static UIUC load acquisition, normalization and figure context. The now-read
DOCX supplies a separate CFD record, not the missing experimental row. The
[source intake](docx_intake_2026-10-19.md) keeps three evidence columns distinct:

| Evidence stream | Present evidence | Admission boundary |
| --- | --- | --- |
| APC manufacturer | Fresh PER3 bytes/hash and 4000 RPM zero-speed row | Computational prediction; numeric density/matched CAD not established |
| Engineer's CFD | Actual DOCX, stated last record, report windows, equations and figures; arithmetic reproduced | No case/data, raw histories or independent setup/statistic replay |
| Independent experimental candidate R03 | Original paper text/model/condition and institutional identity | Exact 4000 RPM numeric row, uncertainty, specimen/CAD correspondence and raw/traceable curve data still pending |

### R01–R10 claim / source / applicability ledger

Reconciliation/access date for every row: **2026-10-19**. “Register only” means
this execution read the supplied preliminary entry, not the linked original.
Bibliographic details in those rows remain register-supplied. No numeric dataset,
polar, hinge-loss factor or material limit is imported by any row. Missing
uncertainty is not set to zero. Source URLs below are durable research leads,
not proofs that a deferred original was opened.

| ID / source identity | Current reading scope and locator | Intended use / operating scope | Applicability, uncertainty and disposition |
| --- | --- | --- | --- |
| R01 Brandt–Selig 2011, DOI [10.2514/6.2011-1255](https://doi.org/10.2514/6.2011-1255); [Vol.1](https://m-selig.ae.illinois.edu/props/volume-1/propDB-volume-1.html) | Register only; original methods/Notes not re-read in this continuation | Low-Re propeller test-method/data lead | **DEFER original/data review**; no exact APC13x5.5MR or five-profile identity inferred; no uncertainty imported |
| R02 Deters 2014, [institutional thesis record](https://www.ideals.illinois.edu/items/49658); [Vol.2](https://m-selig.ae.illinois.edu/props/volume-2/propDB-volume-2.html) | Register only; thesis sections not read here | Reynolds/slipstream-method lead | **DEFER**; no transferable scale correction or admitted operating envelope/uncertainty |
| R03 Maier–Narsipur–Deters 2021, DOI [10.2514/6.2021-2223](https://doi.org/10.2514/6.2021-2223) | Original author-uploaded paper text and institutional records read in the earlier same-day assessment above; II.A/II.C/Table1/III.B Figure16(a)/Appendix A10 | Static whole-rotor APC13x5.5MR candidate; right-handed specimen, paper's true D=13.0 in; no exact 4000 RPM load sample verified | **ACCEPT source candidate / HOLD numeric admission**; per-run conditions, uncertainty, data rights and CAD/specimen match remain open; no visual curve digitization |
| R04 Dantsker et al. 2020, [UIUC Vol.3](https://m-selig.ae.illinois.edu/props/volume-3/propDB-volume-3.html) | Primary webpage re-read: opening, Notes1–4 and assembly description. Referenced PDF retrieval returned a tool error; cover not re-inspected | Root-pivot/yoke diameter and normalization-method context; static sweeps and forward-flow data page | **CONTEXT ONLY** for geometry/test provenance; not our spanwise-joint loss. Exact comparative data/uncertainty not admitted; 2020-2760/2762 discrepancy retained below |
| R05 Dantsker et al. 2022, DOI [10.2514/6.2022-4020](https://doi.org/10.2514/6.2022-4020); [Vol.4](https://m-selig.ae.illinois.edu/props/volume-4/propDB-volume-4.html) | Register only; model table not newly checked | APC fixed-blade comparison-method lead | **DEFER**; no Thin Electric data substituted for MR. Matching operating range/specimen and uncertainty remain unassessed here |
| R06 [NASA/NPARC spatial-convergence tutorial](https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html) | Primary method page re-read: Introduction, Grid Considerations and Order of Grid Convergence | Grid refinement and observed-order methodology, not a rotor experiment | **ACCEPT method context only**; explains successive grids and a three-solution observed-order estimate. No computed GCI/total uncertainty or universal propeller study sequence follows |
| R07 [NASA OpenVSP propellers](https://www.nasa.gov/reference/openvsp-propellers/) | Register only; hinge placement/orientation sections not re-read | Geometry-parameterization lead | **DEFER**; no qualified hinge placement, clearance or manufacturing claim |
| R08 Acar 2025, [article record](https://as-proceeding.com/index.php/ijanser/article/view/2790) | Register only for this article; register cites printed pp.150–151. Proposal pp.4–5 were independently read as proposal content | Background/model-assumption lead | **NO direct numeric transfer** from an unverified model correspondence. Do not turn auxiliary tip-rotor background into measured spanwise-joint loss; original article-specific review remains separate |
| R09 [2017 APC Slow Flyer CFD paper](https://www.mdpi.com/2226-4310/4/1/10) | Register only; no fresh full-text/figure read | CFD-method critique lead | **DEFER**; different-model data are not imported. Nearest-reference tuning is not established verification; no uncertainty or model accuracy accepted here |
| R10 Denton et al. 2022, DOI [10.1177/17568293221117189](https://doi.org/10.1177/17568293221117189) | Register only; rotor/hinge sections not newly read | Packaging, root-hinge/stops/deployment-method lead | **DEFER**; no geometry, material, vibration or deployment threshold transferred to our design |

The primary Vol.3 page labels its reference **AIAA 2020-2760**. The preliminary
register reports that the [linked original PDF](https://m-selig.ae.illinois.edu/pubs/DantskerCaccamoDetersSelig-2020-AIAA-Paper-2020-2762-CamPropsTesting.pdf)
cover/DOI says **2020-2762**. The cover was not recovered in this continuation;
therefore retain both provenance statements and leave bibliographic reconciliation
open. The primary webpage's Notes/assembly text independently confirms that yoke
selection participates in unfolded diameter and that screws at the blade roots
are folding pivots. This supports the applicability restriction, not a loss value
for a joint farther along an unchanged parent blade.

The original proposal p.6's low-Re/multiple-profile test plan is a requirement,
not a source of accepted measured polars. The proposal's illustrative analytic
coefficients on p.5 cannot close coordinate-bound alpha/Re/Mach coverage. Nor do
the now-transcribed CFD integrated loads close that gap. Separate joint-loss,
load-transfer, forced-vibration and controlled-folding literature work remains
future scope and does not block this bounded DOCX intake. No author messages,
numeric digitization, new solver run or gate promotion; `physical_qualification=false`.
