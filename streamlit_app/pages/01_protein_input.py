import streamlit as st
from pathlib import Path
import sys

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from streamlit_app.utils.bindcraft_utils import validate_sequence, run_bindcraft

def protein_input_page():
    st.title("Step 1: Protein Input")
    
    # Input method selection
    input_method = st.radio(
        "Choose input method:",
        ["Enter sequence", "Upload FASTA file"]
    )
    
    if input_method == "Enter sequence":
        sequence = st.text_area("Enter protein sequence:")
        if sequence:
            if validate_sequence(sequence):
                st.session_state.protein_sequence = sequence
            else:
                st.error("Invalid protein sequence")
    else:
        fasta_file = st.file_uploader("Upload FASTA file", type=['fasta', 'fa'])
        if fasta_file:
            # Process FASTA file
            pass

    if st.session_state.protein_sequence:
        if st.button("Run BindCraft"):
            with st.spinner("Running BindCraft..."):
                try:
                    binder_designs = run_bindcraft(st.session_state.protein_sequence)
                    st.session_state.binder_designs = binder_designs
                    st.success("BindCraft completed successfully!")
                except Exception as e:
                    st.error(f"Error running BindCraft: {str(e)}")

if __name__ == "__main__":
    protein_input_page() 