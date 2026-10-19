# Engineer handoff — APC 4000 RPM source intake

Date: 2026-10-19. Authoring role: Astra-A implementation/research.
Status: **PARTIAL; ACTUAL DOCX ACCESS REQUIRED**. `physical_qualification=false`.

This updates the engineer-workflow instructions in the [2026-10-16 inventory](report.md).
It preserves that missing-document inventory as history. The
[access checkpoint](intake_2026-10-19.md) records what was and was not read.

## First input: the report itself

Supply `Tahir_APC_4000RPM_Haftalik_Rapor_Taslagi1.docx`. The owner-supplied expected
SHA-256 is `da6ea5414e49c10b40ff1202712193528b1bdb4b01fe7fde64b2d27ce5b856a3`;
it remains unverified. If the actual digest differs, retain both identities and
identify the revision before attributing its contents. Never silently relabel it.

**The DOCX alone is sufficient to begin faithful transcription. CAD, case/data
and CSV availability are not prerequisites for recording what the report says.**
After hashing, inspect its actual paragraphs, native equations, tables and every
embedded figure, including text or formulas stored as images. Keep original
labels/units and unresolved contradictions. Use rendered page locations only
after rendering; also record stable section/table/figure or OOXML object locators.

| Requested item | Required source-bound recording |
| --- | --- |
| Geometry | Report's diameter definition, blade count, hub/solid identity and units; distinguish stated CAD dimensions from inspected CAD |
| Operating conditions | RPM, freestream/advance condition, density/viscosity/temperature and which are stated, absent or derived |
| Solver/settings | Fluent/version, steady/transient, rotating formulation, turbulence/wall treatment, discretization/order, boundaries, mesh metrics, repair and stopping criteria, wherever actually reported |
| Forces/moments | Axes, frame, sign, rotation direction, moment origin/axis, surfaces/components and whether quantities refer to one blade or the whole rotor |
| Last iteration | Iteration identifier and exact final thrust/torque/power tokens, separately from any average |
| Averaging window | Start/end and inclusion rule, sample count, mean and reported spread/drift/statistic definitions; absent definitions stay absent |
| Convergence | Report's stated criterion and outcome, plus separately labeled visual observations of residual/load plots; figure resolution limits stay explicit |
| Manufacturer reference | Exact source/revision, matched speed/advance condition, coefficient conventions and which reference is prediction rather than experiment |

Separate four classes in the intake: **report-stated**, **reproducible arithmetic**,
**visual observation**, and **requires unavailable inputs**. Recompute formulas
only from explicitly supplied numbers; preserve displayed rounding. Check signed
`P=omega*Q` against the declared aerodynamic/shaft convention before using a
torque magnitude. Do not insert assumed density, direction, dimensions or settings.
A reported window statistic is not independently replayed without raw samples.

## Separate replay/validation inputs

Request only existing files, with units/revisions/digests and their relationship
to the reported run: the meshed CAD, Fluent case/data or solver archive, complete
residual and force/moment histories, post-repair mesh/wall-resolution records and
any already-existing radial-load export. These were not inspected in this task.
Do not mark them present merely because the DOCX describes them.

Those files enable checks of the actual setup and raw-history arithmetic. They
do not by themselves establish experimental validation, mesh/domain independence,
or agreement with a manufactured article. No CFD, FEA, clearance, provider, BEM
or transient run is authorized here. The old same-mesh second-order calculation
remains a proposal requiring a separate bounded authorization; mesh/domain studies
remain separate too.

## Reference and engineering boundaries

Use the [2026-10-19 literature assessment](literature_assessment_2026-10-19.md) for
the experimental APC candidate and its pending data admission. Keep manufacturer
predictions, reported CFD and experiments distinct. Do not tune to the APC row.

Preserve parent geometry/global chord–twist correspondence, longer proximal than
distal segments within each jointed blade, and distinct matched-polar attribution
for all five selectable coordinate-bound profiles. The 13-inch APC reference is
not the 250 mm jointed design or the 7100 RPM baseline. Integrated loads cannot
supply section polars, joint-loss evidence or a structural load-transfer proof.
Steady CFD convergence cannot establish forced vibration or controlled folding.
No physical gate, archived evidence or design-selection decision is promoted.

Send the source-bound intake and exact final commit/tree to Astra-B through the
owner. Astra-A checks and prior implementation reports are not Astra-B approval.
