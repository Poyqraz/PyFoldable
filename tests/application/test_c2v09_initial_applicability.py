"""Applicability dossier. The evaluator is not called."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pyfoldable.application.c2v09_initial_applicability import (
    ACCEPTED_REPAIR_HEAD,
    build_applicability_dossier,
    classify_implementation_change,
    declare_initial_operation_graph,
)
from pyfoldable.application.c2v09_cosine_path_certificate import (
    assess_helper_connection,
    call_edges_from_loaded_bytes,
    decode_loaded_calls,
    observe_ulp_terminal_guard,
)
from pyfoldable.application.c2v09_ordered_declaration import sha256_bytes
from pyfoldable.application.c2v09_declared_operations import (
    REQUIRED_GRAPH_QUALNAMES,
    arithmetic_operation_record,
    resolve_qualname,
)
from pyfoldable.application.c2v09_initial_call_binding import bind_initial_call, revalidate_initial_call_binding
from pyfoldable.application.c2v09_pre_call_admission import prepare_pre_call_admission
from pyfoldable.application.c2v09_pre_call_package import (
    PRE_CALL_READY,
    UNRESOLVED,
    _constants_identity,
    _helper_call_bound,
    _label,
    _probe_range_gaps,
    prepare_pre_call_package,
)
from pyfoldable.application.c2v09_pre_call_binding import observe_pre_call_binding
from pyfoldable.core.foldable_rotor import FoldableRotorState
from pyfoldable.core.models import BladeGeometry
import pyfoldable.core.bem_rotor as bem_rotor
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
    assert edges[0]["kind"] == "direct"
    assert edges[0]["opcode"] == "e8"
    assert edges[0]["offset"] == 0
    assert edges[0]["target"] == hex(0x1005)
    assert edges[0]["source"] == "loaded bytes"
    got = call_edges_from_loaded_bytes(bytes.fromhex("ff1500000000"), 0x2000)
    assert got[0]["kind"] == "indirect"
    assert got[0]["opcode"] == "ff15"
    assert got[0]["target"] == hex(0x2006)
    assert got[0]["source"] == "loaded bytes"
    assert got[0]["plt_destination"] == hex(0x2006)
    assert got[0]["resolved_callee"] is None


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
                    "kind": "direct",
                    "target": "0x70",
                    "source": "loaded bytes",
                    "loaded_bytes_match_file": True,
                    "disk_disassembly_is_proof": False,
                },
                "plt_stub": "0x60",
                "cosine_call_edges": [
                    {
                        "kind": "direct",
                        "opcode": "e8",
                        "target": "0x60",
                        "source": "loaded bytes",
                        "loaded_bytes_match_file": True,
                        "disk_disassembly_is_proof": False,
                    }
                ],
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
                {
                    "qualname": "FoldableRotorState.angle_from_deployed_rad",
                    "co_code_hex": "aa",
                    "start_offset": 0,
                    "end_offset": 1,
                    "parent_co_code_length": 1,
                    "opcodes": ["BINARY_OP -"],
                    "output_sampled": False,
                },
                {
                    "qualname": "BladeGeometry.radius_m",
                    "co_code_hex": "bb",
                    "start_offset": 0,
                    "end_offset": 1,
                    "parent_co_code_length": 1,
                    "opcodes": ["BINARY_OP /"],
                    "output_sampled": False,
                },
                {
                    "qualname": "project_foldable_blade.kernel_radius",
                    "co_code_hex": "cc",
                    "start_offset": 0,
                    "end_offset": 1,
                    "parent_co_code_length": 8,
                    "opcodes": ["BINARY_OP *"],
                    "output_sampled": False,
                },
                {
                    "qualname": "solve_bem_annulus.kernel_radius",
                    "co_code_hex": "ff",
                    "start_offset": 0,
                    "end_offset": 1,
                    "parent_co_code_length": 8,
                    "opcodes": ["STORE_DEREF radius"],
                    "output_sampled": False,
                },
                {
                    "qualname": "solve_bem_rotor.annulus_edge",
                    "co_code_hex": "dd",
                    "start_offset": 0,
                    "end_offset": 1,
                    "parent_co_code_length": 8,
                    "opcodes": ["STORE_FAST outer"],
                    "output_sampled": False,
                },
                {
                    "qualname": "solve_bem_rotor.midpoint",
                    "co_code_hex": "ee",
                    "start_offset": 0,
                    "end_offset": 1,
                    "parent_co_code_length": 8,
                    "opcodes": ["STORE_FAST midpoint"],
                    "output_sampled": False,
                },
            ],
        },
    }


def test_complete_evidence_is_ready_and_a_missing_byte_is_not() -> None:
    context = _ready_context()
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)
    assert label == UNRESOLVED
    names = {row["name"] for row in unresolved}
    assert "interpreter binary64 arithmetic semantics" in names
    assert "PyFloat_AsDouble conversion semantics" in names
    assert "selected nextafter semantics" in names
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


def test_equal_default_object_is_not_the_retained_binding() -> None:
    bound = _bind()
    resolved = resolve_qualname("solve_bem_rotor")
    assert resolved is not None
    function = resolved.callee
    original = function.__kwdefaults__
    try:
        function.__kwdefaults__ = None if original is None else dict(original)
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        function.__kwdefaults__ = original
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"


def test_stub_bytes_without_a_loaded_call_edge_stay_unresolved() -> None:
    context = _ready_context()
    cosine = context["native"]["runtime_correspondence"]["cosine"]
    cosine.pop("cosine_call_edges", None)
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)
    assert label == UNRESOLVED
    assert any(row["name"] == "cosine path" for row in unresolved)


def test_shared_parent_bytecode_is_not_two_arithmetic_paths() -> None:
    context = _ready_context()
    arithmetic = context["interpreter_arithmetic"]
    for row in arithmetic["operations"]:
        if row["qualname"] in {"solve_bem_rotor.annulus_edge", "solve_bem_rotor.midpoint"}:
            row["co_code_hex"] = "abcd"
            row["start_offset"] = 0
            row["end_offset"] = 2
            row["parent_co_code_length"] = 2
            row["opcodes"] = ["BINARY_OP *"]
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)
    assert label == UNRESOLVED
    assert any(row["name"] == "interpreter binary64 arithmetic" for row in unresolved)


def test_annulus_kernel_follows_the_consumed_solve_bem_annulus() -> None:
    annulus_window = arithmetic_operation_record("solve_bem_annulus.kernel_radius")
    projection_window = arithmetic_operation_record("project_foldable_blade.kernel_radius")
    assert annulus_window["co_code_hex"]
    assert annulus_window["co_code_hex"] != projection_window["co_code_hex"]
    assert any(token in {"STORE_DEREF radius", "STORE_FAST radius"} for token in annulus_window["opcodes"])
    original = bem_rotor.solve_bem_annulus

    def other(*_args, **_kwargs):
        raise AssertionError("annulus evaluated")

    try:
        bem_rotor.solve_bem_annulus = other
        rows = {item["qualname"]: item for item in declare_initial_operation_graph(_repository())}
        kernel = rows["solve_bem_annulus.kernel_radius"]
        assert kernel["family"] == "geometric lemma"
        assert kernel["classification"] != "MATCH"
        assert kernel["every_angle_convergence_theorem"] is False
        projection = rows["project_foldable_blade.kernel_radius"]
        assert projection["operation"] != kernel["operation"]
    finally:
        bem_rotor.solve_bem_annulus = original
    bound = _bind()
    try:
        bem_rotor.solve_bem_annulus = other
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        bem_rotor.solve_bem_annulus = original
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"
    restored = {item["qualname"]: item for item in declare_initial_operation_graph(_repository())}
    assert restored["solve_bem_annulus.kernel_radius"]["classification"] == "MATCH"
    assert bound.evaluator.successful_bem_solves == 0


def test_rex_w_mov_immediate_is_not_a_call() -> None:
    record = decode_loaded_calls(bytes.fromhex("6648c7c00000e8010000c3"), 0x1000)
    assert record["edges"] == []
    assert record["classification"] in {"OBSERVED", "NOT ESTABLISHED"}
    assert record["mode"] == "64-bit"
    assert record["decoder"]
    assert record["coverage"] in {"complete", "unsupported", "truncated"}
    if record["classification"] == "OBSERVED":
        assert record["coverage"] == "complete"


def _relative_call(base: int, offset: int, target: int) -> bytes:
    next_ip = base + offset + 5
    return b"\xe8" + (target - next_ip).to_bytes(4, "little", signed=True)


def test_helper_connection_follows_stub_got_and_qword() -> None:
    base = 0x1000
    helper_stub = 0x2000
    other_stub = 0x4000
    helper_bytes = bytes.fromhex("f30f1efa89f8c1e81b83e001c3")
    code = _relative_call(base, 0, helper_stub) + _relative_call(base, 5, other_stub) + b"\xc3"
    helper_plt = bytes.fromhex("ff2500000000") + b"\x90" * 10
    other_plt = bytes.fromhex("ff2500000000") + b"\x90" * 10
    evidence = {
        "read_state_bytes": code,
        "read_state_address": base,
        "stub_bytes_by_address": {helper_stub: helper_plt, other_stub: other_plt},
        "qword_by_slot": {0x2006: 0x3000, 0x4006: 0x9999},
        "helper_address": 0x3000,
        "helper_range_bytes": helper_bytes,
        "helper_file_bytes": helper_bytes,
        "resolved_callee": {other_stub: 0x3000},
    }
    connected = assess_helper_connection(evidence)
    assert connected["classification"] == "OBSERVED"
    assert connected["call_offset"] == 0
    assert connected["plt_destination"] == hex(helper_stub)
    assert connected["got_slot"] == hex(0x2006)
    assert connected["observed_qword"] == hex(0x3000)
    assert connected["helper_range_matches"] is True
    assert connected["address_annotation_establishes_connection"] is False
    reassigned = dict(evidence)
    reassigned["stub_bytes_by_address"] = {other_stub: other_plt}
    reassigned["qword_by_slot"] = {0x4006: 0x9999}
    assert assess_helper_connection(reassigned)["classification"] == "NOT ESTABLISHED"
    missing = dict(evidence)
    missing["stub_bytes_by_address"] = {}
    assert assess_helper_connection(missing)["classification"] == "NOT ESTABLISHED"
    unresolved = dict(evidence)
    unresolved["qword_by_slot"] = {0x4006: 0x9999}
    assert assess_helper_connection(unresolved)["classification"] == "NOT ESTABLISHED"
    inconsistent = dict(evidence)
    inconsistent["qword_by_slot"] = {0x2006: 0x1111, 0x4006: 0x9999}
    assert assess_helper_connection(inconsistent)["classification"] == "NOT ESTABLISHED"
    mismatched = dict(evidence)
    mismatched["helper_file_bytes"] = b"\x00"
    assert assess_helper_connection(mismatched)["classification"] == "NOT ESTABLISHED"
    annotation = {
        "plt_destination": hex(helper_stub),
        "got_slot": hex(0x2006),
        "observed_qword": hex(0x3000),
        "helper_address": hex(0x3000),
        "resolved_callee": hex(0x3000),
    }
    assert assess_helper_connection(annotation)["classification"] == "NOT ESTABLISHED"


def test_reviewed_artifact_clears_only_the_libm_hypothesis() -> None:
    context = _ready_context()
    cosine = context["native"]["runtime_correspondence"]["cosine"]
    cosine["required_bits_ok"] = True
    cosine["mxcsr"] = "0x1f80"
    cosine["libm_body_argument"] = "DOES NOT APPLY"
    document = {
        "assumptions": ["the captured body bytes are the selected cosine path"],
        "applies_to": {
            "body_sha256": cosine["body_sha256"],
            "constants_identity": _constants_identity(cosine),
            "path": cosine["selected_address"],
        },
    }
    artifact = json.dumps(document, sort_keys=True).encode("utf-8")
    cosine["reviewed_transfer_artifact"] = artifact
    cosine["reviewed_transfer_review"] = {
        "artifact_sha256": sha256_bytes(artifact),
        "provenance": "independent review names this artifact digest",
        "scope": "captured cosine body and constants only",
        "assumptions": document["assumptions"],
        "binds_captured_path": True,
    }
    unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)[1]
    assert not any(row["name"] == "libm body argument" for row in unresolved)
    assert any(row["name"] == "selected nextafter semantics" for row in unresolved)
    cosine["reviewed_transfer_review"] = dict(cosine["reviewed_transfer_review"])
    cosine["reviewed_transfer_review"]["artifact_sha256"] = "00" * 32
    unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)[1]
    assert any(row["name"] == "libm body argument" for row in unresolved)


def test_helper_gate_recomputes_the_loaded_chain() -> None:
    helper_bytes = bytes.fromhex("f30f1efa89f8c1e81b83e001c3")
    base = 0x1000
    helper_stub = 0x2000
    other_stub = 0x4000
    code = _relative_call(base, 0, helper_stub) + _relative_call(base, 5, other_stub) + b"\xc3"
    helper_plt = bytes.fromhex("ff2500000000") + b"\x90" * 10
    other_plt = bytes.fromhex("ff2500000000") + b"\x90" * 10
    helper = {
        "address": hex(0x3000),
        "loaded_bytes_hex": helper_bytes.hex(),
        "file_bytes_hex": helper_bytes.hex(),
    }
    reader = {
        "symbol_bytes_establish_edge": False,
        "address": hex(base),
        "loaded_bytes_hex": code.hex(),
        "observed_plt_stubs": [
            {"address": hex(helper_stub), "bytes_hex": helper_plt.hex()},
            {"address": hex(other_stub), "bytes_hex": other_plt.hex()},
        ],
        "observed_got_qwords": [
            {"slot": hex(0x2006), "qword": hex(0x3000)},
            {"slot": hex(0x4006), "qword": hex(0x9999)},
        ],
        "call_edges": [
            {"resolved_callee": hex(0x3000), "plt_destination": hex(other_stub), "symbol_bytes_establish_edge": False},
        ],
        "helper_connection": {
            "classification": "OBSERVED",
            "plt_stub_bytes_hex": "00",
            "got_slot": "0x1",
            "observed_qword": hex(0x3000),
            "plt_destination": hex(other_stub),
            "helper_range_matches": True,
            "address_annotation_establishes_connection": False,
        },
    }
    assert _helper_call_bound(reader, helper) is True
    forged = {
        "name": "read_state",
        "address": "0x1000",
        "loaded_bytes_hex": "c3",
        "file_bytes_hex": "c3",
        "symbol_bytes_establish_edge": False,
        "correspondence": "MATCH",
        "whole_elf": False,
        "disk_disassembly_is_proof": False,
        "call_edges_decoded_from_loaded_bytes": True,
        "call_edges": [],
        "address_to_elf": {"mapped_file": "/tmp/probe.so", "runtime_address": "0x1000", "file_offset": 128},
        "helper_connection": {
            "classification": "OBSERVED",
            "plt_stub_bytes_hex": "00",
            "got_slot": "0x1",
            "observed_qword": "0x3000",
            "plt_destination": "0x2000",
            "helper_range_matches": True,
            "address_annotation_establishes_connection": False,
        },
    }
    retained = {
        "name": "xcr0_read_permitted",
        "address": "0x3000",
        "loaded_bytes_hex": "bb",
        "file_bytes_hex": "bb",
        "correspondence": "MATCH",
        "whole_elf": False,
        "disk_disassembly_is_proof": False,
        "call_edges_decoded_from_loaded_bytes": True,
        "call_edges": [],
        "address_to_elf": {"mapped_file": "/tmp/probe.so", "runtime_address": "0x3000", "file_offset": 256},
    }
    assert _helper_call_bound(forged, retained) is False
    gaps = _probe_range_gaps({"measurement_image": {"consumed_instruction_ranges": [forged, retained]}})
    assert any(row["name"] == "read_state helper call edge" for row in gaps)


def test_blank_body_identities_do_not_clear_the_libm_hypothesis() -> None:
    context = _ready_context()
    cosine = context["native"]["runtime_correspondence"]["cosine"]
    cosine["required_bits_ok"] = True
    cosine["mxcsr"] = "0x1f80"
    cosine["libm_body_argument"] = "DOES NOT APPLY"
    cosine["body_sha256"] = ""
    cosine["constants"] = []
    document = {
        "assumptions": ["the captured body bytes are the selected cosine path"],
        "applies_to": {
            "body_sha256": "",
            "constants_identity": "[]",
            "path": cosine["selected_address"],
        },
    }
    artifact = json.dumps(document, sort_keys=True).encode("utf-8")
    cosine["reviewed_transfer_artifact"] = artifact
    cosine["reviewed_transfer_review"] = {
        "artifact_sha256": sha256_bytes(artifact),
        "provenance": "independent review names this artifact digest",
        "scope": "captured cosine body and constants only",
        "assumptions": document["assumptions"],
        "binds_captured_path": True,
    }
    unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)[1]
    assert any(row["name"] == "libm body argument" for row in unresolved)
    assert any(row["name"] == "selected nextafter semantics" for row in unresolved)


def test_reassigned_callee_does_not_bind_the_helper() -> None:
    helper = {"address": "0x3000"}
    reader = {
        "symbol_bytes_establish_edge": False,
        "call_edges": [
            {
                "symbol_bytes_establish_edge": False,
                "resolved_callee": "0x1111",
                "plt_destination": "0x2000",
                "offset": 0,
            },
            {
                "symbol_bytes_establish_edge": False,
                "resolved_callee": "0x3000",
                "plt_destination": "0x4000",
                "offset": 5,
            },
        ],
    }
    assert _helper_call_bound(reader, helper) is False


def test_caller_dictionary_does_not_clear_the_libm_body_blocker() -> None:
    context = _ready_context()
    cosine = context["native"]["runtime_correspondence"]["cosine"]
    cosine["required_bits_ok"] = True
    cosine["mxcsr"] = "0x1f80"
    cosine["libm_body_argument"] = "DOES NOT APPLY"
    cosine["alternative_transfer_argument"] = {
        "applicable": True,
        "scope": "captured libm body",
        "binds_captured_path": True,
        "body_sha256": cosine["body_sha256"],
        "constants_identity": _constants_identity(cosine),
    }
    _label_result = _label(False, _ready_graph(), _ready_ulp(), **context)
    unresolved = _label_result[1]
    assert any(row["name"] == "libm body argument" for row in unresolved)
    assert any(row["name"] == "selected nextafter semantics" for row in unresolved)


def test_shr_and_mov_immediate_are_not_calls() -> None:
    helper = call_edges_from_loaded_bytes(bytes.fromhex("f30f1efa89f8c1e81b83e001c3"), 0x1000)
    mov = call_edges_from_loaded_bytes(bytes.fromhex("b8e8000000c3"), 0x2000)
    assert helper == []
    assert mov == []


def test_sse_immediate_bytes_are_not_calls() -> None:
    witnesses = (
        "0f71d0e8000000c3",
        "0f72d0e8000000c3",
        "0f73d0e8000000c3",
        "0fc6c0e800000000c3",
    )
    for blob in witnesses:
        record = decode_loaded_calls(bytes.fromhex(blob), 0x1000)
        assert record["edges"] == []
        assert record["classification"] in {"OBSERVED", "NOT ESTABLISHED"}


def test_truncated_or_unsupported_decoding_stays_unestablished() -> None:
    truncated = decode_loaded_calls(bytes.fromhex("e800"), 0x3000)
    assert truncated["classification"] == "NOT ESTABLISHED"
    assert truncated["coverage"] == "truncated"
    assert truncated["edges"] == []
    assert truncated["mode"] == "64-bit"
    unsupported = decode_loaded_calls(bytes.fromhex("06c3"), 0x4000)
    assert unsupported["classification"] == "NOT ESTABLISHED"
    assert unsupported["coverage"] == "unsupported"
    assert unsupported["edges"] == []
    direct = decode_loaded_calls(bytes.fromhex("e800000000"), 0x1000)
    assert direct["classification"] == "OBSERVED"
    assert direct["coverage"] == "complete"
    assert direct["edges"][0]["kind"] == "direct"
    assert direct["edges"][0]["target"] == hex(0x1005)
    indirect = decode_loaded_calls(bytes.fromhex("ff1500000000"), 0x2000)
    assert indirect["classification"] == "OBSERVED"
    assert indirect["edges"][0]["kind"] == "indirect"
    assert indirect["edges"][0]["target"] == hex(0x2006)
    assert indirect["edges"][0]["plt_destination"] == hex(0x2006)
    assert indirect["edges"][0]["resolved_callee"] is None
    assert indirect["edges"][0]["symbol_bytes_establish_edge"] is False


def test_symbol_bytes_do_not_establish_the_helper_call_edge() -> None:
    context = _ready_context()
    image = context["native"]["measurement_image"]
    for row in image["consumed_instruction_ranges"]:
        row["call_edges"] = []
        row["call_edges_decoded_from_loaded_bytes"] = True
        row["call_decode"] = {"classification": "OBSERVED", "coverage": "complete", "edges": []}
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)
    assert label == UNRESOLVED
    assert any(row["name"] == "read_state helper call edge" for row in unresolved)


def test_control_and_body_disagreement_stay_unresolved() -> None:
    context = _ready_context()
    cosine = context["native"]["runtime_correspondence"]["cosine"]
    cosine["required_bits_ok"] = False
    cosine["mxcsr"] = "0x1f80"
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)
    assert label == UNRESOLVED
    assert any(row["name"] == "numerical controls" and "required bits" in str(row["missing"]) for row in unresolved)
    context = _ready_context()
    cosine = context["native"]["runtime_correspondence"]["cosine"]
    cosine["required_bits_ok"] = True
    cosine["mxcsr"] = "0x9fa0"
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)
    assert any(row["name"] == "numerical controls" and "FTZ" in str(row["missing"]) for row in unresolved)
    context = _ready_context()
    cosine = context["native"]["runtime_correspondence"]["cosine"]
    cosine["required_bits_ok"] = True
    cosine["mxcsr"] = "0x1f80"
    cosine["libm_body_argument"] = "DOES NOT APPLY"
    cosine.pop("alternative_transfer_argument", None)
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)
    assert any(row["name"] == "libm body argument" for row in unresolved)
    cosine["exact_historical_xcr0_match"] = False
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)
    assert not any(row["missing"] == "historical XCR0 equality" for row in unresolved)


def test_structural_records_do_not_close_semantic_hypotheses() -> None:
    context = _ready_context()
    cosine = context["native"]["runtime_correspondence"]["cosine"]
    cosine["required_bits_ok"] = True
    cosine["mxcsr"] = "0x1f80"
    cosine["libm_body_argument"] = "APPLIES"
    label, unresolved = _label(False, _ready_graph(), _ready_ulp(), **context)
    names = {row["name"] for row in unresolved}
    assert label == UNRESOLVED
    assert "interpreter binary64 arithmetic semantics" in names
    assert "PyFloat_AsDouble conversion semantics" in names
    assert "selected nextafter semantics" in names


def test_historical_capsule_bytes_remain_the_earlier_record() -> None:
    root = _repository() / "reports/c2v09_pre_call_capsule"
    historical = hashlib.sha256((root / "capsule.json").read_bytes()).hexdigest()
    loaded = hashlib.sha256((root / "loaded_correspondence_capsule.json").read_bytes()).hexdigest()
    assert historical == "09f7df71697528333be1674fde6419bbeadeec084213274c2eab3ee7abb6649a"
    assert loaded == "8cebb4d5fe12e4ef6f15aacae0dcc986999534346d9043de9c9cef51320024f5"
