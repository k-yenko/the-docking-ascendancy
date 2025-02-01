import streamlit as st
from pathlib import Path
import sys

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def main():
    st.set_page_config(
        page_title="Protein-Binder Pipeline",
        page_icon="🧬",
        layout="wide"
    )

    # Initialize session state
    if 'protein_sequence' not in st.session_state:
        st.session_state.protein_sequence = None
    if 'binder_designs' not in st.session_state:
        st.session_state.binder_designs = None
    if 'selected_binder' not in st.session_state:
        st.session_state.selected_binder = None
    if 'prediction_results' not in st.session_state:
        st.session_state.prediction_results = {}

    st.title("🧬 Protein-Binder Design Pipeline")
    st.write("""
    Welcome! This pipeline helps you:
    1. Design protein binders using BindCraft
    2. Select promising candidates
    3. Predict complex structures using multiple methods
    4. Analyze and compare results
    """)

if __name__ == "__main__":
    main()
