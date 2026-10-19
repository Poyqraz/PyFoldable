# APC 4000 RPM DOCX intake — source received 2026-10-19

Status: **SOURCE TRANSCRIPTION AND ARITHMETIC CHECKED; RAW REPLAY / VALIDATION NOT ESTABLISHED**.
`physical_qualification=false`. No genuine provider, BEM, clearance, CFD, FEA or
transient study was run. This is a source-intake record, not a canonical CFD
qualification bundle or a scientific-gate decision.

## Revision and source identities

Continuation of Draft PR #105 from `447caf8edd6ac4bc922d2d8cbaf893a328a9f599`,
tree `47a19e77426799ddbdf62f688dc81de309a3fad4`; main remained
`022b466303c59b8c0adb02f935f9c2f065b0e2b5`. The original
[2026-10-16 inventory](report.md) and [earlier access checkpoint](intake_2026-10-19.md)
are history. Their missing-attachment status is superseded for this execution by
the actual source receipt below, without changing their earlier evidence.

All four actual files were opened and read from the owner's supplied local copies:

| Source | Verified SHA-256 |
| --- | --- |
| `Tahir_APC_4000RPM_Haftalik_Rapor_Taslagi1.docx` | `da6ea5414e49c10b40ff1202712193528b1bdb4b01fe7fde64b2d27ce5b856a3` |
| `TUBITAK_2209B_Research_Proposal.pdf` | `e16db4182fe5171dc7d06bb05c74875e0e80fac726cd8be52df366c29a7e1541` |
| `PyFoldable_Arastirma_Kaynak_Kaydi_2026-10-16.md` | `fb73ea93c923ee0b7636a7f91b872f89480fbd5d105c35697e24946d32636b8c` |
| `PyFoldable_Two_Astra_Handoff_2026-10-19.md` | `bbfa82a2506a3842203a6028eb2e01a113c16222c3f0a452cd5f0eef088a3b35` |

The first three match the handoff's expected identities. The handoff's own digest
is a fresh content observation, not a self-authenticating expected hash. Hashes
identify bytes, not truth, authorship, solver provenance or physical accuracy.
The originals and full vendor tables are not added to public Git history.

The DOCX is dated **14 October 2026** on its title page. Its actual OOXML contains
five tables, two native math objects and five embedded PNG figures. Text, table
cells and math structure were read; eight LibreOffice-rendered pages were checked
in context and all five native images were inspected. Rendered page numbers below
refer to this render; section/table/figure labels are primary locators. In the
[structured companion](docx_intake_2026-10-19.json), direct `w:body` child indices
include empty paragraphs and tables, and figure member digests allow exact replay
of source identification. The proposal PDF's nine pages were read separately.

## Report-stated setup and exact remaining gaps

Every entry in the middle column is a **report statement**, not inspection of the
meshed solid or a replay of Fluent settings.

