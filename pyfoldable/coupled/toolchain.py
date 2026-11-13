"""Operator toolchain manifest and readiness (no solver is executed here).

The manifest is a JSON file named by ``PYFOLDABLE_COUPLED_TOOLCHAIN`` or found
at ``~/.pyfoldable/coupled_toolchain.json``. It is written by
``tools/coupled/build_toolchain.sh``. Normal users never edit it; without it
the coupled route reports "not installed" and every other workflow continues.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

ENV = "PYFOLDABLE_COUPLED_TOOLCHAIN"
DEFAULT = Path.home() / ".pyfoldable" / "coupled_toolchain.json"
REQUIRED_EXECUTABLES = ("dust", "dust_pre", "dust_post", "mbdyn", "coupling_python")
EXPECTED = {"dust_revision": "3b1d2e61f0b74a3c9fdde9c850951c73f8c6ad3e",
            "mbdyn_revision": "55c86cc6ec7ff8d69d31271c8f23220a43d996b6",
            "precice_version": "2.5.0", "pyprecice_version": "2.5.0.4"}


@dataclass(frozen=True)
class Toolchain:
    path: Path
    manifest: dict

    def exe(self, name: str) -> str:
        return self.manifest["executables"][name]

    @property
    def mbpy(self) -> str:
        return self.manifest["mbdyn_python_module_dir"]

    @property
    def library_path(self) -> str:
        return os.pathsep.join(self.manifest.get("ld_library_path", []))

    def environment(self) -> dict:
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "USER")}
        env["LD_LIBRARY_PATH"] = self.library_path
        env["OMP_NUM_THREADS"] = str(self.manifest.get("omp_num_threads", 4))
        env["PYFOLDABLE_MBDYN_MBPY"] = self.mbpy
        return env


@dataclass(frozen=True)
class Readiness:
    status: str  # ready | not_installed | invalid
    message: str
    toolchain: Toolchain | None = None
    identity: dict | None = None


def _sha_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def locate() -> Path | None:
    explicit = os.environ.get(ENV)
    if explicit:
        return Path(explicit)
    return DEFAULT if DEFAULT.is_file() else None


def readiness(*, hash_executables: bool = True) -> Readiness:
    path = locate()
    if path is None:
        return Readiness("not_installed", "DUST–MBDyn–preCICE araç zinciri kurulu değil. BEM ve diğer analizler etkilenmez.")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Readiness("invalid", f"Araç zinciri bildirimi okunamadı: {exc}")
    if manifest.get("schema_version") != 1 or manifest.get("artifact_class") != "pyfoldable_coupled_toolchain":
        return Readiness("invalid", "Araç zinciri bildirimi tanınmayan biçimde.")
    missing = [n for n in REQUIRED_EXECUTABLES if not os.access(manifest.get("executables", {}).get(n, ""), os.X_OK)]
    if missing:
        return Readiness("invalid", "Eksik çalıştırılabilir dosya: " + ", ".join(missing))
    if not (Path(manifest.get("mbdyn_python_module_dir", "")) / "mbc_py.py").is_file():
        return Readiness("invalid", "MBDyn Python modülü (mbc_py) bulunamadı.")
    for key, value in EXPECTED.items():
        if manifest.get("versions", {}).get(key) != value:
            return Readiness("invalid", f"Doğrulanmış sürümle uyuşmayan bileşen: {key}")
    identity = {"manifest_sha256": _sha_file(str(path)), "versions": manifest["versions"],
                "sources": manifest.get("sources", {}), "build": manifest.get("build", {})}
    if hash_executables:
        identity["executables_sha256"] = {n: _sha_file(manifest["executables"][n]) for n in REQUIRED_EXECUTABLES}
        recorded = manifest.get("executables_sha256", {})
        changed = [n for n in REQUIRED_EXECUTABLES if recorded.get(n) and recorded[n] != identity["executables_sha256"][n]]
        if changed:
            return Readiness("invalid", "Kurulumdan sonra değişmiş çalıştırılabilir dosya: " + ", ".join(changed))
    return Readiness("ready", "Araç zinciri hazır.", Toolchain(path, manifest), identity)
