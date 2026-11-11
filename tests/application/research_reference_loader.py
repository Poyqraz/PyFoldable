"""Load the operator-only checkout caller without requiring examples as a package."""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[2] / "examples/research_reference_data.py"
_spec = importlib.util.spec_from_file_location("research_reference_operator_test", _path)
ref = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ref)
