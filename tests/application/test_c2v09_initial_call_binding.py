"""Actual initial-call binding. The evaluator is not called."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pyfoldable.application.c2v09_initial_call_binding as binding_module
import pyfoldable.application.cmm2_coupled_transient_service as service
import pyfoldable.core.foldable_rotor as rotor
from pyfoldable.application.c2v09_cosine_path_certificate import prepare_cosine_path_certificate
from pyfoldable.application.c2v09_ordered_declaration import (
    _json_fence,
    _read_text,
    historical_manifest_bytes,
    sha256_bytes,
)
from pyfoldable.application.cmm2_coupled_transient_service import Cmm2FoldableBemMappedAeroEvaluator
from pyfoldable.core.config import load_design_config
from pyfoldable.core.foldable_aero_load import map_foldable_bem_aero_loads
from pyfoldable.core.foldable_rotor import solve_foldable_bem_rotor
from pyfoldable.application.c2v09_initial_call_binding import (
    binary64_hex,
    bind_initial_call,
    revalidate_initial_call_binding,
)
from pyfoldable.application.c2v09_pre_call_admission import prepare_pre_call_admission
from pyfoldable.application.c2v09_pre_call_binding import SOURCE_BINDING, observe_pre_call_binding


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def _native_unavailable(_root):
    return {"canonical_payload": {"selected_call_target": {"classification": "NOT ESTABLISHED"}, "cosine_function_calls": 0, "eligibility_evidence": False}}


def _observer(root):
    return observe_pre_call_binding(root, cosine_observer=_native_unavailable)


def _collector(_root):
    return {"canonical_payload": {"executing_dependencies": {}, "observations": {}, "source_callbacks": 0}}


def _admission():
    return prepare_pre_call_admission(
        _repository(),
        pre_call_observer=_observer,
        dependency_collector=_collector,
    )


def _native_double(_root):
    """A lookalike certificate. It is not this process's probe."""
    return {
        "canonical_payload": {
            "cosine_function_calls": 0,
            "compiled_probe_image_sha256": "ab" * 32,
            "probe_source_sha256": "cd" * 32,
            "selected_call_target": {
                "classification": "OBSERVED",
                "address": "0x1",
                "evidence": "python wrapper plt got",
                "got_slot": "0x2",
                "plt_stub": "0x3",
                "independent_cdll_is_evidence": False,
            },
            "python_wrapper": {"address": "0x4"},
            "loaded_body": {"sha256": "ef" * 32, "elf_vaddr": "0x7bad0", "matches_historical_body": True},
            "loaded_constants": [{"classification": "MATCH", "vaddr": "0x1"}],
            "numerical_controls_and_features": {
                "classification": "OBSERVED",
                "mxcsr": "0x1fa0",
                "fegetround": "0",
                "xcr0": ["0xe7", "0x0"],
            },
            "eligibility_evidence": False,
        }
    }


def _bind(**kwargs):
    arguments = {"admission": _admission(), "native_observer": _native_double}
    arguments.update(kwargs)
    return bind_initial_call(_repository(), **arguments)


def test_signed_zero_is_distinct_binary64() -> None:
    assert binary64_hex(-0.0) == "-0x0.0p+0"
    assert binary64_hex(0.0) == "0x0.0p+0"
    assert binary64_hex(-0.0) != binary64_hex(0.0)


def test_binding_uses_parsed_inputs_and_does_not_call_the_evaluator() -> None:
    bound = _bind()
    evaluator = bound.evaluator
    assert evaluator.successful_bem_solves == 0
    assert evaluator.successful_map_calls == 0
    assert evaluator.bounds == "error"
    assert len(evaluator.blade.stations) == 6
    assert bound.input_identity["station_r_over_r_hex"][0] == binary64_hex(0.2)
    assert bound.input_identity["hinge_radius_hex"] == binary64_hex(evaluator.hinge_radius_m)
    assert bound.input_identity["parsed_draft_matches_manifest"] is True
    assert bound.caller_claims_role == "not actual-input evidence"
    assert bound.initial_arguments["time_s"] == "NOT ESTABLISHED"
    assert bound.deferred_routines["clearance_granted"] is False
    assert all(row["classification"] == "MATCH" for row in bound.active_graph)
    assert bound.deferred_routines["solve_cmm2_transient"] == "NOT CLEARED"
    assert bound.applicability["status"] == "CONTRACT BLOCKED"
    assert bound.applicability["exact_historical_equality_assumed"] is False
    assert bound.applicability["equivalence_assumed"] is False
    assert bound.applicability["review_status"] == "UNREVIEWED"
    assert bound.applicability["proof_roles"]["exact_historical_equality"] == "NOT A PROOF"
    assert bound.applicability["proof_roles"]["equivalence"] == "NOT A PROOF"
    assert bound.applicability["proof_roles"]["body_match"] == "historical libm body predicate only"
    assert all(row["defaults"] == "MATCH" for row in bound.active_graph)
    assert all(row["constants"] == "MATCH" for row in bound.active_graph)
    assert all(row["globals"] != "MISMATCH" for row in bound.active_graph)
    assert bound.input_identity["parsed_correspondence"] == "MATCH"
    assert bound.revalidation_classification == "REVALIDATED"
    assert bound.post_return["returned_source_object"] == "POST-RETURN ONLY"
    assert bound.post_return["mapped_interval_consumption"] == "POST-RETURN ONLY"
    assert bound.candidate29_disposition == "NOT SELECTED"
    assert bound.eligibility_evidence is False
    assert bound.physical_qualification is False
    assert bound.authorizes_execution is False
    assert bound.dependent_counters == {"source": 0, "mapper": 0, "partition": 0, "selection": 0, "seal": 0, "trajectory": 0}
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"


