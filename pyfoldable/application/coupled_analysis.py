"""Application service for the optional DUST–MBDyn–preCICE dynamic analysis.

Binds the same ResearchDesign, catalog profile and retained-provider admission
used by the fully deployed BEM to a declared coupled case. Explicit actions
only: preparation writes nothing; ``start_run`` creates one fresh run
directory and launches a detached supervisor; results are read from that
directory. Missing toolchains never affect the BEM route.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import gzip
import hashlib
import json
import lzma
import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zlib

from pyfoldable.coupled import MODEL_ID, SCHEMA_VERSION
from pyfoldable.coupled import c81 as c81mod
from pyfoldable.coupled import deck as deckmod
from pyfoldable.coupled import postprocess
from pyfoldable.coupled import toolchain as tcmod
from pyfoldable.coupled.model import CoupledCase, CoupledCaseError, CoupledControls, CoupledMechanics, build_case
from pyfoldable.coupled.postprocess import digest

from . import research_design as research

PARTICIPANTS = Path(__file__).resolve().parents[1] / "coupled" / "participants"
# Canonical (uncompressed) record bound: the whole record is parsed, re-verified and kept in the
# session; measured restore of a 16.6 MB record peaks at ~215 MB RSS.
MAX_COUPLED_RESULT_BYTES = 24 * 1024 * 1024
# Compressed transport bound (gzip of the same canonical JSON; measured ratio ~3x).
MAX_COUPLED_ARCHIVE_BYTES = 12 * 1024 * 1024
GZIP_MAGIC = b"\x1f\x8b"
XZ_MAGIC = b"\xfd7zXZ\x00"
# xz decoder memory bound: preset 6 needs < 16 MiB; streams declaring larger dictionaries are refused.
XZ_MEMLIMIT_BYTES = 16 * 1024 * 1024
XZ_PRESET = 6  # ~3.6x on recorded runs; the 720-window main record is 4.60 MB (fits a 5 MiB upload limit)
# Controls added after records were first written, with the meaning older records had.
# A saved record lacking such a field is restored with exactly this value (identical decks).
LEGACY_CONTROL_DEFAULTS = {"vortex_stretching": True, "aero_topology": "split_rigid"}
RUNS_ENV = "PYFOLDABLE_COUPLED_RUNS"


def runs_root(repo_root: Path) -> Path:
    return Path(os.environ.get(RUNS_ENV) or repo_root / "outputs" / "coupled_runs")


@dataclass(frozen=True)
class CoupledPreparation:
    request: dict
    case: CoupledCase
    deck: dict
    c81_text: str
    toolchain: tcmod.Readiness

    @property
    def request_sha256(self) -> str:
        return self.request["request_sha256"]


class CoupledPreparationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def preflight_ranges(case: CoupledCase) -> dict:
    """No-induction section states for the open blade and the declared release.

    A readiness hint only: induction, wake and hinge motion change the visited
    states. The coupled run audits every accepted step against the table.
    """
    g, m = case.geometry, case.mechanics
    rows = []
    for sections, distal in ((g.proximal_sections, False), (g.distal_sections, True)):
        for s in sections:
            for fold in ((0.0, m.initial_fold_rad) if distal else (0.0,)):
                s_from_hinge = s.radius_m - g.hinge_radius_m
                tangential = (case.omega_rad_s * (g.hinge_radius_m * math.cos(fold) + s_from_hinge)) if distal \
                    else case.omega_rad_s * s.radius_m
                speed = math.hypot(case.inflow_m_s, tangential)
                rows.append((math.degrees(s.twist_rad - math.atan2(case.inflow_m_s, tangential)),
                             case.density_kg_m3 * speed * s.chord_m / case.viscosity_pa_s,
                             speed / case.speed_of_sound_m_s))
    return {"alpha_deg": [min(r[0] for r in rows), max(r[0] for r in rows)],
            "reynolds": [min(r[1] for r in rows), max(r[1] for r in rows)],
            "mach": [min(r[2] for r in rows), max(r[2] for r in rows)]}


def estimated_result_bytes(case: CoupledCase) -> int:
    return postprocess.estimated_result_bytes(case, len(deckmod.coupling_nodes(case)))


def supported_duration(case: CoupledCase) -> dict:
    """Longest simulated time whose complete record stays restorable at this step and discretization.

    The record keeps every accepted window (no thinning), so this is a storage bound, stated before a
    run; it is not a physical settling time. Also bounded by the duration control's own limit."""
    from pyfoldable.coupled.model import MAX_DURATION_S
    per = postprocess.estimated_bytes_per_window(case, len(deckmod.coupling_nodes(case)))
    windows = max(0, (MAX_COUPLED_RESULT_BYTES - postprocess.RESULT_FIXED_BYTES) // per)
    limited_by = "record_size"
    if windows * case.dt_s > MAX_DURATION_S:
        windows, limited_by = int(math.floor(MAX_DURATION_S / case.dt_s + 1e-9)), "duration_control"
    duration = windows * case.dt_s
    return {"windows": int(windows), "duration_s": duration, "revolutions": duration * case.omega_rad_s / (2 * math.pi),
            "limit_bytes": MAX_COUPLED_RESULT_BYTES, "bytes_per_window": per, "limited_by": limited_by}


def check_result_budget(case: CoupledCase) -> None:
    """Fail closed before running when the complete record could not be restored (size cap)."""
    est = estimated_result_bytes(case)
    if est > MAX_COUPLED_RESULT_BYTES:
        lim = supported_duration(case)
        raise CoupledPreparationError(
            "result_too_large",
            f"Tahmini sonuç kaydı {est / 2**20:.1f} MiB, sınır {MAX_COUPLED_RESULT_BYTES / 2**20:.0f} MiB. "
            f"Bu azimut adımı ve eleman sayısıyla desteklenen en uzun süre {lim['duration_s']:.3f} s "
            f"({lim['revolutions']:.1f} devir, {lim['windows']} pencere): süreyi kısaltın veya azimut adımını büyütün. "
            "Kayıt her kabul edilen pencereyi saklar; örnek seyreltilmez.")


def record_json_bytes(row: dict) -> bytes:
    """Canonical record bytes (identical to the JSON download)."""
    return (json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            + "\n").encode("utf-8")


def record_archive_bytes(row: dict) -> bytes:
    """Lossless compressed transport of the same canonical record (single gzip member, no timestamp)."""
    return gzip.compress(record_json_bytes(row), compresslevel=6, mtime=0)


def record_xz_bytes(row: dict) -> bytes:
    """Denser lossless transport of the same canonical record (one .xz stream, CRC64). Repeatable for a
    given liblzma build, not guaranteed bit-identical across builds; the record's own result_sha256
    identifies the content. Slower to encode (seconds), so the UI prepares it only on request."""
    return lzma.compress(record_json_bytes(row), format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=XZ_PRESET)


def _inflate_xz(raw: bytes) -> bytes:
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=XZ_MEMLIMIT_BYTES)
    try:
        out = decoder.decompress(raw, MAX_COUPLED_RESULT_BYTES + 1)
    except lzma.LZMAError as exc:
        raise ValueError("Coupled archive is not a valid xz stream within the decoder memory limit.") from exc
    _require(len(out) <= MAX_COUPLED_RESULT_BYTES, "Coupled result size is invalid.")
    _require(decoder.eof, "Coupled archive is truncated.")
    _require(not decoder.unused_data, "Coupled archive has trailing data.")
    return out


