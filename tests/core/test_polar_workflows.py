"""Static safety contracts for polar qualification workflows."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
DOWNLOAD = "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c"


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_first_party_actions_are_node24_release_commit_pinned() -> None:
    tests = _workflow("tests.yml")
    capture = _workflow("polar-real-qualification.yml")
    comparison = _workflow("polar-real-reproducibility.yml")
    combined = "\n".join((tests, capture, comparison))

    assert combined.count(CHECKOUT) == 3
    assert combined.count(SETUP_PYTHON) == 3
    assert combined.count(UPLOAD) == 2
    assert combined.count(DOWNLOAD) == 2
    assert "actions/checkout@v4" not in combined
    assert "actions/setup-python@v5" not in combined
    assert "actions/upload-artifact@v4" not in combined


def test_reproducibility_workflow_is_read_only_and_fail_closed() -> None:
    workflow = _workflow("polar-real-reproducibility.yml")

    assert "actions: read" in workflow
    assert "contents: read" in workflow
    assert "first_run_id:" in workflow
    assert "second_run_id:" in workflow
    assert 'test "$FIRST_RUN_ID" != "$SECOND_RUN_ID"' in workflow
    assert workflow.count("digest-mismatch: error") == 2
    assert "compare_real_polar_qualification.py" in workflow
    assert "if: always()" in workflow
