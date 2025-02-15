import streamlit as st
from pathlib import Path
import sys
import tarfile
import io
import tempfile
from streamlit_molstar import st_molstar
from datetime import datetime

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
            # List all files in archive
            st.write("Files in result:")
            for member in tar.getmembers():
                st.write(f"- {member.name}")
            
            # Look for CIF file
            cif_files = [m for m in tar.getmembers() if m.name.endswith('.cif')]
            if cif_files:
                cif_file = cif_files[0]
                st.write(f"Found CIF file: {cif_file.name}")
                # Extract CIF content
                cif_content = tar.extractfile(cif_file).read()
                st.write("### Predicted Structure")
                st_molstar(cif_content, key="structure_viewer")
                
                # Download button
                st.download_button(
                    "Download Structure (CIF)",
                    cif_content,
                    file_name="prediction.cif",
                    mime="chemical/x-cif"
                )
            else:
                raise ValueError("No CIF file found in prediction results")
    
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

def create_chimerax_script(cif_content, filename):
    """Create a ChimeraX script to open and display the structure"""
    # Save CIF content to a temporary file
    temp_dir = Path("temp_structures")
    temp_dir.mkdir(exist_ok=True)
    cif_path = temp_dir / f"{filename}.cif"
    cif_path.write_bytes(cif_content)
    
    # Create ChimeraX script
    script = f"""
    open {cif_path.absolute()}
    cartoon
    color bychain
    """
    script_path = temp_dir / f"{filename}.cxc"
    script_path.write_text(script)
    
    return script_path

def results_dashboard():
    st.title("Structure Prediction Results")
    
    if 'prediction_history' not in st.session_state:
        st.info("No predictions available yet. Run some predictions first!")
        return
        
    # Create selection for viewing results
    predictions = st.session_state.prediction_history
    selected_pred = st.selectbox(
        "Select prediction to view:",
        options=list(predictions.keys()),
        format_func=lambda x: f"{predictions[x]['design_name']} ({predictions[x]['timestamp']})"
    )
    
    if selected_pred:
        pred_data = predictions[selected_pred]
        
        # Show metadata
        st.subheader("Prediction Details")
        col1, col2 = st.columns(2)
        with col1:
            st.write("Design:", pred_data['design_name'])
            st.write("Method:", pred_data['method'])
        with col2:
            st.write("Run ID:", pred_data['run_id'])
            st.write("Time:", pred_data['timestamp'])
            
        # Show structure viewer
        st.subheader("Structure Visualization")
        
        # Create a temporary file to store CIF content
        with tempfile.NamedTemporaryFile(suffix='.cif', mode='wb', delete=False) as tmp:
            tmp.write(pred_data['cif_content'])
            tmp_path = tmp.name
        
        # Use st_molstar with the file path
        st_molstar(tmp_path, key=f"molstar_{selected_pred}")
        
        # Add download button
        st.download_button(
            "Download Structure (CIF)",
            pred_data['cif_content'],
            file_name=f"{pred_data['design_name']}_prediction.cif",
            mime="chemical/x-cif"
        )

if __name__ == "__main__":
    results_dashboard() 