def test_caller_claim_does_not_replace_parsed_hinge() -> None:
    bound = _bind(caller_claims={"hinge_radius_m": 1.0, "draft_sha256": "0" * 64})
    assert bound.evaluator.hinge_radius_m != 1.0
    assert bound.caller_claims["hinge_radius_m"] == 1.0


def test_draft_source_and_polar_bytes_are_the_parsed_inputs() -> None:
    bound = _bind(caller_claims={"source_sha256": "11" * 32})
    manifest = json.loads(_json_fence(_read_text(_repository(), "docs/cmm2_c2v09_candidate29_proposal.md"), 0))
    draft = str(manifest["draft_toml"]).encode("utf-8")
    recipe = historical_manifest_bytes(manifest["source_recipe"])
    assert bound.retained["draft_bytes"] == draft
    assert bound.retained["source_recipe_bytes"] == recipe
    assert sha256_bytes(draft) == manifest["effective_binding"]["draft_sha256"]
    assert sha256_bytes(recipe) == manifest["effective_binding"]["source_sha256"]
    assert bound.input_identity["draft_bytes_sha256"] == sha256_bytes(draft)
    assert bound.input_identity["source_recipe_bytes_sha256"] == sha256_bytes(recipe)
    assert bound.input_identity["parsed_correspondence"] == "MATCH"
    assert bound.caller_claims["source_sha256"] == "11" * 32
    assert bound.input_identity["source_recipe_bytes_sha256"] != bound.caller_claims["source_sha256"]
    alphas = bound.input_identity["polar_alpha_hex"]
    assert "0x0.0p+0" in alphas
    assert "-0x0.0p+0" not in alphas
    assert bound.input_identity["environment_air_density_hex"] == binary64_hex(bound.evaluator.environment.air_density_kg_m3)


def test_input_and_code_mutations_invalidate_and_restore() -> None:
    bound = _bind()
    original_hinge = bound.evaluator.hinge_radius_m
    try:
        bound.evaluator.hinge_radius_m = original_hinge + 0.01
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        bound.evaluator.hinge_radius_m = original_hinge
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"

    function = Cmm2FoldableBemMappedAeroEvaluator.__call__
    original = function.__code__
    try:
        function.__code__ = original.replace(co_consts=original.co_consts + ("mutated",))
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        function.__code__ = original

    original_polars = bound.evaluator.polars
    try:
        bound.evaluator.polars = object()
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        bound.evaluator.polars = original_polars
    original_draft = bound.retained["draft_bytes"]
    try:
        bound.retained["draft_bytes"] = original_draft + b"\n"
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        bound.retained["draft_bytes"] = original_draft
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"


def test_field_writes_invalidate_retained_inputs() -> None:
    bound = _bind()
    station = bound.evaluator.blade.stations[0]
    original_radius = station.r_over_R
    try:
        object.__setattr__(station, "r_over_R", 0.3)
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        object.__setattr__(station, "r_over_R", original_radius)
    original_bounds = bound.evaluator.bounds
    try:
        object.__setattr__(bound.evaluator, "bounds", "clamp")
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        object.__setattr__(bound.evaluator, "bounds", original_bounds)
    original_count = bound.evaluator.settings.annulus_count
    try:
        object.__setattr__(bound.evaluator.settings, "annulus_count", original_count + 1)
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        object.__setattr__(bound.evaluator.settings, "annulus_count", original_count)
    table = bound.evaluator.polars.anchors[0].family.tables[0]
    original_cl = table.cl
    try:
        object.__setattr__(table, "cl", original_cl + (original_cl[0],))
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        object.__setattr__(table, "cl", original_cl)
    original_temperature = bound.evaluator.environment.temperature_k
    try:
        object.__setattr__(bound.evaluator.environment, "temperature_k", 1.0)
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        object.__setattr__(bound.evaluator.environment, "temperature_k", original_temperature)
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"


