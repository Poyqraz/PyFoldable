import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 CI
    import tomli as tomllib

import pyfoldable


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_distribution_metadata_activates_polyform_with_legal_files():
    metadata = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    project = metadata["project"]

    assert metadata["build-system"]["requires"][0] == "setuptools>=77.0.3"
    assert project["version"] == pyfoldable.__version__ == "0.3.0"
    assert project["authors"] == [{"name": "Poyraz Baydemir"}]
    assert project["license"] == "PolyForm-Noncommercial-1.0.0"
    assert set(project["license-files"]) == {
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "CLA.md",
    }


def test_license_notice_contribution_gate_and_history_are_explicit():
    license_text = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    contributing = (PROJECT_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    cla = (PROJECT_ROOT / "CLA.md").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    scope = (PROJECT_ROOT / "docs" / "licensing.md").read_text(encoding="utf-8")

    assert license_text.startswith(
        "Required Notice: Copyright 2026 Poyraz Baydemir\n"
    )
    assert "PolyForm Noncommercial License 1.0.0" in license_text
    assert "Apache License" not in license_text
    assert "I have read and agree to the PyFoldable CLA." in contributing
    assert "license, not a copyright assignment" in cla.lower().replace("\n", " ")
    assert "separate commercial or proprietary terms" in cla.replace("\n", " ")
    assert "PolyForm Noncommercial 1.0.0" in readme
    assert "Apache-2.0" in scope
    assert "does not revoke rights already granted" in scope


def test_third_party_apc_data_is_not_mislabeled_as_experiment_or_relicensed():
    metadata = json.loads(
        (
            PROJECT_ROOT
            / "data"
            / "propellers"
            / "apc_202602"
            / "APC_10x4.7SF.json"
        ).read_text(encoding="utf-8")
    )
    notices = (PROJECT_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    assert metadata["evidence_class"] == "manufacturer_vortex_model_prediction"
    assert metadata["experimental"] is False
    assert metadata["license_scope"] == "third_party_source_terms_apply"
    assert "does not relicense third-party material" in notices
    assert "UIUC Propeller Database benchmark evidence" in notices
