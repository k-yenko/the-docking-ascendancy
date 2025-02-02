import streamlit as st
from pathlib import Path
import sys
import tarfile
import io
from streamlit_molstar import st_molstar

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def calculate_metrics(struct1, struct2):
    """Calculate structural comparison metrics"""
    # Calculate RMSD
    super_imposer = PDB.Superimposer()
    atoms1 = [atom for atom in struct1.get_atoms() if atom.get_name() == 'CA']
    atoms2 = [atom for atom in struct2.get_atoms() if atom.get_name() == 'CA']
    super_imposer.set_atoms(atoms1, atoms2)
    return {
        'rmsd': super_imposer.rms,
        'num_atoms': len(atoms1)
    }

def display_structure(pdb_content, key):
    """Display structure using Mol*"""
    st_molstar(pdb_content, key=key)

def display_structure_py3dmol(structure_content, structure_format='cif'):
    """Display structure using py3Dmol"""
    view = py3Dmol.view(width=800, height=600)
    view.addModel(structure_content, format=structure_format)
    view.setStyle({'cartoon': {'color': 'spectrum'}})
    view.zoomTo()
    
    # Convert to HTML for Streamlit
    showmol(view, height=600, width=800)

def display_boltz_results(result_bytes):
    """Display results from Boltz prediction"""
    try:
        # Convert bytes to file-like object
        tar_buffer = io.BytesIO(result_bytes)
        
        with tarfile.open(fileobj=tar_buffer, mode='r:gz') as tar:
            # Look for the CIF file
            cif_path = "boltz_results/predictions/input/input_model_0.cif"
            try:
                cif_info = tar.getmember(cif_path)
                cif_file = tar.extractfile(cif_info)
                if cif_file is not None:
                    cif_content = cif_file.read()
                    st.write("### Predicted Structure")
                    st_molstar(cif_content, key="structure_viewer")
                    
                    # Download button
                    st.download_button(
                        "Download Structure (CIF)",
                        cif_content,
                        file_name="prediction.cif",
                        mime="chemical/x-cif"
                    )
            except KeyError:
                st.error("Could not find predicted structure file")
            except Exception as e:
                st.error(f"Error displaying structure: {str(e)}")
    
    except Exception as e:
        st.error("Error processing prediction results")

def compare_structures(results):
    """Compare multiple prediction results"""
    st.subheader("Structure Comparison")
    
    # Create selection for structures to compare
    methods = list(results.keys())
    if len(methods) > 1:
        col1, col2 = st.columns(2)
        with col1:
            struct1 = st.selectbox("Select first structure", methods)
        with col2:
            struct2 = st.selectbox("Select second structure", methods)
        
        if struct1 != struct2:
            # Extract PDB content
            pdb1 = extract_pdb_from_results(results[struct1])
            pdb2 = extract_pdb_from_results(results[struct2])
            
            # Calculate and display metrics
            metrics = calculate_metrics(pdb1, pdb2)
            st.write(f"RMSD between {struct1} and {struct2}: {metrics['rmsd']:.2f} Å")
            
            # Display aligned structures
            st.write("Aligned Structures:")
            display_aligned_structures(pdb1, pdb2)

def results_dashboard():
    st.title("Structure Prediction Results")
    
    # Debug - check what's in session state
    if st.checkbox("Debug"):
        st.write("Session state:", {k: type(v) for k, v in st.session_state.items()})
        if 'prediction_results' in st.session_state:
            st.write("Prediction results:", {k: type(v) for k, v in st.session_state.prediction_results.items()})
    
    if 'prediction_results' not in st.session_state:
        st.error("No prediction results found. Please run predictions first.")
        st.button("Go back to Structure Prediction", 
                 on_click=lambda: st.switch_page("pages/03_structure_prediction.py"))
        return
    
    # Display results for each method
    for method, result in st.session_state.prediction_results.items():
        st.header(f"{method} Results")
        if method == "Boltz-1" and result is not None:
            display_boltz_results(result)
        elif method == "ChAI-1":
            st.write("ChAI-1 results display not implemented yet")
        elif method == "AlphaFold3":
            st.write("AlphaFold3 results display not implemented yet")

if __name__ == "__main__":
    results_dashboard() 