def test_loaded_global_and_callee_code_mutations_invalidate() -> None:
    bound = _bind()
    original_limit = service.OMEGA_MIN
    try:
        service.OMEGA_MIN = -1.0
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        service.OMEGA_MIN = original_limit
    original_code = rotor.project_foldable_blade.__code__
    try:
        rotor.project_foldable_blade.__code__ = original_code.replace(co_consts=original_code.co_consts + ("mutated",))
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
        rebound = _bind()
        solve_row = next(row for row in rebound.active_graph if row["qualname"] == "solve_foldable_bem_rotor")
        assert solve_row["classification"] == "MISMATCH"
        assert solve_row["globals"] == "MISMATCH"
    finally:
        rotor.project_foldable_blade.__code__ = original_code
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"


def test_manifest_hinge_disagreement_is_not_correspondence_match(monkeypatch) -> None:
    original = binding_module._candidate

    def shifted(root):
        manifest = original(root)
        effective = dict(manifest["effective_binding"])
        effective["hinge_radius_m"] = 0.2
        manifest["effective_binding"] = effective
        return manifest

    monkeypatch.setattr(binding_module, "_candidate", shifted)
    bound = _bind()
    assert bound.evaluator.hinge_radius_m != 0.2
    assert bound.input_identity["parsed_draft_matches_manifest"] is False
    assert bound.input_identity["parsed_correspondence"] == "MISMATCH"


def test_default_and_global_mutations_invalidate_and_restore() -> None:
    bound = _bind()
    function = solve_foldable_bem_rotor
    original_keywords = function.__kwdefaults__
    try:
        function.__kwdefaults__ = {"bounds": "clamp", "settings": None}
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        function.__kwdefaults__ = original_keywords
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"

    original = rotor.project_foldable_blade

    def other(*_args, **_kwargs):
        raise AssertionError("source evaluated")

    rotor.project_foldable_blade = other
    try:
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        rotor.project_foldable_blade = original
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"


def test_active_graph_code_replacement_invalidates(monkeypatch) -> None:
    bound = _bind()
    for function in (
        solve_foldable_bem_rotor,
        map_foldable_bem_aero_loads,
        load_design_config,
        Cmm2FoldableBemMappedAeroEvaluator.__init__,
    ):
        original = function.__code__
        try:
            function.__code__ = original.replace(co_consts=original.co_consts + ("mutated",))
            assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
        finally:
            function.__code__ = original
        assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"


def test_global_replacement_and_stale_context_invalidate(monkeypatch) -> None:
    bound = _bind()

    def other(*_args, **_kwargs):
        raise AssertionError("source evaluated")

    monkeypatch.setattr(service, SOURCE_BINDING, other)
    assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    monkeypatch.undo()
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"
    bound.thread_id = bound.thread_id + "-other"
    assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"


def test_test_double_native_and_archive_are_not_genuine() -> None:
    bound = _bind()
    assert bound.native_observation["kind"] == "test_double"
    assert bound.native_observation["compiled_probe_image_sha256"] is None
    assert bound.native_observation["got_slot"] is None
    assert bound.applicability["native_is_genuine"] is False
    assert revalidate_initial_call_binding({"kind": "archived", "native_observation": {"kind": "genuine"}}).classification == "NOT ESTABLISHED"


