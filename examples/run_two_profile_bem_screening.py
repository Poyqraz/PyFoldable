"""Execute the declared two-profile screening without widening its envelope.

The pinned XFOIL build is selected by ``TWO_PROFILE_XFOIL`` and
``TWO_PROFILE_XFOIL_SOURCE_SHA256``. A missing executable, a source-archive
mismatch, or a backend version other than the declaration is written as a
blockage. This script does not substitute another polar source.
"""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from pyfoldable import __version__
from pyfoldable.application.two_profile_bem_screening import (
    block_declared_screening,
    build_shared_declaration,
    canonical_json,
    execute_declared_screening,
    write_study_outputs,
)
from pyfoldable.core.providers import PolarProviderUnavailableError
from pyfoldable.providers.xfoil import XfoilProvider


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_revision(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip()
    return revision if completed.returncode == 0 and revision else "unavailable"


def _runtime(root: Path, **fields: object) -> dict[str, object]:
    runtime = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pyfoldable_version": __version__,
        "numpy": version("numpy"),
        "scipy": version("scipy"),
        "git_revision": _git_revision(root),
        "physical_qualification": False,
    }
    runtime.update(fields)
    return runtime


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    declaration = build_shared_declaration(root)
    output = root / "reports" / "two_profile_bem_screening"
    output.mkdir(parents=True, exist_ok=True)
    declaration_path = output / "declaration.json"
    declaration_path.write_text(canonical_json(declaration) + "\n", encoding="utf-8")
    reloaded = declaration_path.read_text(encoding="utf-8")
    if reloaded != canonical_json(declaration) + "\n":
        raise RuntimeError("Declaration file does not match the computed declaration.")

    executable = os.environ.get("TWO_PROFILE_XFOIL", "").strip()
    source_sha = os.environ.get("TWO_PROFILE_XFOIL_SOURCE_SHA256", "").strip()
    if not executable:
        result = block_declared_screening(
            declaration,
            repository_root=root,
            status="provider_unavailable",
            failure="TWO_PROFILE_XFOIL is unset. No polar provider was executed.",
        )
        write_study_outputs(
            output,
            declaration=declaration,
            records=result["records"],
            published=result["published"],
            runtime=_runtime(root, provider_status="unavailable"),
        )
        return 2
    if source_sha != declaration["provider"]["source_sha256"]:
        result = block_declared_screening(
            declaration,
            repository_root=root,
            status="provider_identity_mismatch",
            failure=(
                "TWO_PROFILE_XFOIL_SOURCE_SHA256 does not match the declared "
                "XFOIL source archive."
            ),
        )
        write_study_outputs(
            output,
            declaration=declaration,
            records=result["records"],
            published=result["published"],
            runtime=_runtime(root, source_sha256=source_sha or "missing"),
        )
        return 2
    try:
        provider = XfoilProvider(executable)
    except PolarProviderUnavailableError as exc:
        result = block_declared_screening(
            declaration,
            repository_root=root,
            status="provider_unavailable",
            failure=str(exc),
        )
        write_study_outputs(
            output,
            declaration=declaration,
            records=result["records"],
            published=result["published"],
            runtime=_runtime(root, executable=executable, provider_status="unavailable"),
        )
        return 2

    identity = provider.identity
    runtime = _runtime(
        root,
        provider_name=identity.name,
        provider_adapter_version=identity.adapter_version,
        provider_backend_name=identity.backend_name,
        provider_backend_version=identity.backend_version,
        executable=provider.executable,
        executable_sha256=_file_sha256(Path(provider.executable)),
        source_sha256=source_sha,
        gfortran=os.environ.get("TWO_PROFILE_GFORTRAN", "unrecorded"),
        osmap=os.environ.get("OSMAP", "unset"),
    )
    result = execute_declared_screening(
        declaration, provider=provider, repository_root=root
    )
    write_study_outputs(
        output,
        declaration=declaration,
        records=result["records"],
        published=result["published"],
        runtime=runtime,
    )
    return 0 if not result["published"]["failure_ledger"] else 2


if __name__ == "__main__":
    sys.exit(main())
