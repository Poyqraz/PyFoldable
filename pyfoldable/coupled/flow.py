"""Flow companion of a sealed coupled record: verification, events and wake metrics (NumPy only).

The companion (``<run>/flow/flow_companion.{json,npz}``) is extracted on request from retained
DUST outputs by ``participants/extract_flow.py``; no solver runs. It is accepted only when its
manifest names this record's ``result_sha256`` and every source DUST file it was built from has
exactly the sha256 the sealed record lists in ``raw_outputs`` — the same bytes the record's
loads came from. What it holds was computed by DUST: vortex-particle positions and strengths,
the implicit panel-wake rows, and the velocity that DUST's own kernels induce (plus the free
stream) on a meridional plane. Blade surfaces drawn with it are reconstructed from MBDyn states.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ARTIFACT = "pyfoldable_coupled_flow_companion"
SCHEMA = 1
MAX_NPZ_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_INFLATED_BYTES = 1024 * 1024 * 1024
ARRAYS = ("windows", "time_label_s", "particle_offsets", "particle_position_m", "particle_vorticity",
          "particle_core_radius_m", "panel_wake_m", "plane_x_m", "plane_z_m", "plane_y_m", "plane_velocity_m_s")


class FlowCompanionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def select_windows(row: dict, max_frames: int = 81, *, dense_step: int = 3, dense_span: int = 72) -> list[int]:
    """Accepted windows of the valid prefix for the flow companion: a regular stride (always
    including the last window) plus every ``dense_step``-th window from just before release through
    ``dense_span`` windows after it, where stop contact and rebound happen."""
    last = int(row["execution"]["valid_prefix_windows"])
    if last < 1:
        return []
    step = max(1, math.ceil(last / max(1, max_frames - 1)))
    picked = set(range(last - step * ((last - 1) // step), last + 1, step))
    ev = events(row)
    rel = ev.get("release")
    if rel is not None:
        picked |= set(range(max(1, rel - 2 * dense_step), min(last, rel + dense_span) + 1, dense_step))
    picked |= {w for w in ev.values() if 1 <= w <= last}  # the event windows themselves
    return sorted(picked)


def default_plane(row: dict, n: int = 81) -> dict:
    """Meridional plane y = 0 (lab frame) covering the disk and the near slipstream below it."""
    R = float(row["run_definition"]["case"]["geometry"]["tip_radius_m"])
    return {"n_xyz": [n, 1, n], "min_xyz": [-1.3 * R, 0.0, -2.0 * R], "max_xyz": [1.3 * R, 0.0, 0.5 * R]}


@dataclass(frozen=True)
class FlowCompanion:
    manifest: dict
    windows: np.ndarray
    time_label_s: np.ndarray
    offsets: np.ndarray
    position: np.ndarray
    vorticity: np.ndarray
    core_radius: np.ndarray
    panel_wake: np.ndarray
    plane_x: np.ndarray
    plane_z: np.ndarray
    plane_y: float
    plane_velocity: np.ndarray

    def index(self, window: int) -> int:
        hits = np.nonzero(self.windows == window)[0]
        if not len(hits):
            raise KeyError(window)
        return int(hits[0])

    def particles(self, window: int):
        i = self.index(window)
        a, b = int(self.offsets[i]), int(self.offsets[i + 1])
        return self.position[a:b], self.vorticity[a:b], self.core_radius[a:b]


def companion_dir(run_dir: Path) -> Path:
    return Path(run_dir) / "flow"


def source_file(window: int) -> str:
    """The DUST result file of accepted window ``window`` (result k, 0-based, is window k + 1)."""
    return f"dust/Output/run_res_{int(window):04d}.h5"


def _bad(message: str) -> FlowCompanionError:
    return FlowCompanionError("malformed", message)


def load(run_dir: Path, row: dict) -> FlowCompanion:
    """Fail-closed load. Accepted only when the manifest names this record, every frame's source is
    that window's own DUST file with the sha256 the sealed record lists (plus the geometry file
    dust_post reads), each frame's DUST time label equals the window time minus one step, and the
    arrays match the manifest. Residual trust: the array file's digest is declared in the same
    local folder, so these checks prove consistency with the record's sources, not authorship."""
    try:
        return _load(Path(run_dir), row)
    except FlowCompanionError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, ValueError) as exc:
        raise _bad("Akış verisi bildirimi veya dizileri beklenen yapıda değil.") from exc


