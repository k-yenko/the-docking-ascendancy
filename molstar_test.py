import streamlit as st
from streamlit_molstar import st_molstar
from pathlib import Path

st.title("Mol* Test")

# Path to your CIF file
cif_path = Path("boltz_outputs/boltz_results_input/predictions/input/input_model_0.cif")

if cif_path.exists():
    st.write(f"Found CIF file: {cif_path}")
    
    # Display structure using Mol*
    st_molstar(str(cif_path), key="test_viewer")
    
    # Show file info
    st.write("File size:", cif_path.stat().st_size, "bytes")
else:
    st.error(f"CIF file not found at: {cif_path}")
    
    # Show what files/directories exist
    st.write("Available files in current directory:")
    for p in Path().glob("**/*.cif"):
        st.write(f"- {p}")