def test_binding_does_not_invoke_source(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("source evaluated")

    monkeypatch.setattr(service, SOURCE_BINDING, forbidden)
    monkeypatch.setattr(service, "map_foldable_bem_aero_loads", forbidden)
    bound = _bind()
    assert bound.dependent_counters["source"] == 0
    assert bound.evaluator.successful_bem_solves == 0


def test_bind_now_process_keeps_probe_image_and_control_changes(tmp_path: Path) -> None:
    root = _repository()
    script = tmp_path / "bind_now_check.py"
    script.write_text(
        "import ctypes, json, sys\n"
        "from pathlib import Path\n"
        "from pyfoldable.application.c2v09_cosine_path_certificate import prepare_cosine_path_certificate\n"
        "from pyfoldable.application.c2v09_initial_call_binding import bind_initial_call, revalidate_initial_call_binding\n"
        "from pyfoldable.application.c2v09_pre_call_admission import prepare_pre_call_admission\n"
        "from pyfoldable.application.c2v09_pre_call_binding import observe_pre_call_binding\n"
        "root = Path(sys.argv[1])\n"
        "def unavailable(_root):\n"
        "    return {'canonical_payload': {'selected_call_target': {'classification': 'NOT ESTABLISHED'}, 'cosine_function_calls': 0, 'eligibility_evidence': False}}\n"
        "def observer(path):\n"
        "    return observe_pre_call_binding(path, cosine_observer=unavailable)\n"
        "def collector(_root):\n"
        "    return {'canonical_payload': {'executing_dependencies': {}, 'observations': {}, 'source_callbacks': 0}}\n"
        "admission = prepare_pre_call_admission(root, pre_call_observer=observer, dependency_collector=collector)\n"
        "bound = bind_initial_call(root, admission=admission, native_observer=prepare_cosine_path_certificate)\n"
        "native = bound.native_observation\n"
        "library = ctypes.CDLL('libm.so.6')\n"
        "library.fesetround.argtypes = [ctypes.c_int]\n"
        "library.fesetround(0x800)\n"
        "try:\n"
        "    changed = revalidate_initial_call_binding(bound).classification\n"
        "finally:\n"
        "    library.fesetround(0)\n"
        "restored = revalidate_initial_call_binding(bound).classification\n"
        "import pyfoldable.application.c2v09_cosine_path_certificate as certificate\n"
        "original_qword = certificate._read_qword\n"
        "certificate._read_qword = lambda _address: 16\n"
        "try:\n"
        "    target_changed = revalidate_initial_call_binding(bound).classification\n"
        "finally:\n"
        "    certificate._read_qword = original_qword\n"
        "target_restored = revalidate_initial_call_binding(bound).classification\n"
        "json.dump({\n"
        "    'kind': native['kind'],\n"
        "    'evidence': native['evidence'],\n"
        "    'got_slot': native['got_slot'],\n"
        "    'plt_stub': native['plt_stub'],\n"
        "    'wrapper_address': native['wrapper_address'],\n"
        "    'selected_address': native['selected_address'],\n"
        "    'compiled_probe_image_sha256': native['compiled_probe_image_sha256'],\n"
        "    'probe_source_sha256': native['probe_source_sha256'],\n"
        "    'body_sha256': native['loaded_body_sha256'],\n"
        "    'calls': native['cosine_function_calls'],\n"
        "    'solves': bound.evaluator.successful_bem_solves,\n"
        "    'applicability': bound.applicability['status'],\n"
        "    'equality_assumed': bound.applicability['exact_historical_equality_assumed'],\n"
        "    'equivalence_assumed': bound.applicability['equivalence_assumed'],\n"
        "    'body_role': bound.applicability['proof_roles']['body_match'],\n"
        "    'mismatches': bound.applicability['historical_mismatches'],\n"
        "    'xcr0': bound.applicability['historical_xcr0'],\n"
        "    'body_clears_xcr0': bound.applicability['body_match_clears_xcr0'],\n"
        "    'changed': changed,\n"
        "    'restored': restored,\n"
        "    'target_changed': target_changed,\n"
        "    'target_restored': target_restored,\n"
        "    'deferred': bound.deferred_routines['cmm2_radau_dense'],\n"
        "    'clearance': bound.deferred_routines['clearance_granted'],\n"
        "}, sys.stdout)\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["LD_BIND_NOW"] = "1"
    env["PYTHONPATH"] = str(root)
    completed = subprocess.run(
        [sys.executable, str(script), str(root)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=root,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["kind"] == "genuine"
    assert payload["evidence"] == "python wrapper plt got"
    assert payload["got_slot"]
    assert payload["plt_stub"]
    assert payload["wrapper_address"]
    assert payload["selected_address"]
    assert payload["compiled_probe_image_sha256"]
    assert payload["compiled_probe_image_sha256"] != payload["probe_source_sha256"]
    assert payload["calls"] == 0
    assert payload["solves"] == 0
    assert payload["applicability"] == "CONTRACT BLOCKED"
    assert payload["equality_assumed"] is False
    assert payload["equivalence_assumed"] is False
    assert payload["body_role"] == "historical libm body predicate only"
    assert payload["body_clears_xcr0"] is False
    authority = subprocess.call(
        ["git", "cat-file", "-e", "fd55fa97676c84c896511765e94561a706252239^{commit}"],
        cwd=root,
        stderr=subprocess.DEVNULL,
    ) == 0
    if authority:
        assert payload["xcr0"]["classification"] == "MISMATCH"
        assert "historical XCR0" in payload["mismatches"]
    else:
        assert payload["xcr0"]["classification"] == "NOT ESTABLISHED"
    assert payload["changed"] == "INVALIDATED"
    assert payload["restored"] == "REVALIDATED"
    assert payload["target_changed"] == "INVALIDATED"
    assert payload["target_restored"] == "REVALIDATED"
    assert payload["deferred"] == "NOT CLEARED"
    assert payload["clearance"] is False