def _load(run_dir: Path, row: dict) -> FlowCompanion:
    import zipfile
    d = companion_dir(run_dir)
    mpath, npath = d / "flow_companion.json", d / "flow_companion.npz"
    if not mpath.is_file() or not npath.is_file():
        raise FlowCompanionError("missing", "Akış verisi bu çalıştırma klasöründe henüz hazırlanmadı.")
    if mpath.stat().st_size > MAX_MANIFEST_BYTES or npath.stat().st_size > MAX_NPZ_BYTES:
        raise FlowCompanionError("too_large", "Akış verisi dosyası beklenen boyut sınırını aşıyor.")
    try:
        m = json.loads(mpath.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise _bad("Akış verisi bildirimi okunamadı.") from exc
    if not isinstance(m, dict) or m.get("artifact_class") != ARTIFACT or m.get("schema_version") != SCHEMA:
        raise FlowCompanionError("unsupported", "Akış verisi sürümü desteklenmiyor.")
    if m.get("result_sha256") != row["result_sha256"]:
        raise FlowCompanionError("other_record", "Akış verisi başka bir sonuç kaydına ait.")
    windows, sources = m["windows"], m["sources"]
    if (not isinstance(windows, list) or not windows or not all(isinstance(w, int) for w in windows)
            or windows != sorted(set(windows)) or not isinstance(sources, list) or len(sources) != len(windows)):
        raise _bad("Akış verisi pencere listesi boş veya tutarsız.")
    raw = row["raw_outputs"]["files"]
    for w, src in zip(windows, sources):
        if not isinstance(src, dict) or src.get("window") != w or src.get("file") != source_file(w):
            raise _bad(f"Pencere {w} için kaynak dosya o pencerenin DUST çıktısı değil.")
        rec = raw.get(src["file"])
        if rec is None or rec.get("sha256") != src.get("sha256"):
            raise FlowCompanionError("source_mismatch", f"{src['file']}: kaynak DUST dosyası mühürlü kayıtla eşleşmiyor.")
    for aux in m.get("auxiliary_sources", []):
        rec = raw.get(aux.get("file")) if isinstance(aux, dict) else None
        if rec is None or rec.get("sha256") != aux.get("sha256"):
            raise FlowCompanionError("source_mismatch", f"{aux}: dust_post’un okuduğu dosya mühürlü kayıtla eşleşmiyor.")
    if _sha(npath) != m["npz"]["sha256"]:
        raise FlowCompanionError("checksum", "Akış verisi dizisi bildirimdeki özetle eşleşmiyor.")
    with zipfile.ZipFile(npath) as zf:  # bound the inflated size before materialising arrays
        if sum(i.file_size for i in zf.infolist()) > MAX_INFLATED_BYTES:
            raise FlowCompanionError("too_large", "Akış verisi açıldığında beklenen boyut sınırını aşıyor.")
    with np.load(npath, allow_pickle=False) as z:
        a = {k: z[k] for k in ARRAYS}
    w = a["windows"].astype(int)
    nf, off = len(w), a["particle_offsets"].astype(np.int64)
    valid = row["series"][:row["execution"]["valid_prefix_windows"]]
    by_w = {r["window"]: r for r in valid}
    dt = float(row["run_definition"]["case"]["dt_s"])
    nx, _, nz = (int(v) for v in m["plane"]["n_xyz"])
    finite = ("time_label_s", "particle_position_m", "particle_vorticity", "particle_core_radius_m", "panel_wake_m",
              "plane_x_m", "plane_z_m", "plane_y_m", "plane_velocity_m_s")
    ok = (w.tolist() == windows and all(x in by_w for x in windows) and len(a["time_label_s"]) == nf
          and off.shape == (nf + 1,) and off[0] == 0 and np.all(np.diff(off) >= 0)
          and int(off[-1]) == int(m["particles_total"])
          and a["particle_position_m"].shape == (off[-1], 3) and a["particle_vorticity"].shape == (off[-1], 3)
          and a["particle_core_radius_m"].shape == (off[-1],) and a["panel_wake_m"].ndim == 4
          and a["panel_wake_m"].shape[:2] == (nf, 2) and a["panel_wake_m"].shape[3] == 3
          and a["plane_x_m"].shape == (nx,) and a["plane_z_m"].shape == (nz,)
          and a["plane_velocity_m_s"].shape == (nf, nz, nx, 3)
          and all(np.all(np.isfinite(a[k])) for k in finite))
    if not ok:
        raise _bad("Akış verisi dizileri bildirim veya kayıtla tutarsız.")
    # each frame's DUST time label lags its accepted window time by one step (alignment rule, §8)
    lag = np.array([by_w[x]["time_s"] - dt for x in windows])
    if not np.allclose(a["time_label_s"], lag, rtol=0.0, atol=1e-6 * dt):
        raise _bad("Akış verisi zaman etiketleri pencere zamanlarıyla eşleşmiyor.")
    return FlowCompanion(m, w, a["time_label_s"], off, a["particle_position_m"], a["particle_vorticity"],
                         a["particle_core_radius_m"], a["panel_wake_m"], a["plane_x_m"], a["plane_z_m"],
                         float(a["plane_y_m"]), a["plane_velocity_m_s"])


def events(row: dict, *, settle_windows: int = 3) -> dict:
    """Release (first unlatched window after a latched one), first stop contact after release,
    largest opening after release, second-swing minimum (lowest θ between leaving the first
    contact — no contact for ``settle_windows`` consecutive windows — and the next contact) and the
    last valid window. Uses blade 1's angle and any blade's contact flag."""
    s = row["series"][:row["execution"]["valid_prefix_windows"]]
    out = {}
    if not s:
        return out
    out["last"] = s[-1]["window"]
    if not s[0]["latch_active"]:
        return out  # never latched: no release event
    rel_i = next((i for i, r in enumerate(s) if not r["latch_active"]), None)
    if rel_i is None:
        return out
    after = s[rel_i:]
    out["release"] = after[0]["window"]
    out["largest_opening"] = max(after, key=lambda r: r["theta_deg"][0])["window"]
    first_i = next((i for i, r in enumerate(after) if any(r["contact_active"])), None)
    if first_i is None:
        return out
    out["first_contact"] = after[first_i]["window"]
    out["largest_opening"] = max(after[first_i:first_i + max(1, settle_windows * 4)], key=lambda r: r["theta_deg"][0])["window"]
    run, leave_i = 0, None
    for i in range(first_i + 1, len(after)):
        run = 0 if any(after[i]["contact_active"]) else run + 1
        if run >= settle_windows:
            leave_i = i - settle_windows + 1
            break
    if leave_i is not None:
        nxt = next((i for i in range(leave_i, len(after)) if any(after[i]["contact_active"])), len(after))
        span = after[leave_i:nxt]
        if span:
            out["second_swing_min"] = min(span, key=lambda r: r["theta_deg"][0])["window"]
    return out


def nearest_frame(fc: FlowCompanion, window: int) -> int:
    return int(fc.windows[int(np.argmin(np.abs(fc.windows - window)))])


def radial_wake_strength(fc: FlowCompanion, window: int, tip_radius_m: float, depth_m: float | None = None,
                         bins: int = 24):
    """Near-wake particle strength |alpha| summed in radial bins (particles within ``depth_m`` below
    the disk): where the blade sheds vorticity, e.g. the tip and root vortices or a hinge vortex."""
    p, v, _ = fc.particles(window)
    depth = 0.5 * tip_radius_m if depth_m is None else depth_m
    keep = p[:, 2] > -depth
    r = np.hypot(p[keep, 0], p[keep, 1])
    mag = np.linalg.norm(v[keep], axis=1)
    edges = np.linspace(0.0, 1.2 * tip_radius_m, bins + 1)
    total, _ = np.histogram(r, bins=edges, weights=mag)
    return 0.5 * (edges[:-1] + edges[1:]), total
