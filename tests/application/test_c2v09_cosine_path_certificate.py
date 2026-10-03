"""One actual runtime's Python cosine call path. CDLL is not that path."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

import pyfoldable.application.c2v09_cosine_path_certificate as cosine_certificate
from pyfoldable.application.c2v09_cosine_path_certificate import (
    CERTIFICATE_FILE_SHA256,
    HISTORICAL_BODY_SHA256,
    UNPARSED_STUB_METHOD,
    _feature_record,
    attribute_loaded_wrapper,
    classify_selected_call,
    libm_body_verdict,
    plt_got_address,
    prepare_cosine_path_certificate,
    xcr0_read_permitted,
)
from pyfoldable.application.c2v09_ordered_declaration import canonical_bytes, sha256_bytes


HISTORICAL_OBSERVATION_SHA256 = "ead8a612b8df532a3f1218d33ea416452f4ec967f8240846003e784b0e2ec92d"
_OSXSAVE = 1 << 27


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def _payload(record: dict) -> dict:
    payload = record["canonical_payload"]
    assert "canonical_sha256" not in payload
    return payload


def test_plt_got_is_the_rip_relative_slot() -> None:
    stub = bytes.fromhex("ff25f28b6000")
    assert plt_got_address(stub, 0x4207E0) == 0xA293D8
    endbr = b"\xf3\x0f\x1e\xfa" + stub
    assert plt_got_address(endbr, 0x4207E0 - 4) == 0xA293D8
    assert plt_got_address(b"\x90\x90\x90\x90\x90\x90", 0x4207E0) is None
    assert "does not repair an unrecognized stub" in UNPARSED_STUB_METHOD


def test_missing_loaded_bytes_block_instead_of_refuting_the_argument() -> None:
    blocked = libm_body_verdict(
        selected_observed=True,
        features_observed=True,
        body_sha=None,
        constant_rows=[],
        required_bits=True,
        body_vaddr=None,
        historical_vaddr="0x7bad0",
    )
    unread_constants = libm_body_verdict(
        selected_observed=True,
        features_observed=True,
        body_sha=HISTORICAL_BODY_SHA256,
        constant_rows=[{"classification": "NOT ESTABLISHED"}],
        required_bits=True,
        body_vaddr="0x7bad0",
        historical_vaddr="0x7bad0",
    )
    shifted = libm_body_verdict(
        selected_observed=True,
        features_observed=True,
        body_sha=HISTORICAL_BODY_SHA256,
        constant_rows=[{"classification": "MATCH"}],
        required_bits=True,
        body_vaddr="0x8000",
        historical_vaddr="0x7bad0",
    )
    applies = libm_body_verdict(
        selected_observed=True,
        features_observed=True,
        body_sha=HISTORICAL_BODY_SHA256,
        constant_rows=[{"classification": "MATCH"}],
        required_bits=True,
        body_vaddr="0x7bad0",
        historical_vaddr="0x7bad0",
    )
    assert blocked == unread_constants == "BLOCKED"
    assert shifted == "DOES NOT APPLY"
    assert applies == "APPLIES"


def test_unresolved_plt_is_not_replaced_by_cdll() -> None:
    selected = classify_selected_call(
        got_pointer=0x4207E6,
        stub_address=0x4207E0,
        cdll_pointer=0x7BAD0,
    )
    assert selected["classification"] == "NOT ESTABLISHED"
    assert selected["address"] is None
    assert selected["evidence"] == "python wrapper plt got"
    assert selected["independent_cdll_is_evidence"] is False
    assert "LD_BIND_NOW" in selected["method"]
    assert "CDLL" in selected["method"]


def test_resolved_got_stays_the_evidence_when_it_equals_cdll() -> None:
    selected = classify_selected_call(
        got_pointer=0x7F0000BAD0,
        stub_address=0x4207E0,
        cdll_pointer=0x7F0000BAD0,
    )
    assert selected["classification"] == "OBSERVED"
    assert selected["address"] == hex(0x7F0000BAD0)
    assert selected["evidence"] == "python wrapper plt got"
    assert selected["independent_cdll_is_evidence"] is False
    assert selected["addresses_equal"] is True


def test_historical_certificate_bytes_stay_unchanged() -> None:
    root = _repository()
    certificate = root / "docs/cmm2_c2v09_partition_runtime_certificate.md"
    assert sha256_bytes(certificate.read_bytes()) == CERTIFICATE_FILE_SHA256


def test_live_path_keeps_cdll_out_of_the_call_target() -> None:
    payload = _payload(prepare_cosine_path_certificate(_repository()))
    selected = payload["selected_call_target"]
    assert selected["evidence"] == "python wrapper plt got"
    assert selected["independent_cdll_is_evidence"] is False
    assert payload["historical_cpython_wrapper_argument"] == "DOES NOT APPLY"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["cosine_function_calls"] == 0
    assert payload["checkout_sha"] and payload["tree_sha"]
    assert payload["probe_source_sha256"] != payload["implementation_sha256"]
    identities = {
        payload["checkout_sha"],
        payload["tree_sha"],
        payload["probe_source_sha256"],
        payload["implementation_sha256"],
    }
    assert len(identities) == 4
    assert payload["returned_source_object"] == "NOT IN THIS CERTIFICATE"
    assert payload["changed_python_operation_graph"] == "NOT IN THIS CERTIFICATE"
    if selected["classification"] == "OBSERVED":
        assert selected["address"]
        assert payload["libm_body_argument"] in {"APPLIES", "DOES NOT APPLY", "BLOCKED"}
    else:
        assert selected["classification"] == "NOT ESTABLISHED"
        assert payload["libm_body_argument"] == "BLOCKED"
        assert "LD_BIND_NOW" in selected["method"] or "objdump" in selected["method"]


def _assert_recorded_checkout(root: Path, checkout: str, tree_sha: str) -> None:
    assert len(checkout) == 40 and len(tree_sha) == 40
    present = subprocess.call(
        ["git", "cat-file", "-e", f"{checkout}^{{commit}}"],
        cwd=root,
        stderr=subprocess.DEVNULL,
    ) == 0
    if not present:
        return
    tree = subprocess.check_output(["git", "rev-parse", f"{checkout}^{{tree}}"], cwd=root, text=True).strip()
    assert tree_sha == tree


def test_persisted_path_certificate_recomputes() -> None:
    root = _repository()
    document = json.loads(
        (root / "reports/c2v09_cosine_path_certificate/observation.json").read_text(encoding="utf-8")
    )
    payload = _payload(document)
    assert document["canonical_sha256"] == sha256_bytes(canonical_bytes(payload))
    assert payload["libm_body_argument"] == "APPLIES"
    assert payload["historical_cpython_wrapper_argument"] == "DOES NOT APPLY"
    assert payload["selected_call_target"]["evidence"] == "python wrapper plt got"
    assert payload["selected_call_target"]["independent_cdll_is_evidence"] is False
    assert payload["selected_call_target"]["classification"] == "OBSERVED"
    assert payload["loaded_body"]["matches_historical_body"] is True
    assert payload["loaded_body"]["sha256"] == HISTORICAL_BODY_SHA256
    assert payload["loaded_body"]["elf_vaddr"] == "0x7bad0"
    assert payload["selected_call_target"]["plt_jmp_bytes_hex"] == "ff25f28b6000"
    assert payload["python_wrapper"]["loaded_wrapper_matches_elf"] is True
    assert payload["python_wrapper"]["disassembly_source"].startswith("objdump")
    assert payload["numerical_controls_and_features"]["required_bits_ok"] is True
    assert payload["numerical_controls_and_features"]["exact_historical_xcr0_match"] is False
    assert payload["ld_bind_now"] == "1"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["cosine_function_calls"] == 0
    _assert_recorded_checkout(root, payload["checkout_sha"], payload["tree_sha"])


def test_certificate_text_does_not_call_source_or_cosine() -> None:
    text = (_repository() / "pyfoldable/application/c2v09_cosine_path_certificate.py").read_text(encoding="utf-8")
    assert "math.cos(" not in text
    assert "bem" not in text
    assert "mapper" not in text
    assert "trajectory" not in text
    document = (_repository() / "docs/cmm2_c2v09_one_runtime_cosine_path_certificate.md").read_text(encoding="utf-8")
    assert "DOES NOT APPLY" in document
    assert "physical_qualification=false" in document
    assert "not eligibility evidence" in document
    assert HISTORICAL_BODY_SHA256


def _probe_permission(tmp_path: Path):
    """Compile the predicate only. Do not call read_state."""
    source = _repository() / "pyfoldable/application/c2v09_cosine_path_probe.c"
    binary = tmp_path / "probe.so"
    compiled = subprocess.run(
        ["gcc", "-O2", "-shared", "-fPIC", "-o", str(binary), str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert compiled.returncode == 0, compiled.stderr
    library = ctypes.CDLL(str(binary))
    permitted = library.xcr0_read_permitted
    permitted.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    permitted.restype = ctypes.c_int
    return permitted


def _feature_words(*, leaf1_ecx: int, leaf7_ecx: int, xcr0_lo: int) -> list[int]:
    words = [0x1FA0, 0x37F, 0, 0, leaf1_ecx, 0, 0, 0, leaf7_ecx, 0, xcr0_lo, 0]
    return words


def test_leaf1_osxsave_absent_does_not_permit_xgetbv_when_leaf7_bit27_is_set(tmp_path: Path) -> None:
    permitted = _probe_permission(tmp_path)
    assert permitted(0, _OSXSAVE) == 0
    assert xcr0_read_permitted(0, _OSXSAVE) is False


def test_absent_osxsave_does_not_publish_a_zero_xcr0() -> None:
    record = _feature_record(_feature_words(leaf1_ecx=0, leaf7_ecx=_OSXSAVE, xcr0_lo=0), "0")
    assert record.get("xcr0_classification") == "NOT ESTABLISHED"
    assert record.get("xcr0") is None
    assert record["classification"] == "NOT ESTABLISHED"


def test_leaf1_osxsave_present_permits_xgetbv_when_leaf7_bit27_is_absent(tmp_path: Path) -> None:
    permitted = _probe_permission(tmp_path)
    assert permitted(_OSXSAVE, 0) == 1
    assert xcr0_read_permitted(_OSXSAVE, 0) is True


def test_osxsave_publishes_xcr0_when_leaf7_bit27_is_absent() -> None:
    record = _feature_record(_feature_words(leaf1_ecx=_OSXSAVE, leaf7_ecx=0, xcr0_lo=0x602E7), "0")
    assert record.get("xcr0_classification") == "OBSERVED"
    assert record["xcr0"] == ["0x602e7", "0x0"]
    assert record["classification"] == "OBSERVED"
    assert record["osxsave"] is True


def _applying_body() -> dict:
    return {
        "body_sha": HISTORICAL_BODY_SHA256,
        "constant_rows": [{"classification": "MATCH"}],
        "features_observed": True,
        "required_bits": True,
        "body_vaddr": "0x7bad0",
        "historical_vaddr": "0x7bad0",
    }


def _observed_got(cdll_pointer: int) -> dict:
    return classify_selected_call(
        got_pointer=0x7F0000BAD0,
        stub_address=0x4207E0,
        cdll_pointer=cdll_pointer,
    )


def test_unreadable_wrapper_bytes_block_got_attribution() -> None:
    decision = attribute_loaded_wrapper(
        raw_selected=_observed_got(0x111),
        loaded_wrapper=None,
        elf_wrapper=b"elf-wrapper",
        **_applying_body(),
    )
    selected = decision["selected_call_target"]
    assert decision["loaded_wrapper_matches_elf"] is False
    assert decision["libm_body_argument"] == "BLOCKED"
    assert selected["classification"] == "NOT ESTABLISHED"
    assert selected["address"] is None
    assert selected["raw_got_pointer"] == hex(0x7F0000BAD0)
    assert selected["evidence"] == "python wrapper plt got"
    assert selected["independent_cdll_is_evidence"] is False


def test_mismatched_wrapper_bytes_block_got_attribution() -> None:
    decision = attribute_loaded_wrapper(
        raw_selected=_observed_got(0x7F0000BAD0),
        loaded_wrapper=b"loaded-wrapper",
        elf_wrapper=b"elf-wrapper",
        **_applying_body(),
    )
    selected = decision["selected_call_target"]
    assert decision["loaded_wrapper_matches_elf"] is False
    assert decision["libm_body_argument"] == "BLOCKED"
    assert selected["classification"] == "NOT ESTABLISHED"
    assert selected["address"] is None
    assert selected["raw_got_pointer"] == hex(0x7F0000BAD0)
    assert selected["addresses_equal"] is True
    assert selected["independent_cdll_is_evidence"] is False
    assert selected["evidence"] == "python wrapper plt got"


def test_matched_wrapper_certifies_the_selected_target() -> None:
    body = b"same-wrapper"
    decision = attribute_loaded_wrapper(
        raw_selected=_observed_got(0x1234),
        loaded_wrapper=body,
        elf_wrapper=body,
        **_applying_body(),
    )
    selected = decision["selected_call_target"]
    assert decision["loaded_wrapper_matches_elf"] is True
    assert decision["libm_body_argument"] == "APPLIES"
    assert selected["classification"] == "OBSERVED"
    assert selected["address"] == hex(0x7F0000BAD0)
    assert selected["independent_cdll_is_evidence"] is False
    assert "raw_got_pointer" not in selected


def test_unresolved_plt_stays_unresolved_and_cdll_is_not_evidence() -> None:
    raw = classify_selected_call(
        got_pointer=0x4207E6,
        stub_address=0x4207E0,
        cdll_pointer=0x7BAD0,
    )
    matched = attribute_loaded_wrapper(
        raw_selected=raw,
        loaded_wrapper=b"same",
        elf_wrapper=b"same",
        **_applying_body(),
    )
    mismatched = attribute_loaded_wrapper(
        raw_selected=raw,
        loaded_wrapper=None,
        elf_wrapper=b"elf",
        **_applying_body(),
    )
    for decision in (matched, mismatched):
        selected = decision["selected_call_target"]
        assert selected["classification"] == "NOT ESTABLISHED"
        assert selected["address"] is None
        assert selected["evidence"] == "python wrapper plt got"
        assert selected["independent_cdll_is_evidence"] is False
        assert "LD_BIND_NOW" in selected["method"]
        assert "CDLL" in selected["method"]
        assert decision["libm_body_argument"] == "BLOCKED"


def test_prepare_uses_wrapper_attribution_for_the_body_argument(monkeypatch) -> None:
    seen: dict = {}

    def fake_attribute(**kwargs):
        seen["raw_classification"] = kwargs["raw_selected"]["classification"]
        seen["loaded_is_none"] = kwargs["loaded_wrapper"] is None
        seen["elf_is_none"] = kwargs["elf_wrapper"] is None
        selected = dict(kwargs["raw_selected"])
        selected["classification"] = "NOT ESTABLISHED"
        selected["address"] = None
        selected["raw_got_pointer"] = kwargs["raw_selected"].get("address")
        return {
            "loaded_wrapper_matches_elf": False,
            "selected_call_target": selected,
            "libm_body_argument": "BLOCKED",
        }

    monkeypatch.setattr(cosine_certificate, "attribute_loaded_wrapper", fake_attribute)
    payload = _payload(cosine_certificate.prepare_cosine_path_certificate(_repository()))
    assert seen, "prepare must attribute the loaded wrapper before the libm body argument"
    assert payload["libm_body_argument"] == "BLOCKED"
    assert payload["selected_call_target"]["classification"] == "NOT ESTABLISHED"
    assert payload["python_wrapper"]["loaded_wrapper_matches_elf"] is False
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False


def _child_certificate(root: Path, mutation: str) -> dict:
    script = f"""