| Topic / source location | Report-stated information | Unresolved evidence |
| --- | --- | --- |
| Geometry, section 2 / Table 2.1, p.1, body 8–10 | APC 13x5.5MR; CAD-measured `D=329.3519 mm`; hub diameter `19 mm`, height `14 mm` | Exact meshed CAD, revision, SKU/rotation and dimensional definition |
| Domain, same location | Hub-centred inner rotating cylinder: diameter `1.2D`, total axial length `0.5D`; outer cylinder: diameter `4D`, total axial length `8D`; nonconformal interface | Axial placement/split and actual mesh/case correspondence |
| Mesh, Table 2.1 and section 2 continuation, pp.1–2, body 10/12 | Hybrid volume mesh/prismatic wall layers; `4,475,758` cells; minimum orthogonal quality `0.1013`; maximum aspect ratio `161.16`; seven trailing-edge stair-stepping regions; 31 zero-area void faces removed | Report explicitly says post-repair recount is not documented; quality values are not independently verified post-repair metrics |
| Solver, section 3 / Table 3.1, p.2, body 14/16 | Fluent 2025 R2; 3D, double precision, pressure based, steady MRF; SST k–omega; constant-property air; energy off; momentum/k/omega First Order Upwind | Actual case/data, pressure scheme, gradient/coupling/relaxation/initialization settings and stopping policy |
| Condition, Table 3.1 | `+4000 RPM` about `+Z` by right-hand rule, centre `(0,0,0)`, axis `(0,0,1)`; freestream `0 m/s`; air `rho=1.225 kg/m3`, `mu=1.7894e-5 Pa s` | No solid density, mass or inertia follows from the air properties |
| Boundaries, Table 3.1 | Pressure inlet; outlet and `outer_radial` pressure outlets; gauge pressures `0 Pa`; no-slip wall stationary relative to rotating frame | Operating pressure, boundary turbulence data and complete zone definitions are not supplied |
| Force/sign convention, section 4 / Eq.4.1, p.2, body 20–21 | Thrust is `Fz` on propeller and hub walls; resistance moment `Mz=-0.110849921 N m`; positive required shaft torque `Q=-Mz`; `P=2*pi*n*Q`, `n=RPM/60`; shaft power excludes motor/ESC losses | Exact moment-report surfaces, origin, pressure/viscous components and exported report definitions are not stated. Rotating-region centre is not proof of the moment-report origin |
| Normalization, Eq.4.2, p.3, body 22 | `CT=T/(rho*n^2*D^4)`, `CQ=Q/(rho*n^2*D^5)`, `CP=P/(rho*n^3*D^5)` | This is the report's CAD/air normalization; APC numeric density and matched geometry are not established |

## Last record, independently reproduced arithmetic and APC prediction

Section 4 explicitly describes CSV iterations **1–1061** as complete and Table 4.1
as the **last record, not an average**. No CSV was attached; neither completeness
nor the actual solver export was independently replayed.

| Quantity | DOCX Table 4.1 CFD token | DOCX APC token | DOCX deviation (%) |
| --- | --- | --- | --- |
| `T (N)` | `5.212321` | `6.002` | `-13.16` |
| `Q (N m)` | `0.110850` | `0.108` | `+2.64` |
| `P (W)` | `46.432706` | `45.403` | `+2.27` |
| `CT` | `0.081365` | `0.0941` | `-13.53` |
| `CQ` | `0.005254` | absent (`—`) | absent (`—`) |
| `CP` | `0.033011` | `0.0325` | `+1.57` |

Using only retained report tokens (`T=5.212321 N`, `Mz=-0.110849921 N m`,
`D=0.3293519 m`, `rho=1.225 kg/m3`, `RPM=4000`) gives:

- `n=66.6666666667 rev/s`, `omega=418.879020479 rad/s`;
- `Q=0.110849921 N m`, `P=46.4327063286 W`;
- `CT=0.0813648616807`, `CQ=0.00525388970516`, `CP=0.0330111626010`.

These round to the CFD table's six-decimal tokens. The higher-precision moment in
the paragraph matters: using the displayed `Q=0.110850` instead gives
`P=46.4327394201 W`. Keep both source precisions; do not silently replace a token.
The identity `CP=2*pi*CQ` is arithmetically consistent under this normalization.
Applying `100*(CFD/APC-1)` reproduces all five printed deviations at two decimals;
the structured companion retains the unrounded arithmetic and inputs. This checks
internal arithmetic, not CFD truth, numerical verification or experimental accuracy.

