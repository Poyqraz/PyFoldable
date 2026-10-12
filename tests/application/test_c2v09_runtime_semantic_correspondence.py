"""Scoped runtime-semantic argument. It does not admit the readiness hypotheses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pyfoldable.application.c2v09_cosine_path_certificate import _elf_bytes
from pyfoldable.application.c2v09_ordered_declaration import canonical_bytes, sha256_bytes
from pyfoldable.application.c2v09_runtime_semantic_correspondence import (
    ESTABLISHED_CONDITIONALLY,
    MISMATCHED,
    NOT_ESTABLISHED,
    classify_correspondence,
    _decoded_store,
    nextafter_got_resolved,
    prepare_runtime_semantic_correspondence,
    replay_handler_scalars,
)

_HYPOTHESES = (
    "interpreter binary64 arithmetic semantics",
    "PyFloat_AsDouble conversion semantics",
    "selected nextafter semantics",
)
_CAPSULES = {
    "capsule.json": "09f7df71697528333be1674fde6419bbeadeec084213274c2eab3ee7abb6649a",
    "loaded_correspondence_capsule.json": "8cebb4d5fe12e4ef6f15aacae0dcc986999534346d9043de9c9cef51320024f5",
    "boundary_decode_capsule.json": "630d149e0da9c68fdcc328ccb45d4c79cddcbe2868b240a031be7ed01595e3ce",
}


def _handler(kind: str, mnemonic: str, *, store: str = "PyFloat_FromDouble", fma: list[str] | None = None) -> dict[str, object]:
    return {
        "kind": kind,
        "loaded_bytes_match_file": True,
        "scalar_mnemonics": [mnemonic],
        "paths_execute_one_scalar_op": True,
        "fma_mnemonics": [] if fma is None else fma,
        "store": store,
        "ob_fval_load": True,
        "decoder": "capstone",
        "mode": "64-bit",
    }


def _observations() -> dict[str, object]:
    generic = {
        "add": _handler("add", "addsd"),
        "sub": _handler("sub", "subsd"),
        "mul": _handler("mul", "mulsd"),
        "div": _handler("div", "divsd"),
    }
    specialized = {
        "add": [_handler("add", "addsd", store="in-place ob_fval or PyFloat_FromDouble")],
        "sub": [_handler("sub", "subsd", store="in-place ob_fval or PyFloat_FromDouble")],
        "mul": [_handler("mul", "mulsd", store="in-place ob_fval or PyFloat_FromDouble")],
        "div": [],
    }
    return {
        "pid": 1,
        "thread_id": "7",
        "single_process_thread": True,
        "output_sampled": False,
        "version_label": "3.12.3",
        "version_label_establishes_semantics": False,
        "approval_receipt_establishes_semantics": False,
        "sample_outputs_establish_semantics": False,
        "controls": {
            "classification": "OBSERVED",
            "required_bits_ok": True,
            "mxcsr_ftz": False,
            "mxcsr_daz": False,
            "mxcsr_rounding": "nearest ties-to-even",
            "fegetround": "0",
            "thread_id": "7",
        },
        "arithmetic": {
            "operations": [
                {
                    "qualname": "FoldableRotorState.angle_from_deployed_rad",
                    "kinds": ["sub"],
                    "bytecode_window_establishes_semantics": False,
                },
                {
                    "qualname": "solve_bem_rotor.annulus_edge",
                    "kinds": ["mul", "add", "add", "mul", "add"],
                    "bytecode_window_establishes_semantics": False,
                },
                {
                    "qualname": "solve_bem_rotor.midpoint",
                    "kinds": ["add", "mul"],
                    "bytecode_window_establishes_semantics": False,
                },
            ],
            "generic_handlers": generic,
            "specialized_handlers": specialized,
            "specialized_scan": "complete",
            "unclassified_scalar_sites": 0,
        },
        "conversion": {
            "wrapper_calls_defined_symbol": True,
            "loaded_bytes_match_file": True,
            "builtin_float_path": "movsd [obj+0x10]; ret",
            "fast_path_has_no_convert": True,
            "finite_result_store": "PyFloat_FromDouble",
            "non_float_paths_are_not_the_builtin_argument": True,
        },
        "terminal_guard": {
            "ulp_function_calls": 0,
            "nextafter_function_calls": 0,
            "output_sampled": False,
            "wrapper_matches_file": True,
            "wrapper_calls_nextafter_plt": True,
            "got_resolved": True,
            "selected_body_bound": True,
            "integer_increment_in_selected_body": True,
            "wrapper_subtraction": "subsd",
            "unchanged_guard_ulps": 2,
            "allowance_recomputed": False,
            "independent_symbol_establishes_selected_path": False,
        },
    }


def _by_name(result: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = result["hypotheses"]
    assert isinstance(rows, list)
    return {str(row["name"]): row for row in rows if isinstance(row, dict)}


def test_receipts_samples_and_version_labels_do_not_establish() -> None:
    observations = _observations()
    observations["arithmetic"] = {
        "operations": [],
        "generic_handlers": {},
        "specialized_handlers": {},
        "specialized_scan": "unavailable",
        "unclassified_scalar_sites": 0,
    }
    observations["conversion"] = {}
    observations["terminal_guard"] = {
        "ulp_function_calls": 0,
        "nextafter_function_calls": 0,
        "output_sampled": True,
        "sample_result": "0x1.0p-56",
        "approval_receipt": "APPROVED",
        "version_label": "CPython 3.12.14",
    }
    found = _by_name(classify_correspondence(observations))
    assert set(found) == set(_HYPOTHESES)
    assert all(row["status"] == NOT_ESTABLISHED for row in found.values())
    assert all(row["readiness_admitted"] is False for row in found.values())


def test_complete_observation_is_conditional_and_not_admitted() -> None:
    observations = _observations()
    observations["approval_receipt"] = "APPROVED by an independent board"
    observations["sample_result"] = "0x1.0p-56"
    result = classify_correspondence(observations)
    found = _by_name(result)
    assert all(row["status"] == NOT_ESTABLISHED for row in found.values())
    assert all(row["readiness_admitted"] is False for row in found.values())
    assert result["readiness_hypotheses_admitted"] is False
    assert result["approval_receipt_establishes_semantics"] is False
    assert result["sample_outputs_establish_semantics"] is False
    assert result["version_label_establishes_semantics"] is False
    arithmetic = found["interpreter binary64 arithmetic semantics"]
    assert arithmetic["conditions"] == []
    assert any("POST-RETURN ONLY" in str(item) for item in arithmetic["post_return_only"])
    guard = found["selected nextafter semantics"]
    assert guard["unchanged_guard_ulps"] == 2
    matrix = result["argument_to_evidence"]
    assert isinstance(matrix, list)
    assert {row["hypothesis"] for row in matrix} == set(_HYPOTHESES)


def test_trailing_e8_range_is_not_established() -> None:
    observations = _observations()
    handler = _handler("mul", "mulsd")
    handler["address"] = "0x1000"
    handler["loaded_bytes_hex"] = "f20f104010f20f59c1f20f114010c3e8"
    observations["arithmetic"]["generic_handlers"]["mul"] = handler
    found = _by_name(classify_correspondence(observations))
    assert found["interpreter binary64 arithmetic semantics"]["status"] == NOT_ESTABLISHED


def test_unresolved_side_branch_does_not_complete_the_store_path() -> None:
    observations = _observations()
    for blob in (
        "f20f58c1f20f114010e900000000",
        "f20f58c10f8500100000f20f114010c3",
        "f20f58c1f20f114010",
    ):
        handler = _handler("add", "addsd")
        handler["address"] = "0x1000"
        handler["loaded_bytes_hex"] = blob
        observations["arithmetic"]["generic_handlers"]["add"] = handler
        found = _by_name(classify_correspondence(observations))
        assert found["interpreter binary64 arithmetic semantics"]["status"] == NOT_ESTABLISHED


def test_fromdouble_load_is_not_a_store() -> None:
    observations = _observations()
    observations["conversion"] = {
        "wrapper_address": "0x1000",
        "wrapper_bytes_hex": "e8fb0f0000c3",
        "asdouble_address": "0x2000",
        "asdouble_bytes_hex": "f20f104010c3",
        "fromdouble_address": "0x3000",
        "fromdouble_bytes_hex": "488b4710c3",
        "ulp_function_calls": 0,
        "nextafter_function_calls": 0,
        "output_sampled": False,
    }
    found = _by_name(classify_correspondence(observations))
    assert found["PyFloat_AsDouble conversion semantics"]["status"] == NOT_ESTABLISHED


def test_external_branch_without_continuation_is_not_established() -> None:
    observations = _observations()
    handler = _handler("add", "addsd")
    handler["address"] = "0x1000"
    handler["loaded_bytes_hex"] = "f20f58c1e9fb0f0000"
    observations["arithmetic"]["generic_handlers"]["add"] = handler
    found = _by_name(classify_correspondence(observations))
    assert found["interpreter binary64 arithmetic semantics"]["status"] == NOT_ESTABLISHED


def test_ret_only_conversion_claim_is_rejected() -> None:
    observations = _observations()
    observations["conversion"] = {
        "wrapper_calls_defined_symbol": True,
        "loaded_bytes_match_file": True,
        "builtin_float_path": "movsd [obj+0x10]; ret",
        "fast_path_has_no_convert": True,
        "finite_result_store": "PyFloat_FromDouble",
        "wrapper_address": "0x1000",
        "wrapper_bytes_hex": "c3",
        "asdouble_address": "0x2000",
        "asdouble_bytes_hex": "c3",
        "fromdouble_address": "0x3000",
        "fromdouble_bytes_hex": "c3",
    }
    found = _by_name(classify_correspondence(observations))
    assert found["PyFloat_AsDouble conversion semantics"]["status"] == NOT_ESTABLISHED


def test_integer_add_is_not_a_float_handler() -> None:
    observations = _observations()
    blob = bytes.fromhex("f20f104010f20f58c1f20f114010c3")
    handler = _handler("add", "addsd")
    handler["address"] = "0x1000"
    handler["loaded_bytes_hex"] = blob.hex()
    observations["arithmetic"]["operations"] = [
        {
            "qualname": "solve_bem_rotor.annulus_edge",
            "kinds": ["add"],
            "categories": ["integer_add"],
            "bytecode_window_establishes_semantics": False,
        }
    ]
    observations["arithmetic"]["generic_handlers"] = {"add": handler}
    observations["arithmetic"]["specialized_handlers"] = {"add": [], "sub": [], "mul": [], "div": []}
    found = _by_name(classify_correspondence(observations))
    assert found["interpreter binary64 arithmetic semantics"]["status"] == NOT_ESTABLISHED


def test_stored_handler_bytes_override_a_clean_claim() -> None:
    observations = _observations()
    sequential = bytes.fromhex("f20f58c1f20f58c1c3")
    handler = _handler("add", "addsd")
    handler["address"] = "0x1000"
    handler["loaded_bytes_hex"] = sequential.hex()
    observations["arithmetic"]["generic_handlers"]["add"] = handler
    found = _by_name(classify_correspondence(observations))
    assert found["interpreter binary64 arithmetic semantics"]["status"] == NOT_ESTABLISHED
    fused = bytes.fromhex("c4e2f1a9c0c3")
    handler = _handler("add", "addsd")
    handler["address"] = "0x1000"
    handler["loaded_bytes_hex"] = fused.hex()
    observations["arithmetic"]["generic_handlers"]["add"] = handler
    found = _by_name(classify_correspondence(observations))
    assert found["interpreter binary64 arithmetic semantics"]["status"] == MISMATCHED


def test_endbr_plt_slot_is_not_a_resolved_nextafter() -> None:
    stub = bytes.fromhex("f30f1efaff2500000000")
    target = 0x2000
    assert nextafter_got_resolved(target, target + 10, stub) is False
    assert nextafter_got_resolved(target, target + 6, stub) is False
    assert nextafter_got_resolved(target, 0x8000, stub) is True


def test_evidence_uses_the_store_present_in_the_bytes() -> None:
    observations = _observations()
    blob = bytes.fromhex("f20f104010f20f5cc1f20f114010c3")
    handler = _handler("sub", "subsd", store="in-place ob_fval or PyFloat_FromDouble")
    handler["address"] = "0x1000"
    handler["loaded_bytes_hex"] = blob.hex()
    observations["arithmetic"]["generic_handlers"]["sub"] = handler
    found = _by_name(classify_correspondence(observations))
    evidence = found["interpreter binary64 arithmetic semantics"]["evidence"]
    sub_lines = [str(item) for item in evidence if str(item).startswith("generic sub")]
    assert sub_lines
    assert "ob_fval" in sub_lines[0]
    assert "PyFloat_FromDouble" not in sub_lines[0]


def test_fused_handler_is_mismatched() -> None:
    observations = _observations()
    observations["arithmetic"]["generic_handlers"]["add"] = _handler("add", "addsd", fma=["vfmadd213sd"])
    found = _by_name(classify_correspondence(observations))
    assert found["interpreter binary64 arithmetic semantics"]["status"] == NOT_ESTABLISHED
    assert found["interpreter binary64 arithmetic semantics"]["readiness_admitted"] is False


def test_unresolved_nextafter_slot_is_not_established() -> None:
    observations = _observations()
    guard = observations["terminal_guard"]
    guard["got_resolved"] = False
    guard["selected_body_bound"] = False
    guard["integer_increment_in_selected_body"] = None
    guard["approval_receipt"] = "UNREVIEWED"
    found = _by_name(classify_correspondence(observations))
    assert found["selected nextafter semantics"]["status"] == NOT_ESTABLISHED
    assert any("GOT" in str(item) for item in found["selected nextafter semantics"]["gaps"])
    assert found["interpreter binary64 arithmetic semantics"]["status"] == NOT_ESTABLISHED


def test_live_package_does_not_admit_the_three_hypotheses() -> None:
    package = prepare_runtime_semantic_correspondence(Path(__file__).resolve().parents[2])
    assert package["authorizes_execution"] is False
    assert package["candidate29_disposition"] == "NOT SELECTED"
    assert package["eligibility_evidence"] is False
    assert package["physical_qualification"] is False
    assert package["readiness_hypotheses_admitted"] is False
    assert package["output_sampled"] is False
    assert package["ulp_function_calls"] == 0
    assert package["nextafter_function_calls"] == 0
    assert package["cosine_function_calls"] == 0
    found = _by_name(package)
    assert set(found) == set(_HYPOTHESES)
    for name in _HYPOTHESES:
        assert found[name]["status"] in {ESTABLISHED_CONDITIONALLY, MISMATCHED, NOT_ESTABLISHED}
        assert found[name]["readiness_admitted"] is False
        assert found[name]["post_return_only"]
    generic = package["observations"]["arithmetic"]["generic_handlers"]
    assert isinstance(generic, dict)
    for handler in generic.values():
        assert replay_handler_scalars(handler) == handler["scalar_mnemonics"]
    specialized = package["observations"]["arithmetic"]["specialized_handlers"]
    assert isinstance(specialized, dict)
    for sites in specialized.values():
        assert isinstance(sites, list)
        for site in sites:
            blob = bytes.fromhex(str(site["loaded_bytes_hex"]))
            file_bytes = _elf_bytes(str(site["image"]), int(str(site["elf_vaddr"]), 16), len(blob))
            assert file_bytes == blob
            assert site["store"] == _decoded_store(site)
    observations = package["observations"]
    arguments = package["arguments"]
    assert observations is not arguments
    assert "hypotheses" not in observations
    root = Path(__file__).resolve().parents[2] / "reports" / "c2v09_pre_call_capsule"
    for name, digest in _CAPSULES.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest


def test_correspondence_record_is_not_the_measurement_commit() -> None:
    path = Path(__file__).resolve().parents[2] / "reports" / "c2v09_pre_call_capsule" / "runtime_semantic_correspondence.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "74f4ea340bd524ac721ec002798effe5538f4bb38aec680f8db0fe30d27ad785"
    document = json.loads(raw)
    payload = document["canonical_payload"]
    assert payload["measurement_implementation_head"] == "a6ac80d4047f4bbee56421bcff3d060ca1bee8d6"
    assert payload["measurement_implementation_tree"] == "e889f8c1b2b1ad22d0dc28e968510e0c817f038f"
    assert payload["record_commit_is_measurement_commit"] is False
    assert payload["readiness_hypotheses_admitted"] is False
    assert "canonical_sha256" not in payload
    assert document["canonical_sha256"] == "38ff1dee457b06f6969b2e201981e86d7723f5970113fbaaecf10edb75fabc9d"
    assert sha256_bytes(canonical_bytes(payload)) == document["canonical_sha256"]
    statuses = {row["name"]: row["status"] for row in payload["hypotheses"]}
    assert statuses == {
        "interpreter binary64 arithmetic semantics": "ESTABLISHED CONDITIONALLY",
        "PyFloat_AsDouble conversion semantics": "ESTABLISHED CONDITIONALLY",
        "selected nextafter semantics": "NOT ESTABLISHED",
    }


def test_fail_closed_record_is_a_later_observation() -> None:
    path = Path(__file__).resolve().parents[2] / "reports" / "c2v09_pre_call_capsule" / "runtime_semantic_fail_closed.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "c5f36955d9082df11141fc31c4a161b0391f104cd4bf0449620c600ff48b279e"
    document = json.loads(raw)
    payload = document["canonical_payload"]
    assert payload["measurement_implementation_head"] == "51abb91c984b77438516818635e046e30cbb1b42"
    assert payload["measurement_implementation_tree"] == "ca4f15fb576522d8646baa5c2bc9e22ceb21a35c"
    assert payload["record_commit_is_measurement_commit"] is False
    assert payload["readiness_hypotheses_admitted"] is False
    assert "canonical_sha256" not in payload
    assert document["canonical_sha256"] == "695121f0eb2fe5009cb37e36eb2fb73b6d4e16e9a5274ad29e0b8ba8d290e448"
    assert sha256_bytes(canonical_bytes(payload)) == document["canonical_sha256"]
    statuses = {row["name"]: row["status"] for row in payload["hypotheses"]}
    assert statuses == {
        "interpreter binary64 arithmetic semantics": "NOT ESTABLISHED",
        "PyFloat_AsDouble conversion semantics": "ESTABLISHED CONDITIONALLY",
        "selected nextafter semantics": "ESTABLISHED CONDITIONALLY",
    }
    assert all(row["readiness_admitted"] is False for row in payload["hypotheses"])