def _inflate_record(raw: bytes) -> bytes:
    """Bounded decompression of a gzip member or an xz stream: one complete stream (integrity
    checked), no trailing data, output never larger than the canonical record bound."""
    _require(len(raw) <= MAX_COUPLED_ARCHIVE_BYTES, "Coupled archive size is invalid.")
    if raw[:6] == XZ_MAGIC:
        return _inflate_xz(raw)
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = inflater.decompress(raw, MAX_COUPLED_RESULT_BYTES + 1)
    except zlib.error as exc:
        raise ValueError("Coupled archive is not a valid gzip stream.") from exc
    _require(len(out) <= MAX_COUPLED_RESULT_BYTES and not inflater.unconsumed_tail, "Coupled result size is invalid.")
    _require(inflater.eof, "Coupled archive is truncated.")
    _require(not inflater.unused_data, "Coupled archive has trailing data.")
    return out


def prepare(active, family, repository, mechanics: CoupledMechanics, controls: CoupledControls,
            *, readiness: tcmod.Readiness | None = None) -> CoupledPreparation:
    """No solver, no file writes. Raises CoupledPreparationError with a stable code."""
    readiness = readiness or tcmod.readiness()
    if readiness.status != "ready":
        raise CoupledPreparationError("toolchain_" + readiness.status, readiness.message)
    try:
        prepared = research.prepare_aero(active, family, repository)
    except (ValueError, OSError) as exc:
        raise CoupledPreparationError("aero_admission_rejected", str(exc)) from exc
    admission = json.loads(prepared.admission_json)
    if admission.get("evidence_class") == "inert_fixture":
        raise CoupledPreparationError("inert_fixture_tables", "Test fixture tables cannot enter a coupled engineering run.")
    tables = c81mod.admitted_tables(admission)
    table = c81mod.build_c81(tables)
    try:
        case = build_case(active, mechanics, controls)
    except CoupledCaseError as exc:
        raise CoupledPreparationError(exc.code, str(exc)) from exc
    check_result_budget(case)
    files = deckmod.generate_deck(case, table.text, coupled=True)
    scripts = {name: _sha_text((PARTICIPANTS / name).read_text(encoding="utf-8")) for name in ("adapter.py", "extract_dust.py")}
    request = {
        "schema_version": SCHEMA_VERSION, "artifact_class": "pyfoldable_coupled_request", "model_id": MODEL_ID,
        "research": {"input_sha256": active.identity, "inputs": asdict(active.inputs),
                     "draft_toml": active.draft.toml, "draft_sha256": active.draft.draft_sha256,
                     "draft_source_sha256": active.draft.source_sha256,
                     "template_toml": active.template.source_bytes.decode("utf-8"),
                     "template_identity": active.template.source_identity,
                     "length_order_policy": active.length_order_policy,
                     "root": None if active.root is None else asdict(active.root),
                     "coordinate_sha256": active.coordinate_sha256},
        "aero_admission": {"request_sha256": prepared.request_sha256, "family_id": admission["family_id"],
                           "stored_version_sha256": (admission.get("stored_version") or {}).get("content_sha256"),
                           "evidence_class": admission["evidence_class"], "provider_policy": admission["provider_policy"],
                           "source_identity": admission["source_identity"], "tables": c81mod.tables_summary(tables)},
        "c81": {"sha256": table.sha256, "envelope": table.envelope, "text": table.text,
                "source_table_sha256": list(table.source_table_sha256)},
        "mechanics": asdict(mechanics), "controls": asdict(controls), "drive": case.drive,
        "case_sha256": digest(case.as_dict()), "deck": deckmod.deck_manifest(files),
        "participant_scripts_sha256": scripts, "toolchain": readiness.identity,
        "preflight_no_induction_ranges": preflight_ranges(case),
    }
    request["request_sha256"] = digest(request)
    return CoupledPreparation(request, case, files, table.text, readiness)


