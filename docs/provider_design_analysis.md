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

## Persistent operator store — 2026-11-06 stacked increment

The earlier empty deployment hook is replaced by
[provider_record_store.py](../pyfoldable/application/provider_record_store.py).
This increment is stacked on reviewed #107 `8f2d38a826b6118ab97273dbd26ef6bbf43d23ae`
(tree `08feaa83ac120f783f3f59cafecbbd9a20a06118`), not merged main. Original
#103–107 branches and the integration base are unchanged. No data is installed in
a production registry by this increment. The old empty-registry descriptions above
and in historical handoffs describe the preceding revision.

### Operator setup and the single registration entry point

Run the application and registration under an account with access to a private,
persistent **local POSIX filesystem** directory. No database, scheduler, automatic
acquisition or user-result persistence service is added. Configure its absolute
path before starting Streamlit. Provision its parent directory first; registration
creates the private store directory, while runtime loading never creates it:

```bash
export PYFOLDABLE_PROVIDER_STORE=/srv/pyfoldable/provider-records
python -m streamlit run apps/pyfoldable_dashboard.py
```

The operator entry point is `ProviderRecordStore.register_family(family,
version_label=...)`. Supply an independently declared ordered plan, not a plan
inferred from returned success records. The following operator-only example uses
a separately retained JSON plan whose `requests` entries explicitly contain
`profile`, `alpha_rad`, `reynolds`, `mach`, `n_crit`, `xtr_upper`, `xtr_lower`,
`max_iterations`, `timeout_s`, `scenario_id`, and `options`. Its `cells` list has
one slot per planned request: `returned` with result/capture locations,
`not_launched` with source-bound reason/identity, or `unavailable` when launch
status is unknown. These paths are operator inputs, never normal-user UI inputs.

```python
import json
from pathlib import Path
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.core.providers import PolarGenerationRequest, ProviderIdentity
from pyfoldable.application.provider_design_analysis import (
    ManagedProviderFamily, UnlaunchedCell, read_retained_cell,
)
from pyfoldable.application.provider_record_store import ProviderRecordStore

plan_path = Path('/operator-evidence/independent-family-plan.json')
original_plan = plan_path.read_bytes()
plan = json.loads(original_plan)
provider = ProviderIdentity(**plan['provider'])
requests = tuple(PolarGenerationRequest(
    airfoil=load_project_airfoil(row['profile']),
    alpha_rad=tuple(row['alpha_rad']),
    **{key: row[key] for key in (
        'reynolds', 'mach', 'n_crit', 'xtr_upper', 'xtr_lower',
        'max_iterations', 'timeout_s', 'scenario_id', 'options')},
) for row in plan['requests'])

def retained_cell(row):
    if row['status'] == 'returned':
        return read_retained_cell(Path(row['result_path']), Path(row['capture_directory']))
    if row['status'] == 'not_launched':
        return UnlaunchedCell(row['reason'], row['source_identity'])
    if row['status'] == 'unavailable':
        return None  # no assertion about whether a process ran
    raise ValueError('Unknown declared cell status')

family = ManagedProviderFamily(
    family_id=plan['family_id'], provider=provider, requests=requests,
    cells=tuple(retained_cell(row) for row in plan['cells']),
    evidence_class=plan['evidence_class'], source_identity=plan['source_identity'],
    provenance_files=(('independent-family-plan.json', original_plan),
                      ('build-and-source-record.json', Path('/operator-evidence/build-and-source-record.json').read_bytes())),
)
with ProviderRecordStore('/srv/pyfoldable/provider-records') as store:
    binding = store.register_family(family, version_label='operator-declared-v1')
print(binding)
```

Use one coordinate-bound profile per application family; retain a multi-profile
experiment's original ordered requests in separate profile families without
editing requests or classifying unknown launch status as unlaunched. Attach the
original plan and relevant build/source/execution provenance bytes. The plan's
`evidence_class` retains `caller_supplied_unqualified` for actual unqualified data
or `inert_fixture` for explicitly isolated software fixtures. Never install inert
fixtures as normal deployment data. Registration does not supply physically
validated coefficients or admit a complete family.

### Storage, identity and failure semantics

Schema1 canonical UTF-8 manifests live in `records/<registration-key>.json`.
Original results, capture files, provenance and exact canonical request preimages
live in `blobs/<sha256>`. Logical capture/provenance names are labels, not paths.
References contain only lowercase SHA-256 and byte count; runtime derives their
location inside the configured store. Regular-file, no-follow, bounded reads reject
symlinks/path references and unavailable or changed bytes. This is local content
integrity, not authenticity, process-image attestation or protection from an
operator controlling the entire application/account.

