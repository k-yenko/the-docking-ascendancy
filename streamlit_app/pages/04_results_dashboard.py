import streamlit as st
from pathlib import Path
import sys
import tarfile
import io

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def display_boltz_results(result_bytes):
    """Display results from Boltz prediction"""
    # Convert bytes to file-like object
    tar_bytes = io.BytesIO(result_bytes)
    
    # Extract contents
    with tarfile.open(fileobj=tar_bytes, mode='r:gz') as tar:
        # List contents
        st.write("Files in prediction output:")
        for member in tar.getmembers():
            st.write(f"- {member.name}")
        
        # Extract and display relevant files
        for member in tar.getmembers():
            if member.name.endswith('.pdb'):
                # Extract PDB file
                f = tar.extractfile(member)
                if f is not None:
                    content = f.read()
                    st.download_button(
                        f"Download {Path(member.name).name}",
                        content,
                        file_name=Path(member.name).name,
                        mime="chemical/x-pdb"
                    )
                    # Could add PDB viewer here

def results_dashboard():
    st.title("Results Dashboard")
    
    if 'prediction_results' not in st.session_state:
        st.error("No prediction results found. Please run predictions first.")
        st.button("Go back to Structure Prediction", 
                 on_click=lambda: st.switch_page("pages/03_structure_prediction.py"))
        return
    
    # Display results for each method
    for method, result in st.session_state.prediction_results.items():
        st.header(f"{method} Results")
        
        if method == "Boltz-1":
            display_boltz_results(result)
        elif method == "ChAI-1":
            st.write("ChAI-1 results display not implemented yet")
        elif method == "AlphaFold3":
            st.write("AlphaFold3 results display not implemented yet")

if __name__ == "__main__":
    results_dashboard() 