The original [APC PER3 file](https://www.apcprop.com/files/PER3_13x55MR.dat) was
freshly downloaded on 2026-10-19: SHA-256
`bcf3914a4f7ac4c843823d6b9ebf26120824f2052ed145e03a1dad8246ec9751`,
117936 bytes. It matches the earlier inventory. Header `v2022-0915`, simulation
date `09/22/2022`; 4000 RPM block at line 131, zero-speed row at line 135 (1-based).
That row confirms the DOCX reference tokens: `J=0`, `T=6.002 N`, `Q=0.108 N m`,
`P=45.403 W`, `CT=0.0941`, `CP=0.0325`. The manufacturer's
[performance-method page](https://www.apcprop.com/technical-information/performance-data/)
classifies it as a vortex-theory computation, not an experiment.

Displayed APC torque times omega gives `45.2389342117 W`, not `45.403 W`.
This is compatible with displayed torque rounding; preserve the independent source
tokens. Neither column is a replacement for the other. APC's numeric density is
not stated in that file. The performance header differs from the previously pinned
PE0 `v2025-1001` geometry; common archive dates do not prove matched geometry.
Nominal `330.2 mm`, PE0-footer `328.676 mm`, PE0-last-station `328.93 mm`, and the
now DOCX-read CAD `329.3519 mm` stay separate. The report's `19 mm` hub also needs
CAD correspondence rather than automatic equality to the earlier catalog/PE0 hub
values. No rescaling or coefficient tuning was performed. The deviations above are
differences from a manufacturer prediction, not a total error or uncertainty band.

## Reported windows and convergence — raw replay unavailable

Table 4.2, section 4.1, rendered p.4, body 32/34:

| Iteration window | Integer count if endpoints are inclusive | Reported mean T (N) | Reported delta T (%) | Reported delta Q (%) |
| --- | --- | --- | --- | --- |
| `962–1061` | `100` | `5.214914` | `-0.1068` | `+0.0251` |
| `862–1061` | `200` | `5.218080` | `-0.2283` | `+0.0107` |

The report defines delta as the first-to-last difference divided by the first
value (percent). It is not standard deviation, peak-to-peak range, coefficient of
variation or uncertainty. Only the inclusive index arithmetic is independently
checkable here. The means/deltas remain **reported statistics**; no mean Q is
invented. Last `T=5.212321 N` is distinct from both reported means.

The paragraph reports net mass imbalance `-1.17671e-6 kg/s` and approximately
`0.0000959%` relative to total net-inflow boundaries. The boundary flux values and
denominator are not supplied; the percentage and flux-sign convention were not
independently verified or reconstructed by assuming a missing inflow.

Section 4.2 (body 36, p.4; Figure 4.2 on p.5) reports approximate visual residuals:
continuity `1.5–2e-4`, momentum order `1e-6`, k about `3e-5`, omega about `5e-6`.
The original image supports these approximate orders; continuity below `1e-4` is
not established. A residual is not a thrust-error percentage. Load stabilization,
global mass balance, iterative convergence, grid/domain convergence and physical
validation remain separate questions; no full convergence acceptance is inferred.

## Five figures — observations separated from claims

All original PNGs were viewed, without curve digitization or reconstructed raw
histories. Exact member identities, dimensions and SHA-256 values are in the JSON.

| Figure / member / rendered page | Direct visual observation | Limit |
| --- | --- | --- |
| 4.1 / `word/media/image1.png`, rId8 / p.3 | Four panels; axes are iterations. Large initial excursions; near the end T decreases gently after a maximum, while Q turns gently upward after a minimum | Supports qualitative drift only; cannot replay window means, sample counts or completeness; not physical-time motion |
| 4.2 / `image2.png`, rId9 / p.5 | Scaled-residual plot with continuity, three velocity, k and omega labels; final continuity remains above `1e-4` visually | Raster estimates, not retained exact residual histories or a formal stopping test |
| 5.1 / `image3.png`, rId10 / p.6 | `Z Velocity` slice with scale `-15` to `+5 m/s`; negative-velocity wake extends in the depicted -Z direction; hub-region contrast | Display limits are not global extrema; reported global Vz `-22.7686/+47.8125 m/s` comes from body 41, not this color scale |
| 5.2 / `image4.png`, rId11 / p.6 | Local tip-region patch of positive Z velocity; displayed scale approximately `-16` to `+37.6 m/s` | Does not isolate physical tip flow, mesh artifacts or first-order diffusion; no causal attribution to y-plus |
| 5.3 / `image5.png`, rId12 / p.7 | `Wall Yplus` scale `1.43e-2` to `1.19e1`; hub/root appear lower than outer blade regions | Scale is not an area-weighted mean or verified whole-surface maximum. No all-surface y-plus≈1 claim, wall-layer sufficiency or torque accuracy follows |

Sections 5.1–5.2 discuss possible causes and future checks. These are hypotheses
and plans, not results of a schema/mesh comparison. Table 6.1 (p.8, body 57) plans
same-mesh Second Order, tip/wall/wake refinement, three meshes and a separate
domain study, 6000/8000 RPM points, sliding mesh and radial/field exports. None is
executed or authorized by this intake. The reported future 8000 RPM tip Mach≈0.41
does not become an operating result of the present 4000 RPM run.

## Proposal requirements and ownership boundaries

The actual proposal was read; the owner identifies it as the accepted project
proposal. It is a requirements/planning source, not a new experimental record.

| Requirement / scope | Original location | Disposition |
| --- | --- | --- |
| 250 mm deployed / 140 mm folded; 7100 RPM comparison; 0.85 thrust-retention goal | Proposal p.3, section 1.1; p.6 schedule | Preserve as targets. Its 0.70 preliminary observation is a report-stated historical claim, not replayed data or a calibrated fixture |
| Five profiles: NACA0012, NACA2412, NACA23012, NACA4415, NACA63-412; section lift/drag/moment, stall, roughness/Re tests and hinge moments | Proposal p.6, profile/production plan | No reduction to the initial two-profile experiment; coordinate-bound matching polars are required by owner handoff section 4 |
| PA-CF/print-direction dependence; repeated Re tests, surface treatment, mass balance and calibration plan | Proposal pp.2,6 | Material strength, inertia, calibrated measurements and completed testing remain absent |
| Lift optimization with strength, weight and energy constraints; blade/joint parameters | Proposal p.5, method | Illustrative analytic section coefficients are not measured five-profile polars or authority to bypass scientific gates; no optimum is selected |
| Motor-driven opening and folding on motor stop; vibration/noise measurement facilities | Proposal pp.3,5,7 | Function/measurement intent, not validated controlled motion or forced-vibration acceptance. No extra actuator requirement is invented |
| Longer proximal than distal segment within each blade; preserve parent radius/chord/twist/profile lineage | Owner opening clarification and supplied handoff section 4 | Additional explicit requirement, not a quotation claimed to be in the proposal. It does not mean unequal opposed rotor blades |

The proposal's background illustration/references and its planned MATLAB method
do not change this bounded Python repository task or establish this spanwise joint's
loss model. Air density in Table 3.1 is not the printed solid's material density.
The [literature continuation](literature_assessment_2026-10-19.md#source-receipt-and-preliminary-register-reconciliation--2026-10-19)
now distinguishes the original preliminary register from verified original sources.

## Focused missing-input handoff and conclusion

The [updated engineer handoff](engineer_handoff_2026-10-19.md#source-received--current-engineer-request-2026-10-19)
asks for existing project-specific CAD, case/data, histories, post-repair mesh/wall
records and report definitions. It does not ask the engineer to rewrite the attached
DOCX or recreate public APC tables. The actual source document is now transcribed;
missing solver files do not undo that accomplishment or become falsely present.

The 13-inch/4000 RPM result does not validate the 250 mm/7100 RPM design, any of the
five catalog profiles, section-polar coverage, joint losses, structural load
transfer, forced vibration or controlled deployment/folding. CFD replay,
independence/uncertainty and experimental validation remain unestablished.
Astra-B's independent review of the final exact published head remains pending.
