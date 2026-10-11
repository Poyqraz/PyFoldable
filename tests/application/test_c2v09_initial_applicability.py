"""Applicability dossier. The evaluator is not called."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pyfoldable.application.c2v09_initial_applicability import (
    ACCEPTED_REPAIR_HEAD,
    build_applicability_dossier,
    classify_implementation_change,
    declare_initial_operation_graph,
)
from pyfoldable.application.c2v09_cosine_path_certificate import (
    call_edges_from_loaded_bytes,
    observe_ulp_terminal_guard,
)
from pyfoldable.application.c2v09_declared_operations import REQUIRED_GRAPH_QUALNAMES
from pyfoldable.application.c2v09_initial_call_binding import bind_initial_call, revalidate_initial_call_binding
from pyfoldable.application.c2v09_pre_call_admission import prepare_pre_call_admission
from pyfoldable.application.c2v09_pre_call_package import (
    PRE_CALL_READY,
    UNRESOLVED,
    _label,
    prepare_pre_call_package,
)
from pyfoldable.application.c2v09_pre_call_binding import observe_pre_call_binding
from pyfoldable.core.foldable_rotor import FoldableRotorState
from pyfoldable.core.models import BladeGeometry
import pyfoldable.core.foldable_rotor as foldable_rotor


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def _native_unavailable(_root):
    return {
        "canonical_payload": {
            "selected_call_target": {"classification": "NOT ESTABLISHED"},
            "cosine_function_calls": 0,
            "eligibility_evidence": False,
        }
    }


def _observer(root):
    return observe_pre_call_binding(root, cosine_observer=_native_unavailable)


def _collector(_root):
    return {"canonical_payload": {"executing_dependencies": {}, "observations": {}, "source_callbacks": 0}}


def _native_double(_root):
    return {"canonical_payload": {"cosine_function_calls": 0, "compiled_probe_image_sha256": "ab" * 32}}


def _bind():
    admission = prepare_pre_call_admission(
        _repository(),
        pre_call_observer=_observer,
        dependency_collector=_collector,
    )
    return bind_initial_call(_repository(), admission=admission, native_observer=_native_double)


def test_declared_graph_separates_geometry_from_bem_numerics() -> None:
    graph = declare_initial_operation_graph(_repository())
    by_name = {row["qualname"]: row for row in graph}
    projection = by_name["project_foldable_blade"]
    numerical = by_name["solve_bem_rotor"]
    guard = by_name["math.ulp"]
    assert projection["family"] == "geometric lemma"
    assert projection["bem_numerical_dependency"] is False
    assert projection["module_digest_clears_this_row"] is False
    assert projection["filename_clears_this_row"] is False
    assert numerical["family"] == "bem numerical dependency"
    assert numerical["geometric_lemma"] is False
    assert numerical["every_angle_convergence_theorem"] is False
    assert "convergence" in str(numerical["proof_role"])
    assert by_name["solve_bem_rotor.midpoint"]["family"] == "geometric lemma"
    assert by_name["solve_bem_rotor.annulus_edge"]["family"] == "geometric lemma"
    assert by_name["project_foldable_blade.kernel_radius"]["family"] == "geometric lemma"
    assert by_name["BladeGeometry.radius_m"]["classification"] == "MATCH"
    assert set(REQUIRED_GRAPH_QUALNAMES) <= set(by_name)
    assert guard["classification"] == "NOT ESTABLISHED"
    assert guard["calls"] == 0
    assert guard["historical_equality_assumed"] is False
    assert all(row["module_digest_clears_this_row"] is False for row in graph)


def test_unreviewed_byte_change_is_not_a_reviewed_rebinding() -> None:
    pending = classify_implementation_change("aa" * 32, "bb" * 32)
    assert pending["relation"] == "CHANGED / REVIEW PENDING"
    assert pending["runtime_transfer_approved"] is False
    assert pending["clears_runtime_differences"] is False
    other = classify_implementation_change("cc" * 32, "dd" * 32)
    assert other["relation"] == "CHANGED / REVIEW PENDING"
    reviewed = classify_implementation_change(
        "aa" * 32,
        "bb" * 32,
        review_binding={"current_digest": "aa" * 32, "scope": "certificate source text only"},
    )
    assert reviewed["relation"] == "REVIEWED REBINDING"
    assert reviewed["review_scope"] == "certificate source text only"
    assert reviewed["runtime_transfer_approved"] is False
    mismatched_review = classify_implementation_change(
        "ee" * 32,
        "bb" * 32,
        review_binding={"current_digest": "aa" * 32, "scope": "certificate source text only"},
    )
    assert mismatched_review["relation"] == "CHANGED / REVIEW PENDING"


def test_stale_binding_is_not_a_current_observation() -> None:
    bound = _bind()
    bound.native_observation = {
        "kind": "genuine",
        "measurement_image": {
            "handle_associated": True,
            "loaded_code_correspondence": "MATCH",
            "file_image_identity": "OBSERVED",
            "file_image_sha256": "ab" * 32,
            "second_compilation_is_evidence": False,
            "source_hash_is_the_image": False,
        },
        "cosine_function_calls": 0,
    }
    bound.pid = bound.pid + 1
    dossier = build_applicability_dossier(_repository(), binding=bound)
    assert dossier["binding_revalidation"] == "INVALIDATED"
    assert dossier["genuine_runtime_observations"]["current"] is False
    assert dossier["genuine_runtime_observations"]["loaded_code_correspondence"] != "MATCH"
    retained = dossier["retained_observation"]
    assert retained["role"] == "historical/unvalidated"
    assert retained["original_pid"] == bound.pid
    assert retained["measurement_image"]["loaded_code_correspondence"] == "MATCH"
    serialized = build_applicability_dossier(_repository(), binding={"kind": "archived"})
    assert serialized["binding_revalidation"] == "NOT ESTABLISHED"
    assert serialized["serialized_record_is_a_live_binding"] is False
    assert serialized["genuine_runtime_observations"]["current"] is False
    assert serialized["authorizes_execution"] is False


def test_dossier_blocks_unresolved_items_and_rejects_test_doubles() -> None:
    bound = _bind()
    dossier = build_applicability_dossier(_repository(), binding=bound)
    assert dossier["status"] == "CONTRACT BLOCKED"
    assert dossier["authorizes_execution"] is False
    assert dossier["eligibility_evidence"] is False
    assert dossier["physical_qualification"] is False
    assert dossier["candidate29_disposition"] == "NOT SELECTED"
    assert dossier["accepted_repair"]["head"] == ACCEPTED_REPAIR_HEAD
    assert dossier["time_s"] == "0x0.0p+0"
    assert dossier["post_return"]["returned_source_object"] == "POST-RETURN ONLY"
    assert dossier["post_return"]["mapped_interval_consumption"] == "POST-RETURN ONLY"
    assert dossier["dependent_counters"]["source"] == 0
    assert dossier["genuine_runtime_observations"]["kind"] == "test_double"
    assert dossier["genuine_runtime_observations"]["measurement_image"]["file_image_identity"] == "NOT ESTABLISHED"
    assert dossier["genuine_runtime_observations"]["loaded_code_correspondence"] == "NOT ESTABLISHED"
    assert dossier["genuine_runtime_observations"]["test_double_is_measurement_evidence"] is False
    assert dossier["genuine_runtime_observations"]["archived_json_is_measurement_evidence"] is False
    assert dossier["archived_record_authorizes_later_process"] is False
    assert dossier["historical_certificate_hypotheses"]["exact_equality_assumed"] is False
    assert dossier["historical_certificate_hypotheses"]["implementation"]["clears_runtime_differences"] is False
    assert dossier["historical_certificate_hypotheses"]["implementation"]["runtime_transfer_approved"] is False
    assert dossier["historical_certificate_hypotheses"]["implementation"]["relation"] == "CHANGED / REVIEW PENDING"
    assert dossier["deferred_radau_is_prerequisite_for_isolated_source_attempt"] is False
    assert dossier["post_return_demanded_before_existence"] is False
    timed = {row["name"]: row for row in dossier["unmet_hypotheses"]}
    assert timed["returned source object"]["timing"] == "POST-RETURN ONLY"
    assert timed["returned source object"]["demanded_before_it_exists"] is False
    assert timed["solve_cmm2_transient"]["timing"] == "deferred integration"
    assert timed["solve_cmm2_transient"]["prerequisite_for_isolated_source_attempt"] is False
    assert timed["returned source object"]["timing"] == "POST-RETURN ONLY"
    assert dossier["current_implementation"]["module_digest_clears_any_row"] is False
    names = {row["name"] for row in dossier["unmet_hypotheses"]}
    assert "returned source object" in names
    assert "time_s" not in names
    assert "math.ulp" in names
    assert bound.evaluator.successful_bem_solves == 0
    assert bound.evaluator.successful_map_calls == 0


def test_package_keeps_file_mismatches_and_does_not_authorize_execution() -> None:
    package = prepare_pre_call_package(_repository(), binding=_bind())
    payload = package["canonical_payload"]
    assert "canonical_sha256" not in payload
    assert package["authorizes_execution"] is False
    assert package["revalidation"] == "REVALIDATED"
    assert payload["time_s"] == "0x0.0p+0"
    assert payload["time_declaration"]["knot_is_sole_authority"] is False
    assert payload["deferred_radau_is_prerequisite_for_isolated_source_attempt"] is False
    assert payload["post_return_demanded_before_existence"] is False
    assert payload["future_v2_seal_required"] is False
    assert payload["every_angle_bem_convergence_required"] is False
    assert payload["geometric_applicability_argument"]["code_identity_is_lemma_transfer"] is False
    assert payload["geometric_applicability_argument"]["bem_numerical_success_reuses_geometric_proof"] is False
    assert payload["ulp_terminal_guard"]["ulp_function_calls"] == 0
    assert payload["ulp_terminal_guard"]["output_sampled"] is False
    assert payload["historical_file_deltas"]
    assert all(row["waived"] is False and row["hash_relabelled"] is False for row in payload["historical_file_deltas"])
    assert all(row["settles_applicability"] is False for row in payload["runtime_dispositions"])
    assert package["label"] == UNRESOLVED
    names = {row["name"] for row in payload["unresolved_pre_call"]}
    assert "native observation" in names
    assert payload["unresolved_pre_call"]
    assert package["binding"].evaluator.successful_bem_solves == 0


def test_replaced_angle_property_is_not_the_import_time_getter() -> None:
    original = FoldableRotorState.__dict__["angle_from_deployed_rad"]

    def other(self):
        return self.opening_angle_rad

    try:
        FoldableRotorState.angle_from_deployed_rad = property(other)
        row = next(
            item
            for item in declare_initial_operation_graph(_repository())
            if item["qualname"] == "FoldableRotorState.angle_from_deployed_rad"
        )
        assert row["classification"] != "MATCH"
    finally:
        FoldableRotorState.angle_from_deployed_rad = original


def test_replaced_helper_is_not_the_import_time_callable() -> None:
    original = foldable_rotor._station_at_hinge

    def other(*_args, **_kwargs):
        raise AssertionError("helper evaluated")

    try:
        foldable_rotor._station_at_hinge = other
        row = next(
            item
            for item in declare_initial_operation_graph(_repository())
            if item["qualname"] == "_station_at_hinge"
        )
        assert row["classification"] != "MATCH"
    finally:
        foldable_rotor._station_at_hinge = original


def test_replaced_radius_property_is_not_established_by_a_stale_descriptor() -> None:
    original = BladeGeometry.__dict__["radius_m"]

    def other(self):
        return self.diameter_m

    try:
        BladeGeometry.radius_m = property(other)
        rows = {
            item["qualname"]: item
            for item in declare_initial_operation_graph(_repository())
        }
        assert "BladeGeometry.radius_m" in rows
        assert rows["BladeGeometry.radius_m"]["classification"] != "MATCH"
    finally:
        BladeGeometry.radius_m = original


def test_property_or_getter_replacement_invalidates_the_binding() -> None:
    bound = _bind()
    descriptor = FoldableRotorState.__dict__["angle_from_deployed_rad"]
    getter = descriptor.fget
    original_code = getter.__code__

    def other(self):
        return 0.0

    try:
        getter.__code__ = other.__code__
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        getter.__code__ = original_code
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"
    try:
        FoldableRotorState.angle_from_deployed_rad = property(other)
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        FoldableRotorState.angle_from_deployed_rad = descriptor
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"
    original_helper = foldable_rotor._station_at_hinge

    def helper(*_args, **_kwargs):
        raise AssertionError("helper evaluated")

    try:
        foldable_rotor._station_at_hinge = helper
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        foldable_rotor._station_at_hinge = original_helper
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"


def test_geometric_mismatch_and_missing_rows_stay_unresolved() -> None:
    graph = [
        {
            "qualname": "FoldableRotorState.angle_from_deployed_rad",
            "family": "geometric lemma",
            "classification": "MISMATCH",
        },
        {
            "qualname": "solve_bem_rotor",
            "family": "bem numerical dependency",
            "classification": "MISMATCH",
        },
    ]
    label, unresolved = _label(False, graph, {"wrapper_address": "0x1"})
    assert label == UNRESOLVED
    named = {row["name"]: row for row in unresolved}
    assert named["FoldableRotorState.angle_from_deployed_rad"]["missing"] == "loaded code identity"
    assert named["solve_bem_rotor"]["missing"] == "loaded code identity"
    assert "convergence" not in named["solve_bem_rotor"]["missing"]
    assert "solve_bem_rotor.midpoint" in named
    assert named["solve_bem_rotor.midpoint"]["missing"] == "required graph row"
    assert "solve_bem_rotor.annulus_edge" in named
    assert "project_foldable_blade.kernel_radius" in named
    assert "BladeGeometry.radius_m" in named


def test_wrapper_address_does_not_establish_the_loaded_nextafter_path() -> None:
    label, unresolved = _label(False, [], {"wrapper_address": "0x1"})
    assert label == UNRESOLVED
    assert any(row["name"] == "math.ulp" and "nextafter" in str(row["missing"]) for row in unresolved)
    observed = observe_ulp_terminal_guard()
    assert observed["wrapper_address_establishes_path"] is False
    assert observed["ulp_function_calls"] == 0
    assert observed["nextafter_function_calls"] == 0
    assert observed["output_sampled"] is False
    assert observed["selected_nextafter"] != "OBSERVED IN WRAPPER DISASSEMBLY"
    assert observed["disk_disassembly_is_proof"] is False


def test_loaded_call_edges_are_decoded_from_loaded_bytes() -> None:
    edges = call_edges_from_loaded_bytes(bytes.fromhex("e800000000"), 0x1000)
    assert edges == [
        {
            "kind": "direct",
            "opcode": "e8",
            "offset": 0,
            "target": hex(0x1005),
            "source": "loaded bytes",
        }
    ]
    got = call_edges_from_loaded_bytes(bytes.fromhex("ff1500000000"), 0x2000)
    assert got[0]["kind"] == "indirect"
    assert got[0]["opcode"] == "ff15"
    assert got[0]["target"] == hex(0x2006)
    assert got[0]["source"] == "loaded bytes"


def _ready_graph() -> list[dict[str, object]]:
    rows = []
    for qualname in REQUIRED_GRAPH_QUALNAMES:
        if qualname == "solve_bem_rotor":
            family = "bem numerical dependency"
        elif qualname in {"math.ulp", "_native_terminal_annuli"}:
            family = "native terminal guard"
        elif qualname in {
            "Cmm2FoldableBemMappedAeroEvaluator.__init__",
            "Cmm2FoldableBemMappedAeroEvaluator.__call__",
            "solve_foldable_bem_rotor",
            "map_foldable_bem_aero_loads",
            "load_design_config",
        }:
            family = "transaction"
        else:
            family = "geometric lemma"
        rows.append(
            {
                "qualname": qualname,
                "family": family,
                "classification": "NOT ESTABLISHED" if qualname == "math.ulp" else "MATCH",
            }
        )
    return rows


def _ready_ulp() -> dict[str, object]:
    return {
        "ulp_function_calls": 0,
        "nextafter_function_calls": 0,
        "output_sampled": False,
        "wrapper_address": "0x10",
        "wrapper_address_establishes_path": False,
        "disk_disassembly_is_proof": False,
        "loaded_wrapper_matches_file": True,
        "loaded_wrapper_bytes_hex": "aa",
        "loaded_stub_bytes_hex": "ff25",
        "got_slot": "0x20",
        "selected_address": "0x30",
        "evidence": "loaded wrapper plt got",
        "selected_nextafter": "OBSERVED",
        "call_edges": [
            {
                "source": "loaded bytes",
                "loaded_bytes_match_file": True,
                "disk_disassembly_is_proof": False,
            }
        ],
    }


def _ready_native() -> dict[str, object]:
    symbol = {
        "correspondence": "MATCH",
        "whole_elf": False,
        "disk_disassembly_is_proof": False,
        "call_edges_decoded_from_loaded_bytes": True,
        "call_edges": [],
        "file_bytes_hex": "aa",
        "loaded_bytes_hex": "aa",
        "address_to_elf": {"mapped_file": "/tmp/probe.so", "runtime_address": "0x1000", "file_offset": 128},
    }
    return {
        "kind": "genuine",
        "measurement_image": {
            "loaded_code_correspondence": "NOT ESTABLISHED",
            "correspondence_coverage": "entrypoint prefix",
            "consumed_instruction_ranges": [
                {**symbol, "name": "read_state"},
                {**symbol, "name": "xcr0_read_permitted", "file_bytes_hex": "bb", "loaded_bytes_hex": "bb"},
            ],
        },
        "runtime_correspondence": {
            "disk_disassembly_is_proof": False,
            "whole_elf_required": False,
            "cosine": {
                "loaded_wrapper_matches_file": True,
                "loaded_wrapper_bytes_hex": "cc",
                "file_wrapper_bytes_hex": "cc",
                "conversion": {
                    "classification": "OBSERVED",
                    "source": "loaded bytes",
                    "loaded_bytes_match_file": True,
                    "disk_disassembly_is_proof": False,
                },
                "plt_stub_bytes_hex": "ff25",
                "got_slot": "0x40",
                "selected_address": "0x50",
                "evidence": "python wrapper plt got",
                "selected_classification": "OBSERVED",
                "body_bytes_hex": "dd",
                "body_sha256": "ab" * 32,
                "constants": [{"classification": "MATCH"}],
                "controls_classification": "OBSERVED",
                "cosine_function_calls": 0,
                "disk_disassembly_is_proof": False,
                "libm_body_argument": "DOES NOT APPLY",
            },
        },
    }


def _ready_context() -> dict[str, object]:
    return {
        "native": _ready_native(),
        "dispositions": [
            {"name": name, "classification": "MISMATCH", "settles_applicability": False}
            for name in ("historical XCR0", "historical wrapper", "CPython executable", "loader", "libm")
        ],
        "file_deltas": [
            {
                "path": path,
                "file_identity": "MISMATCH",
                "waived": False,
                "hash_relabelled": False,
                "mismatch_preserved": True,
                "initial_operation_reuse": "narrow initial-operation reuse",
            }
            for path in (
                "pyfoldable/application/cmm2_coupled_transient_service.py",
                "pyfoldable/dynamics/cmm2_coupled_transient.py",
            )
        ],
        "interpreter_arithmetic": {
            "output_sampled": False,
            "same_recording_as_probe": True,
            "controls_classification": "OBSERVED",
            "operations": [
                {"qualname": qualname, "co_code_hex": "aa", "output_sampled": False}
                for qualname in (
                    "FoldableRotorState.angle_from_deployed_rad",
                    "BladeGeometry.radius_m",
                    "project_foldable_blade.kernel_radius",
                    "solve_bem_rotor.annulus_edge",
                    "solve_bem_rotor.midpoint",
                )
            ],
        },
    }


def test_complete_evidence_is_ready_and_a_missing_byte_is_not() -> None:
    context = _ready_context()
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)
    assert label == PRE_CALL_READY
    assert unresolved == []
    native = _ready_native()
    native["measurement_image"]["consumed_instruction_ranges"][0]["file_bytes_hex"] = ""
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **{**context, "native": native})
    assert label == UNRESOLVED
    assert any(row["name"] == "read_state" for row in unresolved)
    native = _ready_native()
    native["measurement_image"]["loaded_code_correspondence"] = "MATCH"
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **{**context, "native": native})
    assert label == UNRESOLVED
    assert any(row["name"] == "loaded probe image" for row in unresolved)


def test_package_names_a_geometric_mismatch_and_keeps_time_controls() -> None:
    bound = _bind()
    original = FoldableRotorState.__dict__["angle_from_deployed_rad"]

    def other(self):
        return 0.0

    try:
        FoldableRotorState.angle_from_deployed_rad = property(other)
        package = prepare_pre_call_package(_repository(), binding=bound)
    finally:
        FoldableRotorState.angle_from_deployed_rad = original
    assert package["label"] == UNRESOLVED
    assert package["authorizes_execution"] is False
    payload = package["canonical_payload"]
    assert payload["time_s"] == "0x0.0p+0"
    assert payload["time_declaration"]["conflict"] is False
    assert payload["every_angle_bem_convergence_required"] is False
    names = {row["name"] for row in payload["unresolved_pre_call"]}
    assert "FoldableRotorState.angle_from_deployed_rad" in names
    assert "native observation" in names


def test_historical_capsule_bytes_remain_the_earlier_record() -> None:
    path = _repository() / "reports/c2v09_pre_call_capsule/capsule.json"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == "09f7df71697528333be1674fde6419bbeadeec084213274c2eab3ee7abb6649a"
