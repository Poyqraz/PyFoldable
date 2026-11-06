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

### PR107 independent-review repair — 2026-11-06

The application now assesses retained **profile, Mach and Reynolds header fields**
as well as coefficient rows. The pure
[header helper](../pyfoldable/application/retained_xfoil_header.py) records original
header lines/tokens and each field's `missing`, `malformed`, `contradictory` or
`compatible` interpretation. Present malformed/duplicate/contradictory fields reject
before BEM, including explicit execution's fresh admission. Headerless records
remain supported: absent fields stay unavailable with no invented value and supply
no observed profile/Mach/Re identity. Ncrit/xtrf and other header text are retained
raw, not interpreted by this bounded header check.

The pinned MIT archive SHA-256 is
`5c0250643f52ce0e75d7338ae2504ce7907f2d49a30f921826717b8ac12ebe40`.
Its `Xfoil/src/iopol.f` (`POLWRIT`, lines515/560/684/692; member SHA-256
`7ab33bdac69a0cc620a4d2de18f85e75f50846337443762ed82bfa7012356e7e`)
writes the input NAME, Mach `F7.3` and Reynolds divided by1e6 as `F9.3`.
Comparison first parses the checked adapter's `.12g` command token into binary64,
then applies the writer's Re scaling. Exact rational half-quantum intervals derive
from the three printed decimals: Mach half-width0.0005; Reynolds half-width500.
Exact halfway ties admit either neighboring printed token. No arbitrary epsilon
or ambient Decimal context changes these bins. Requested Mach
`0.040507164718475736` / Re `26030.624179244653` are compatible with `0.041` /
`0.026 e 6`. This is printed-precision consistency, not proof of coefficient origin.

Optional returned metadata is reconciled when present: `returncode` must be an
integer equal to the capture receipt; `polar_row_count` must be an integer equal
to `len(rows)` from the reviewed parser (including valid unmatched rows, not the
requested-angle count); `repanel` must be boolean and agree with reviewed option
semantics (default true) and checked script `PANE`. Booleans are not integer exit
codes/counts. Absent metadata remains absent. Returned documents and raw receipts
stay separate from derived assessment records, including on rejection.

Preparation first retains a canonical **attempted selection**, before any geometry
or policy rejection. It includes actual draft/template identities, root declaration
value/unit/meaning/kind/source, family, annulus setting and original policy UTF-8
text/bytes/digest; malformed policy text is retained with parsed value unavailable.
Its digest uses sorted-key compact JSON, `ensure_ascii=False`, finite numbers and
UTF-8, without a trailing newline. No timestamp, counter or salt is added.
Preflight snapshots expose `attempted_selection` / `attempted_selection_sha256`;
the existing CSV `attempt_sha256` resolves to that same retained canonical object
in the JSON record. Prepared/executed request, report and totals remain null.
Selection-digest equality, including numeric type and signed zero, prevents
relabeling a rejection. Successful reports retain the attempted selection separately
from their prepared/executed request identities.

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