def start_run(prep: CoupledPreparation, repo_root: Path) -> Path:
    """Create a fresh run directory and launch the detached supervisor."""
    root = runs_root(repo_root)
    root.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + prep.request_sha256[:10]
    run = root / run_id
    run.mkdir(exist_ok=False)
    deckmod.write_deck(run, prep.deck)
    (run / "dust" / "Output").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PARTICIPANTS / "adapter.py", run / "structure" / "adapter.py")
    shutil.copyfile(PARTICIPANTS / "extract_dust.py", run / "extract_dust.py")
    (run / "toolchain.json").write_text(json.dumps(prep.toolchain.toolchain.manifest, indent=1))
    (run / "request.json").write_text(json.dumps(prep.request, indent=1))
    definition = deckmod.run_definition(prep.case, prep.deck, {"request_sha256": prep.request_sha256})
    (run / "run_definition.json").write_text(json.dumps(definition, indent=1, default=list))
    (run / "status.json").write_text(json.dumps({"state": "queued", "n_windows": prep.case.n_steps, "windows_accepted": 0}))
    env = dict(os.environ, PYTHONPATH=str(repo_root) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    with open(run / "supervisor.log", "w") as log:
        subprocess.Popen([sys.executable, "-m", "pyfoldable.coupled.supervisor", str(run)], cwd=repo_root,
                         env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return run


def poll(run: Path) -> dict:
    try:
        return json.loads((run / "status.json").read_text())
    except (OSError, ValueError):
        return {"state": "unknown"}


def cancel(run: Path) -> None:
    (run / "cancel.request").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"))


def load_result(run: Path) -> dict:
    raw = (run / "result.json").read_bytes()
    return read_saved_coupled_result(raw)


# ---------------------------------------------------------------------------
# Flow companion: extracted on request from retained DUST outputs (no solver run).

FLOW_TIMEOUT_S = 1800


def local_run_dir(root: Path, row: dict) -> Path | None:
    """The record's own run folder on this computer: inside the runs root, holding this very record
    (its result.json carries the same result_sha256) and its DUST outputs. Flow data lives there."""
    run_id = str(row.get("raw_outputs", {}).get("run_id", ""))
    if (not run_id or any(c in run_id for c in "/\\:\0") or run_id in (".", "..") or Path(run_id).is_absolute()
            or not re.fullmatch(r"[0-9A-Za-z_.-]+", run_id)):
        return None
    base = runs_root(root).resolve()
    d = (base / run_id).resolve()
    if d.parent != base or not (d / "result.json").is_file() or not (d / "dust" / "Output").is_dir():
        return None
    try:  # the sealed JSON is compact; its top-level digest appears exactly once
        raw = (d / "result.json").read_bytes()
    except OSError:
        return None
    key = b'"result_sha256":"' + str(row.get("result_sha256", "")).encode() + b'"'
    return d if raw.count(b'"result_sha256":') == 1 and key in raw else None


def load_flow(root: Path, row: dict):
    """Verified flow companion of ``row`` or a FlowCompanionError explaining why it is unavailable."""
    from pyfoldable.coupled import flow
    d = local_run_dir(root, row)
    if d is None:
        raise flow.FlowCompanionError("no_run_folder", "Bu kaydın çalıştırma klasörü bu bilgisayarda yok; akış verisi "
                                                       "ham DUST çıktılarından üretilir ve kayıtla taşınmaz.")
    return flow.load(d, row)


def build_flow(root: Path, row: dict, *, max_frames: int = 81, readiness: tcmod.Readiness | None = None):
    """Explicit action: extract the flow companion from the record's retained DUST outputs with the
    attested toolchain (coupling venv + dust_post). Never starts a solver; verifies the result."""
    from pyfoldable.coupled import flow
    d = local_run_dir(root, row)
    if d is None:
        raise flow.FlowCompanionError("no_run_folder", "Bu kaydın çalıştırma klasörü bu bilgisayarda yok.")
    readiness = readiness or tcmod.readiness(hash_executables=True)
    if readiness.status != "ready":
        raise flow.FlowCompanionError("toolchain_" + readiness.status, readiness.message)
    tc = readiness.toolchain
    windows = flow.select_windows(row, max_frames)
    if not windows:
        raise flow.FlowCompanionError("no_windows", "Kabul edilen pencere yok.")
    missing = [w for w in windows if f"dust/Output/run_res_{w:04d}.h5" not in row["raw_outputs"]["files"]]
    if missing:
        raise flow.FlowCompanionError("source_missing", f"Kayıtta listelenmeyen DUST çıktısı: pencere {missing[0]}.")
    out = flow.companion_dir(d)
    out.mkdir(exist_ok=True)
    spec = {"result_sha256": row["result_sha256"], "windows": windows, "dust_post": tc.exe("dust_post"),
            "plane": flow.default_plane(row)}
    (out / "spec.json").write_text(json.dumps(spec, indent=1))
    proc = subprocess.Popen([tc.exe("coupling_python"), "-I", str(PARTICIPANTS / "extract_flow.py"), str(d),
                             str(out / "spec.json")], cwd=d, env=tc.environment(), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        log, _ = proc.communicate(timeout=FLOW_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        import signal
        os.killpg(proc.pid, signal.SIGKILL)  # extractor and dust_post together
        proc.communicate()
        raise flow.FlowCompanionError("timeout", f"Akış verisi çıkarma süresi ({FLOW_TIMEOUT_S} s) aşıldı.")
    (out / "extract_flow.log").write_text(log or "")
    if proc.returncode != 0:
        raise flow.FlowCompanionError("extraction_failed", "Akış verisi çıkarılamadı; ayrıntı flow/extract_flow.log.")
    return flow.load(d, row)


# ---------------------------------------------------------------------------
# Restoration: content consistency only, never a re-run, never authentication.


class _ActiveLike:
    """Minimal ResearchDesign view rebuilt from a saved draft (no current defaults)."""

    def __init__(self, inputs, design, root, policy):
        self.inputs, self.design, self.root, self.length_order_policy = inputs, design, root, policy


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise ValueError(message)


def _case_from_request(req: dict, overrides: dict | None = None):
    """Declared case of a saved request, rebuilt from its own draft, inputs, mechanics and controls."""
    from pyfoldable.application import design_analysis
    from pyfoldable.application.design_draft import DesignDraftArtifact
    from pyfoldable.application.provider_design_analysis import RootDatum

    rs = req["research"]
    _require(hashlib.sha256(rs["draft_toml"].encode()).hexdigest() == rs["draft_sha256"], "Saved draft checksum mismatch.")
    draft = DesignDraftArtifact("saved.toml", rs["draft_toml"], rs["draft_source_sha256"], rs["draft_sha256"])
    design, angle = design_analysis._load_geometry(draft)
    _require(angle == 0, "Saved draft is not the open reference pose.")
    inputs = research.ResearchInputs(**rs["inputs"])
    root = None if rs["root"] is None else RootDatum(**rs["root"])
    active = _ActiveLike(inputs, design, root, rs["length_order_policy"])
    mech = CoupledMechanics(**req["mechanics"])
    missing = set(asdict(CoupledControls())) - set(req["controls"])
    _require(missing <= set(LEGACY_CONTROL_DEFAULTS),
             "Saved controls lack a field without a declared legacy meaning.")
    ctrl = CoupledControls(**{**{k: LEGACY_CONTROL_DEFAULTS[k] for k in missing}, **req["controls"], **(overrides or {})})
    return build_case(active, mech, ctrl), inputs


def case_from_record(row: dict, **control_overrides) -> CoupledCase:
    """Case of a saved record (optionally with changed controls, e.g. for budget estimates)."""
    return _case_from_request(row["request"], control_overrides)[0]


def read_saved_coupled_result(raw: bytes) -> dict:
    from pyfoldable.coupled.frames import relative_angle_about_z, rotvec_to_matrix

    if isinstance(raw, bytes) and (raw[:2] == GZIP_MAGIC or raw[:6] == XZ_MAGIC):
        raw = _inflate_record(raw)
    _require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_COUPLED_RESULT_BYTES, "Coupled result size is invalid.")

    def unique(pairs):
        out = {}
        for k, v in pairs:
            _require(k not in out, "Duplicate key in coupled result.")
            out[k] = v
        return out
    try:
        row = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
        body = {k: v for k, v in row.items() if k != "result_sha256"}
        _require(row.get("result_sha256") == digest(body), "Coupled result checksum mismatch.")
        _require(row.get("schema_version") == SCHEMA_VERSION and row.get("artifact_class") == "pyfoldable_coupled_result",
                 "Unsupported coupled result version.")
        _require(row["physical_qualification"] is False and row["reference_agreement"] == "NOT_ASSESSED",
                 "Coupled result scope flags were altered.")
        req = row["request"]
        req_body = {k: v for k, v in req.items() if k != "request_sha256"}
        _require(req["request_sha256"] == digest(req_body), "Coupled request digest mismatch.")
        # 1. draft and geometry
        case, inputs = _case_from_request(req)
        recorded = case.as_dict()
        recorded["controls"] = {k: v for k, v in recorded["controls"].items() if k in req["controls"]}
        _require(digest(recorded) == req["case_sha256"], "Saved case contradicts the saved draft and inputs.")
        _require(digest(recorded) == digest(row["run_definition"]["case"]), "Run definition case mismatch.")
        # 2. aerodynamic table regenerated from the retained admitted tables
        table = c81mod.build_c81(req["aero_admission"]["tables"])
        _require(table.sha256 == req["c81"]["sha256"] and table.text == req["c81"]["text"], "Saved C81 table mismatch.")
        _require(all(t["airfoil_id"] == inputs.profile for t in req["aero_admission"]["tables"]), "Table profile mismatch.")
        # 3. decks regenerated
        files = deckmod.generate_deck(case, table.text, coupled=True)
        _require(deckmod.deck_manifest(files) == req["deck"] == row["run_definition"]["deck"], "Saved decks do not match.")
        # coupling nodes and bodies drive the hinge moment, element labels and 3-D placement
        rd = row["run_definition"]
        regen = json.loads(json.dumps(deckmod.coupling_nodes(case)))
        saved = rd["coupling_nodes"]
        core = {"blade", "segment", "mbdyn_label", "dust_component", "local", "global"}
        _require(isinstance(saved, list) and len(saved) == len(regen)
                 and all(isinstance(s, dict) and core <= set(s) and s == {k: g[k] for k in s} for s, g in zip(saved, regen))
                 and ("bodies" not in rd or rd["bodies"] == json.loads(json.dumps(deckmod.bodies(case)))),
                 "Saved coupling nodes or bodies do not match the case.")
        # 4. derived channels recomputed from exchanged loads and MBDyn node states
        ex = row["execution"]
        series, wins, states = row["series"], row["window_exchange"], {s["window"]: s["nodes"] for s in row["node_states"]}
        _require(len(series) == len(wins) == ex["windows_accepted"], "Accepted window count mismatch.")
        W = case.omega_rad_s
        for r, w in zip(series, wins):
            _require(r["window"] == w["window"], "Window order mismatch.")
            F, M, X = w["force"], w["moment"], w["position"]
            _require(math.isclose(r["thrust_n"], sum(f[2] for f in F), rel_tol=0, abs_tol=1e-9), "Thrust does not match exchanged loads.")
            mz = sum(M[i][2] + X[i][0] * F[i][1] - X[i][1] * F[i][0] for i in range(len(F)))
            _require(math.isclose(r["aero_shaft_torque_nm"], -mz, rel_tol=0, abs_tol=1e-9), "Aero torque does not match exchanged loads.")
            nodes = states[r["window"]]
            for b in range(case.geometry.blade_count):
                th = relative_angle_about_z(rotvec_to_matrix(nodes[str(100 + b)]["phi"]), rotvec_to_matrix(nodes[str(200 + b)]["phi"]))
                _require(abs(math.degrees(th) - r["theta_deg"][b]) < 1e-9, "Hinge angle does not match node states.")
                cn = row["run_definition"]["coupling_nodes"]
                m_h = postprocess.hinge_aero_torque(cn, b, X, F, M, postprocess.hinge_point(cn, b, X, nodes[str(200 + b)]))
                _require(math.isclose(r["hinge_aero_torque_nm"][b], m_h, rel_tol=0, abs_tol=1e-12), "Hinge aero torque mismatch.")
            _require(abs(r["rpm"] - nodes["2"]["w"][2] * 60 / (2 * math.pi)) < 1e-9, "RPM does not match hub state.")
        # 5. coverage recomputed from the per-element table and the admitted envelope
        env = req["c81"]["envelope"]
        cols = row["radial_columns"]
        ia, ire, im, iw = cols.index("alpha_deg"), cols.index("reynolds"), cols.index("mach"), cols.index("window")
        first_bad = None
        for rec in row["radial"]:
            ok = (env["alpha_deg"][0] <= rec[ia] <= env["alpha_deg"][1] and env["reynolds"][0] <= rec[ire] <= env["reynolds"][1]
                  and env["mach"][0] <= rec[im] <= env["mach"][1])
            if not ok:
                first_bad = rec[iw] if first_bad is None else min(first_bad, rec[iw])
        _require(first_bad == ex["first_uncovered_window"], "Coverage verdict does not match element states.")
        # 6. status consistency
        conv_ok = all(r["coupling_converged"] for r in series)
        if ex["status"] == "completed":
            _require(conv_ok and first_bad is None and ex["windows_accepted"] == ex["windows_planned"]
                     and ex["participant_outcome"] == "finished", "A completed status contradicts the retained history.")
        _require(ex["status"] in {"completed", "failed_aero_coverage", "failed_unconverged_coupling", "cancelled",
                                  "timeout", "failed_solver", "failed_incomplete"}, "Unknown coupled status.")
        return row
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ValueError("Malformed coupled result.") from exc
