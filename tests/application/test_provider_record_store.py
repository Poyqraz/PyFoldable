"""Durable record registration/loading; every positive execution is inert."""
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import tarfile

import pytest

from pyfoldable.application import design_analysis, provider_design_analysis as app
from pyfoldable.application import provider_record_store as storage
from pyfoldable.application.profile_bem_comparison import add_record, comparison_document, comparison_csv
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil
from pyfoldable.providers import xfoil
from test_provider_design_analysis import scenario, install_inert_bem, encoded


@pytest.fixture(autouse=True)
def forbid_genuine_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected genuine provider/BEM/banner call")
    monkeypatch.setattr(xfoil.XfoilProvider, "generate", forbidden)
    monkeypatch.setattr(xfoil, "_discover_backend_version", forbidden)
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", forbidden)


def registered(tmp_path, monkeypatch, profile="NACA0012"):
    selection, repository = scenario(profile)
    root = tmp_path / "store"
    with storage.ProviderRecordStore(root) as store:
        binding = store.register_family(repository.families[0], version_label="inert-v1")
    monkeypatch.setenv(storage.STORE_ENVIRONMENT_VARIABLE, str(root))
    return replace(selection, stored_version_sha256=binding.content_sha256), binding, root


@pytest.mark.parametrize("profile", PROJECT_AIRFOIL_IDS)
def test_round_trip_close_reopen_real_loader_and_explicit_inert_execution(tmp_path, monkeypatch, profile):
    original_selection, original_repo = scenario(profile)
    selection, binding, root = registered(tmp_path, monkeypatch, profile)
    with storage.ProviderRecordStore(root) as reopened:
        loaded = reopened.load_repository()
    family = loaded.families[0]
    assert family.family_id == original_repo.families[0].family_id
    assert family.requests == original_repo.families[0].requests
    assert family.cells == original_repo.families[0].cells
    assert family.provenance_files == original_repo.families[0].provenance_files
    assert family.stored_version == binding
    assert original_selection.draft == selection.draft
    repository = app.application_provider_repository()  # real configured loader, no monkeypatch
    prepared = app.prepare_provider_design_analysis(selection, repository)
    admission = json.loads(prepared.admission_json)
    assert admission["stored_version"]["content_sha256"] == binding.content_sha256
    calls = install_inert_bem(monkeypatch)
    outcome = app.run_provider_design_analysis(prepared, active_selection=selection, repository=repository)
    assert len(calls) == 1 and outcome.record["status"] == "success"
    assert outcome.record["evidence_class"] == "inert_fixture"
    assert outcome.record["physical_qualification"] is False


def test_immutable_versions_are_idempotent_but_conflicts_do_not_overwrite(tmp_path):
    _, repo = scenario()
    with storage.ProviderRecordStore(tmp_path / "store") as store:
        first = store.register_family(repo.families[0], version_label="v1")
        assert store.register_family(repo.families[0], version_label="v1") == first
        changed = replace(repo.families[0], source_identity="different retained source")
        with pytest.raises(storage.ProviderRecordStoreError) as caught:
            store.register_family(changed, version_label="v1")
        assert caught.value.code == "provider_store_version_conflict"
        second = store.register_family(changed, version_label="v2")
        assert second.content_sha256 != first.content_sha256
        assert len(store.load_repository().families) == 2


def test_interrupted_publication_exposes_no_new_version(tmp_path, monkeypatch):
    _, repo = scenario()
    root = tmp_path / "store"
    def interrupted(*args, **kwargs):
        raise OSError("INERT injected interruption before manifest publication")
    monkeypatch.setattr(storage, "_publish_manifest", interrupted)
    with storage.ProviderRecordStore(root) as store:
        with pytest.raises(storage.ProviderRecordStoreError, match="interruption"):
            store.register_family(repo.families[0], version_label="v1")
    with storage.ProviderRecordStore(root) as reopened:
        assert reopened.load_repository().families == ()
    assert list((root / "records").iterdir()) == []


