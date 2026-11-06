# Application-managed provider design analysis

Implemented on the separate integration branch, not merged main. Dependencies:
Draft #103 `fc545b1584d679951fd28db0767cd71c790a7b06` and Draft #104
`8ba282e49ecf3c7ac96ada100c2721fa28a5803f`. Their branches are unchanged.

## Application boundary

[provider_design_analysis.py](../pyfoldable/application/provider_design_analysis.py)
connects an existing catalog-bound `DesignDraftArtifact`, explicit template/root
declarations, a named application-owned retained family and selected provider
policy to `prepare_polar_run` / `run_polar_run` and #103 immutable snapshots.
All five catalog profiles remain selectable. No CAD or normal-user polar JSON
is required. Profile/diameter alone do not generate chord/twist: the draft retains
the source-bound station geometry, hub, hinge and operating condition.

`TemplateDeclaration` retains actual source bytes, their checked SHA-256, a
template ID and source identity. This first UI path uses the existing workspace
station seed, labeled unqualified; it does not add a family-catalog selector.
The retained global station chord/twist/radius functions are not reset at a hinge.
One current hinge is checked; no hinge search, cuts, optimum or joint-loss ranking
is added. Opposed blades continue to share the same parent geometry.

`RootDatum` separately retains numeric value, explicit unit, physical/model meaning,
source/declaration identity and `declared_geometry` or `study_assumption` label.
Missing declaration blocks preparation. Hub radius, declared root and first
aerodynamic station remain distinct. The canonical 18 mm hub and 25 mm station do
not supply the root. Require `h-r_root > R-h`, equivalently
`h > (R+r_root)/2`; retain `h > R/2` separately as the shaft-origin comparison.
Historical screening is unchanged. There is no CAD-upload gate.

## Retained records and admission

Trusted application code populates `ManagedProviderRepository` with
`ManagedProviderFamily` objects. Each contains an **independent declared request
plan**, provider identity, returned cells, `UnlaunchedCell` source declarations
or `None` for unavailable records whose launch status is unknown,
source identity, unqualified evidence class and retained provenance bytes.
`read_retained_cell` is a read-only operator adapter for existing result/capture
files. `application_provider_repository()` is the deployment registration hook;
its shipped registry is empty. It never loads test fixtures as production data.
Deployment registration/persistence is remaining integration work, not an already
populated genuine-data service. Application callers do not invoke a provider.

The first admitted format is the reviewed XFOIL capture/result format. NeuralFoil
or arbitrary backend records require a separately reviewed admission adapter.
Preparation checks:

- Selected catalog and draft coordinate bytes; template source bytes and identity.
- Exact common selected provider policy, alpha order and scenario, and independent
  declared rectangular Re/Mach coverage. No missing/duplicate cells are dropped.
- #104 `_bind_returned_result`: attempted/returned request and provider identities,
  and capture request binding. Canonical retained preimage bytes must equal the
  independently declared request, including exact Re/Mach/angles/options.
- Reviewed adapter-generated script and airfoil input bytes; retained stream and
  polar bytes against receipts; process status, adapter source and executable
  before/after **file observations**. These are not process-image/build attestation.
- Read-only raw polar parsing/reconciliation against every returned point and the
  receipt ledger. A claimed complete flag/hash alone cannot establish admission.
  Require complete usable points, evidence readiness and all required family cells.

Either every required cell is admitted or no internal family is produced. Missing
applicable data, foreign coordinates/requests, incompatible policy, partial/missing
capture and provenance failures stop before BEM. Rejections retain attempted and
returned identities separately; unlaunched records have no attempted identity or
per-angle result. Budgets bound cells, JSON, raw capture and provenance content.

An admitted family is materialized internally with
`to_polar_table(require_complete=True)` and the existing polar bundle schema.
Existing fully-open, zero-offset, station-span, bounds=`error` preparation/execution
and numerical policy remain unchanged. Nominal rectangular ranges do not promise
all actual BEM trial queries are covered. BEM failure returns no partial totals.

## UI and immutable results

[dashboard](../apps/pyfoldable_dashboard.py) adds the opt-in **Uygulama kayıtlarıyla
BEM hazırlığı** route beside the optional manual upload route. It uses the current
five-profile draft, explicit root fields, application family selection and annulus
control. Preparation and BEM have separate explicit buttons. Rerenders/edits never
solve. `prepare_active_provider_design` and `run_active_provider_design` invalidate
stale output/downloads and re-admit unchanged inputs before execution.

Success wraps the retained admission/template/root/condition/provider/receipt
provenance into the report request before calling #103 `snapshot_success`.
Failure uses #103 `snapshot_failure`, with null totals and retained request/policy
or preflight rejection evidence. Records can enter the existing comparison history;
exports remain immutable and keep report text/hash/request links. Same-coordinate
repetitions do not become a distinct-profile comparison. Existing lower-layer
`caller_supplied_unqualified` and inert labels are not promoted.

## Acceptance and remaining evidence

[Application tests](../tests/application/test_provider_design_analysis.py) and
[AppTest witnesses](../tests/ui/test_managed_provider_design_ui.py) use explicitly
labeled inert positive records and an inert BEM seam. They cover five profiles,
raw receipt/request mismatch, incomplete family, missing root, policy mismatch,
stale active state, null failure totals and immutable export attribution.
The [retained negative fixture](../tests/fixtures/provider_design_analysis/README.md)
copies the once-executed 2026-11-06 partial result: 35/37 rows, +32 and -38 degrees
unavailable, seven successors not launched. It cannot admit a complete family or
reach BEM. The original preflight/execution packages remain unchanged.

Software acceptance is separate from (1) a separately authorized genuine
single-case provider/BEM success, (2) matched genuine results for distinct profiles
with controlled geometry/conditions/policy and independent review, and (3)
physical qualification. None is established by these inert tests. Genuine
comparison remains **UNESTABLISHED**, existing comparison block remains in place,
and `physical_qualification=false`. No provider experiment, genuine BEM study,
scheduler, automatic optimization, joint losses, clearance, vibration, FEA, CFD
or transient calculation is added or run. No historical result is repaired.