import json, sys
from pathlib import Path
import pyfoldable.application.c2v09_cosine_path_certificate as cert
root = Path(sys.argv[1])
mode = sys.argv[2]
if mode == "mismatch":
    real = cert._elf_bytes
    def mismatch(path, vaddr, length):
        data = real(path, vaddr, length)
        if not data:
            return data
        return bytes([data[0] ^ 0xFF]) + data[1:]
    cert._elf_bytes = mismatch
elif mode == "unreadable":
    real = cert.ctypes.string_at
    def guarded(address, size):
        if size == 0xC0:
            raise ValueError("unreadable wrapper")
        return real(address, size)
    cert.ctypes.string_at = guarded
payload = cert.prepare_cosine_path_certificate(root)["canonical_payload"]
selected = payload["selected_call_target"]
print(json.dumps({{
    "match": payload["python_wrapper"]["loaded_wrapper_matches_elf"],
    "classification": selected["classification"],
    "address": selected.get("address"),
    "raw": selected.get("raw_got_pointer"),
    "libm": payload["libm_body_argument"],
    "cdll_evidence": selected["independent_cdll_is_evidence"],
    "evidence": selected["evidence"],
    "method": selected["method"],
}}))
"""
    env = os.environ.copy()
    env["LD_BIND_NOW"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script, str(root), mutation],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_live_unreadable_wrapper_blocks_attribution() -> None:
    observed = _child_certificate(_repository(), "unreadable")
    assert observed["match"] is False
    assert observed["classification"] == "NOT ESTABLISHED"
    assert observed["address"] is None
    assert observed["libm"] == "BLOCKED"
    assert observed["cdll_evidence"] is False
    assert observed["evidence"] == "python wrapper plt got"
    assert observed["raw"] not in (None, "")


def test_live_mismatched_wrapper_blocks_attribution() -> None:
    observed = _child_certificate(_repository(), "mismatch")
    assert observed["match"] is False
    assert observed["classification"] == "NOT ESTABLISHED"
    assert observed["address"] is None
    assert observed["libm"] == "BLOCKED"
    assert observed["cdll_evidence"] is False
    assert observed["evidence"] == "python wrapper plt got"
    assert observed["raw"] not in (None, "")


def test_live_matched_wrapper_can_apply() -> None:
    observed = _child_certificate(_repository(), "matched")
    assert observed["match"] is True
    assert observed["classification"] == "OBSERVED"
    assert observed["address"]
    assert observed["libm"] == "APPLIES"
    assert observed["cdll_evidence"] is False
    assert observed["evidence"] == "python wrapper plt got"
    assert observed["raw"] is None


def test_historical_observation_bytes_and_limitations_stay_recorded() -> None:
    root = _repository()
    observation = root / "reports/c2v09_cosine_path_certificate/observation.json"
    assert sha256_bytes(observation.read_bytes()) == HISTORICAL_OBSERVATION_SHA256
    document = (root / "docs/cmm2_c2v09_one_runtime_cosine_path_certificate.md").read_text(encoding="utf-8")
    assert "CPUID leaf 7 overwrites the register checked for OSXSAVE" in document
    assert "OSXSAVE belongs to CPUID leaf 1 ECX" in document
    assert "unavailable XCR0 could be published as register zero" in document
    assert "calculated before the loaded wrapper bytes were compared" in document
    assert "f343a9b206b0169e96bf5e66548ee08d257c3806" in document
    assert "8a8fe2c2b1eb60cea016acec26d50fdcd902ee33ec57b81efa6273cb7fb3aaba" in document