@pytest.mark.parametrize("operation", ["changed_blob", "missing_blob", "removed_manifest", "malformed_manifest"])
def test_stale_selected_version_cannot_execute_and_saved_attribution_survives(tmp_path, monkeypatch, operation):
    selection, binding, root = registered(tmp_path, monkeypatch)
    repository = app.application_provider_repository()
    prepared = app.prepare_provider_design_analysis(selection, repository)
    calls = install_inert_bem(monkeypatch)
    outcome = app.run_provider_design_analysis(prepared, active_selection=selection, repository=repository)
    saved = add_record((), outcome.record)
    saved_bytes = encoded(saved)
    manifest = root / "records" / (binding.registration_key + ".json")
    if operation == "removed_manifest":
        manifest.unlink()
    elif operation == "malformed_manifest":
        manifest.write_bytes(b"{malformed")
    else:
        blob = root / "blobs" / hashlib.sha256(repository.families[0].cells[0].result_json).hexdigest()
        if operation == "missing_blob":
            blob.unlink()
        else:
            blob.write_bytes(b"changed retained bytes")
    with pytest.raises(app.ProviderDesignPreparationError):
        app.run_provider_design_analysis(prepared, active_selection=selection, repository=repository)
    assert len(calls) == 1
    assert encoded(saved) == saved_bytes
    exported = comparison_document(saved, evidence_class="inert_fixture")
    assert saved[0]["report_sha256"] in comparison_csv(exported)
    retained = json.loads(saved[0]["report_text"])["request"]["provider_design_admission"]["stored_version"]
    assert retained["content_sha256"] == binding.content_sha256


def test_new_version_does_not_replace_a_selected_version(tmp_path, monkeypatch):
    selection, binding, root = registered(tmp_path, monkeypatch)
    repository = app.application_provider_repository()
    prepared = app.prepare_provider_design_analysis(selection, repository)
    with storage.ProviderRecordStore(root) as store:
        family = replace(repository.families[0], stored_version=None, source_identity="second version")
        second = store.register_family(family, version_label="inert-v2")
    refreshed = app.application_provider_repository()
    assert len(refreshed.families) == 2
    assert app.prepare_provider_design_analysis(selection, refreshed).request_sha256 == prepared.request_sha256
    with pytest.raises(app.ProviderDesignPreparationError, match="version"):
        app.prepare_provider_design_analysis(replace(selection, stored_version_sha256=None), refreshed)
    (root / "records" / (binding.registration_key + ".json")).unlink()
    with pytest.raises(app.ProviderDesignPreparationError):
        app.prepare_provider_design_analysis(selection, app.application_provider_repository())
    assert second.content_sha256 != binding.content_sha256


@pytest.mark.parametrize("kind", ["unset", "missing", "malformed"])
def test_configured_loader_has_specific_diagnostics(tmp_path, monkeypatch, kind):
    root = tmp_path / "store"
    if kind == "unset":
        monkeypatch.delenv(storage.STORE_ENVIRONMENT_VARIABLE, raising=False)
        code = "provider_store_not_configured"
    else:
        monkeypatch.setenv(storage.STORE_ENVIRONMENT_VARIABLE, str(root))
        code = "provider_store_missing"
        if kind == "malformed":
            selection, binding, root = registered(tmp_path, monkeypatch)
            (root / "records" / (binding.registration_key + ".json")).write_text("{}")
            code = "provider_store_manifest_malformed"
    with pytest.raises(storage.ProviderRecordStoreError) as caught:
        app.application_provider_repository()
    assert caught.value.code == code


def test_blob_symlink_and_path_reference_cannot_escape_store(tmp_path, monkeypatch):
    selection, binding, root = registered(tmp_path, monkeypatch)
    family = app.application_provider_repository().families[0]
    digest = hashlib.sha256(family.cells[0].result_json).hexdigest()
    outside = tmp_path / "outside.json"
    outside.write_bytes(family.cells[0].result_json)
    blob = root / "blobs" / digest
    blob.unlink()
    blob.symlink_to(outside)
    with pytest.raises(storage.ProviderRecordStoreError):
        app.application_provider_repository()
    assert outside.read_bytes() == family.cells[0].result_json


