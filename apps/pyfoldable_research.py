"""Launch with: python -m streamlit run apps/pyfoldable_research.py."""
from pathlib import Path

import streamlit as st

from pyfoldable.application.research_ui import render_research

st.set_page_config(page_title="PyFoldable Araştırma", layout="wide")
render_research(Path(__file__).resolve().parents[1])