The registration key hashes canonical `{family_id, version_label}`. Content identity
hashes the manifest's complete `content` (including version label, ordered plan,
source/evidence class and original-byte references). The manifest has its own byte
hash. No timestamps/salts/counters affect these identities. Re-registering identical
bytes under the same label is idempotent; conflicting bytes raise
`provider_store_version_conflict`. New versions require a new explicit label;
there is no implicit latest version or overwrite. Saved reports retain content,
manifest, registration and source identities even after files disappear.

Fsynced blobs are published without overwrite, then complete storage reconstruction
and the projected whole-repository read budget (including manifest bytes) are
checked before the fsynced manifest is linked atomically **last**. A nonblocking
advisory directory lock serializes operator registrations; a competing writer
receives `provider_store_busy`, with no retry or stale lock file. Use one store
instance per caller. Pending files/unreferenced blobs are ignored; interruption
before publication cannot expose a partial version. Orphan cleanup/backup/remote
replication is not implemented. All request/cell slots must be declared; partial
observations and explicit unknown slots are retainable, without an approval flag.
The existing 64-cell, 2MiB result/preimage, 16MiB capture/cell, 64MiB retained
result+capture/family and 4MiB provenance/family budgets remain. Storage additionally
bounds manifests to2MiB, versions/store to64, provenance files/family to64, capture
files/cell to7 and a repository read to128MiB. These are software resource limits,
not a new numerical acceptance policy.

Unset configuration, missing store, malformed manifest, changed/missing blob,
retention budget and absent applicable family produce specific diagnostics; no
hidden provider or BEM call follows. One malformed/corrupt stored version makes
repository loading fail closed, rather than silently omitting it. Runtime loading
reconstructs the typed repository, not a persisted accepted boolean. The reviewed
admission path still checks coordinates, exact declared requests/provider/policy,
script/input/receipts/parsed points and complete family coverage.

### UI binding and demonstrated scope

The existing no-upload route uses the configured loader. After explicit root
inputs, it lists candidate versions and their current preparation status using
the same admission service. Complete candidates, incomplete/rejected records and
missing applicable data remain distinct. Users explicitly select a stored version,
confirm preparation and execute. No user CAD, polar JSON, manifest or path field
is added. Five catalog profiles remain selectable; changing profiles resets the
version selection and active output without changing saved snapshots.

Selections bind content identity separately from prepared/executed identities.
Preparation and explicit execution reopen the selected manifest/blobs and compare
the original binding even when a caller supplies a cached repository. Changed,
removed or corrupted selected records invalidate active preparation/result and
block a stale solve. An added version never replaces a selected version. UI removal
clears the selection and reports `selected_version_unavailable`. These checks are
file observations, not a transactional lock against a hostile concurrent writer.

[Store tests](../tests/application/test_provider_record_store.py) demonstrate actual
serialization → close/reopen → configured application load → preparation → explicit
**inert** BEM for all five profiles. No loader monkeypatch supplies those families.
Persistent AppTests exercise the same configured loader, explicit version choice,
profile switching, corruption/removal invalidation and saved attribution. They
block genuine provider/banner/BEM entry points. The original actual negative
fixture separately round-trips byte-for-byte:35/37, +32°/−38° unavailable, seven
source-bound unlaunched cells. Separate unknown-status slots remain unknown.
It admits no complete applicable family and reaches no BEM. The original execution
archive SHA-256 remains
`e779bb00158571541a10419ecccb011fc1c8a5ea32cad40a59e005c59f9082e9`.

Provider records persist locally. **Comparison/user-result history remains
session-scoped**; saved snapshots are immutable within the existing session/export
contract, not a new durable user-history service. Genuine single-case BEM evidence
and genuine distinct-profile comparison remain unestablished; `physical_qualification=false`.

## 2026-11-09 — NACA4412 catalog append compatibility

NACA4412 is now the sixth selectable project profile under the
[coordinate contract](py02_profile_coordinate_identity.md#2026-11-09--sixth-selectable-profile-naca4412).
This is geometry/software availability, not numerical-data readiness. All
existing root, longer-proximal, exact request/capture, complete-family, policy,
stored-version, explicit-execution and distinct-coordinate comparison gates
apply unchanged. No accepted production family is added.

Appending the manifest changes new draft metadata/identity for all six profiles,
while original five coordinate bytes and provider request preimages remain
unchanged. Existing persistent records and saved snapshots are not rewritten.
The pre-append PR108 inert compatibility fixture proves old record bytes and
JSON/CSV attribution survive reopening, and fresh admission can use that old
matching family with the current draft. Old active preparations cannot be
silently reused. A missing family gives a specific UI diagnostic with no active
result or run action; when an explicit attempted family selection reaches the
application boundary, its rejection snapshot retains attribution and null totals.
No undeclared family or policy is fabricated just to create a UI rejection record.
Normal users still do not supply CAD/polar/manifest/path files. Comparison history
remains session-scoped; this increment adds no persistence layer or acquisition.