def test_genuine_partial_records_round_trip_without_repair_or_admission(tmp_path, monkeypatch):
    archive = Path("tests/fixtures/provider_design_analysis/partial_xfoil_20261106.tar.gz")
    original_fixture_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    with tarfile.open(archive) as tar:
        retained = {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
    result_bytes = retained["run/result-00.json"]
    actual = app._result(json.loads(result_bytes))
    from pyfoldable.application.polar_query_feasibility import declared_probe_requests, _declared_provider
    experiment = json.loads(Path("reports/polar_query_feasibility/report.json").read_text())["recommended_experiment"]
    requests = declared_probe_requests(experiment, {p: load_project_airfoil(p) for p in ("NACA0012", "NACA2412")})
    provider = _declared_provider(experiment)
    cell = app.RetainedCell(result_bytes, tuple((n.rsplit("/", 1)[1], b) for n, b in retained.items() if "/capture/" in n))
    source = "original execution archive sha256:e779bb00158571541a10419ecccb011fc1c8a5ea32cad40a59e005c59f9082e9"
    not_launched = app.UnlaunchedCell("Reviewed driver stopped after partial cell00", source + "; execution-summary.json")
    families = (
        app.ManagedProviderFamily("actual-NACA0012", provider, requests[:4], (cell, not_launched, not_launched, not_launched), "caller_supplied_unqualified", source, (("execution-summary.json", retained["execution-summary.json"]),)),
        app.ManagedProviderFamily("actual-NACA2412", provider, requests[4:], (not_launched,) * 4, "caller_supplied_unqualified", source, (("execution-summary.json", retained["execution-summary.json"]),)),
    )
    root = tmp_path / "store"
    bindings = []
    with storage.ProviderRecordStore(root) as store:
        for family in families:
            bindings.append(store.register_family(family, version_label="2026-11-06-original-negative"))
        # Separate unknown-status software witness, never relabeling an actual cell.
        unknown = replace(families[1], family_id="unknown-launch-status-witness", cells=(None,) * 4,
                          evidence_class="inert_fixture", source_identity="INERT unknown-status persistence witness; no launch assertion",
                          provenance_files=(("inert-declaration.txt", b"INERT unknown slots; not an observation of the completed probe"),))
        store.register_family(unknown, version_label="unknown")
    monkeypatch.setenv(storage.STORE_ENVIRONMENT_VARIABLE, str(root))
    reopened = app.application_provider_repository()
    loaded = next(f for f in reopened.families if f.family_id == families[0].family_id)
    assert loaded.cells[0].result_json == result_bytes
    assert loaded.cells[0].capture_files == cell.capture_files
    assert sum(isinstance(c, app.UnlaunchedCell) for f in reopened.families for c in f.cells) == 7
    assert sum(c is None for f in reopened.families for c in f.cells) == 4
    assert sum(p.usable for p in actual.points) == 35
    assert [round(math.degrees(p.alpha_rad)) for p in actual.points if p.cl is None] == [32, -38]
    for family, binding in zip(families, bindings):
        selection, _ = scenario(family.requests[0].airfoil.id)
        selection = replace(selection, family_id=family.family_id, stored_version_sha256=binding.content_sha256,
                            provider_policy_json=app._json(app.request_policy(family.requests[0], family.provider)))
        with pytest.raises(app.ProviderDesignPreparationError):
            app.prepare_provider_design_analysis(selection, reopened)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == original_fixture_sha


def test_manifest_reference_is_content_only_even_with_recomputed_digest(tmp_path, monkeypatch):
    _, binding, root = registered(tmp_path, monkeypatch)
    path = root / "records" / (binding.registration_key + ".json")
    doc = json.loads(path.read_bytes())
    doc["content"]["cells"][0]["result"]["sha256"] = "../../outside"
    doc["content_sha256"] = hashlib.sha256(app._json(doc["content"]).encode()).hexdigest()
    path.write_text(app._json(doc))
    with pytest.raises(storage.ProviderRecordStoreError) as caught:
        app.application_provider_repository()
    assert caught.value.code == "provider_store_manifest_malformed"


def test_existing_byte_budget_and_request_preimages_are_preserved(tmp_path, monkeypatch):
    selection, binding, root = registered(tmp_path, monkeypatch)
    repository = app.application_provider_repository()
    family = repository.families[0]
    manifest = json.loads((root / "records" / (binding.registration_key + ".json")).read_bytes())
    for descriptor, request in zip(manifest["content"]["requests"], family.requests):
        raw = (root / "blobs" / descriptor["preimage"]["sha256"]).read_bytes()
        assert raw == xfoil._request_preimage(request, family.provider)
        assert hashlib.sha256(raw).hexdigest() == request.cache_key(family.provider)
    oversized = replace(family.cells[0], result_json=b"x" * (2 * 1024 * 1024 + 1))
    with storage.ProviderRecordStore(root) as store:
        with pytest.raises(storage.ProviderRecordStoreError) as caught:
            store.register_family(replace(family, cells=(oversized,) + family.cells[1:]), version_label="oversized")
        assert caught.value.code == "provider_store_retention_budget"
        assert len(store.load_repository().families) == 1


def test_active_adapter_clears_preparation_and_result_on_disk_removal(tmp_path, monkeypatch):
    selection, binding, root = registered(tmp_path, monkeypatch)
    repository = app.application_provider_repository()
    state = {}
    app.prepare_active_provider_design(state, selection, repository)
    calls = install_inert_bem(monkeypatch)
    outcome = app.run_active_provider_design(state, selection, repository)
    saved = add_record((), outcome.record)
    (root / "records" / (binding.registration_key + ".json")).unlink()
    with pytest.raises(storage.ProviderRecordStoreError):
        app.run_active_provider_design(state, selection, repository)
    assert app.ACTIVE_REQUEST not in state and app.ACTIVE_OUTCOME not in state
    assert calls and len(calls) == 1
    assert saved[0]["report_sha256"] == outcome.record["report_sha256"]


@pytest.mark.parametrize("fault", ["provider_type", "read_budget"])
def test_registration_reconstruction_failure_is_not_published(tmp_path, monkeypatch, fault):
    _, repository = scenario()
    family = repository.families[0]
    if fault == "provider_type":
        family = replace(family, provider=replace(family.provider, backend_version=7))
    else:
        monkeypatch.setattr(storage, "_MAX_LOAD_BYTES", 100)
    root = tmp_path / "store"
    with storage.ProviderRecordStore(root) as store:
        with pytest.raises(storage.ProviderRecordStoreError):
            store.register_family(family, version_label="must-not-publish")
    assert list((root / "records").iterdir()) == []
    with storage.ProviderRecordStore(root) as reopened:
        assert reopened.load_repository().families == ()


def test_removal_between_active_preparation_and_fresh_execution_clears_state(tmp_path, monkeypatch):
    selection, binding, root = registered(tmp_path, monkeypatch)
    repository = app.application_provider_repository()
    state = {}
    app.prepare_active_provider_design(state, selection, repository)
    original = storage.ProviderRecordStore.load_version
    reads = []
    def remove_before_second_read(store, key, **kwargs):
        reads.append(key)
        if len(reads) == 2:
            (root / "records" / (binding.registration_key + ".json")).unlink()
        return original(store, key, **kwargs)
    monkeypatch.setattr(storage.ProviderRecordStore, "load_version", remove_before_second_read)
    with pytest.raises(storage.ProviderRecordStoreError):
        app.run_active_provider_design(state, selection, repository)
    assert app.ACTIVE_REQUEST not in state
    assert app.ACTIVE_OUTCOME not in state


def test_rejected_registration_preserves_previously_usable_store(tmp_path):
    _, repository = scenario()
    family = repository.families[0]
    root = tmp_path / "store"
    with storage.ProviderRecordStore(root) as store:
        good = store.register_family(family, version_label="good")
        original = {p.name: p.read_bytes() for p in (root / "records").iterdir()}
        malformed = replace(family, provider=replace(family.provider, name=7), cells=(None,) * 4)
        with pytest.raises(storage.ProviderRecordStoreError):
            store.register_family(malformed, version_label="rejected")
    assert {p.name: p.read_bytes() for p in (root / "records").iterdir()} == original
    with storage.ProviderRecordStore(root) as reopened:
        assert reopened.load_repository().families[0].stored_version == good


def test_manifest_and_projected_repository_read_budget_precede_publication(tmp_path, monkeypatch):
    _, repository = scenario()
    family = repository.families[0]
    with storage.ProviderRecordStore(tmp_path / "sizing") as store:
        binding = store.register_family(family, version_label="v1")
    manifest_bytes = (tmp_path / "sizing" / "records" / (binding.registration_key + ".json")).read_bytes()
    def referenced_bytes(value):
        if isinstance(value, dict):
            if set(value) == {"sha256", "byte_count"}:
                return value["byte_count"]
            return sum(referenced_bytes(v) for v in value.values())
        return sum(referenced_bytes(v) for v in value) if isinstance(value, list) else 0
    runtime_cost = len(manifest_bytes) + referenced_bytes(json.loads(manifest_bytes))
    with monkeypatch.context() as budget:
        budget.setattr(storage, "_MAX_LOAD_BYTES", runtime_cost - 1)
        root = tmp_path / "manifest-budget"
        with storage.ProviderRecordStore(root) as store:
            with pytest.raises(storage.ProviderRecordStoreError, match="budget"):
                store.register_family(family, version_label="v1")
        assert list((root / "records").iterdir()) == []
    with monkeypatch.context() as budget:
        budget.setattr(storage, "_MAX_LOAD_BYTES", 2 * runtime_cost - 1)
        root = tmp_path / "repository-budget"
        with storage.ProviderRecordStore(root) as store:
            first = store.register_family(family, version_label="v1")
            with pytest.raises(storage.ProviderRecordStoreError, match="budget"):
                store.register_family(family, version_label="v2")
            loaded = store.load_repository()
        assert len(loaded.families) == 1 and loaded.families[0].stored_version == first


def test_operator_registration_is_nonblocking_and_does_not_publish_while_busy(tmp_path):
    import fcntl
    import os
    _, repository = scenario()
    root = tmp_path / "store"
    with storage.ProviderRecordStore(root) as store:
        first = store.register_family(repository.families[0], version_label="v1")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with storage.ProviderRecordStore(root) as other:
            with pytest.raises(storage.ProviderRecordStoreError) as caught:
                other.register_family(repository.families[0], version_label="v2")
            assert caught.value.code == "provider_store_busy"
    finally:
        os.close(fd)
    with storage.ProviderRecordStore(root) as reopened:
        assert tuple(f.stored_version for f in reopened.load_repository().families) == (first,)


def test_identical_registration_remains_idempotent_at_runtime_read_budget(tmp_path, monkeypatch):
    _, repository = scenario()
    root = tmp_path / "store"
    with storage.ProviderRecordStore(root) as store:
        binding = store.register_family(repository.families[0], version_label="v1")
        store.load_repository()
        exact_runtime_bytes = store._read_bytes  # observe the actual bounded read
    monkeypatch.setattr(storage, "_MAX_LOAD_BYTES", exact_runtime_bytes + 1)
    with storage.ProviderRecordStore(root) as reopened:
        assert reopened.load_repository().families[0].stored_version == binding
        assert reopened.register_family(repository.families[0], version_label="v1") == binding
