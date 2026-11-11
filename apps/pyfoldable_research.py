"""Launch with: python -m streamlit run apps/pyfoldable_research.py."""
from pathlib import Path
import os

import streamlit as st

from pyfoldable.application.research_ui import render_research

# This release ships only captured unqualified reference data. An explicit
# operator override is honored even when missing/corrupt; there is no fallback.
root = Path(__file__).resolve().parents[1]
os.environ.setdefault("PYFOLDABLE_PROVIDER_STORE", str(root / "data/research_reference/axial_800_store"))

st.set_page_config(page_title="PyFoldable Araştırma", layout="wide")
render_research(root)
