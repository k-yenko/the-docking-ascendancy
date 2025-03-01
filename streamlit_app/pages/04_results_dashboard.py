import streamlit as st
from pathlib import Path
import sys
import tarfile
import io
import tempfile
from streamlit_molstar import st_molstar
from datetime import datetime
from Bio import PDB
from Bio.PDB import Superimposer
import nglview as nv
import numpy as np
from streamlit_app.utils.boltz_utils import latest_yaml_content
from streamlit_app.utils.common_utils import extract_sequences_from_pdb

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

def align_and_combine_structures(cif1, cif2=None, is_boltz=True):
    """Align structures and create a combined CIF file"""
    # For single structure case
    if cif2 is None:
        with tempfile.NamedTemporaryFile(suffix='.cif', mode='w+', delete=False) as tmp1:
            tmp1.write(cif1)
            path1 = tmp1.name
        
        parser = PDB.MMCIFParser()
        structure = parser.get_structure('struct', path1)
        
        # Create new structure with single model
        combined = PDB.Structure.Structure('combined')
        model = PDB.Model.Model(0)
        combined.add(model)
        
        # Add chains with appropriate IDs
        chain_count = 0
        if is_boltz:
            for chain in structure[0]:
                new_chain = chain.copy()
                new_chain.id = f'A{chain_count}'  # A0, A1, A2, etc.
                model.add(new_chain)
                chain_count += 1
        else:
            for chain in structure[0]:
                new_chain = chain.copy()
                new_chain.id = f'B{chain_count}'  # B0, B1, B2, etc.
                model.add(new_chain)
                chain_count += 1
        
        # Write to CIF
        io = PDB.MMCIFIO()
        io.set_structure(combined)
        
        with tempfile.NamedTemporaryFile(suffix='.cif', mode='w+', delete=False) as tmp:
            io.save(tmp.name)
            with open(tmp.name) as f:
                combined_cif = f.read()
        
        return combined_cif, 0.0

    # For two structures case
    with tempfile.NamedTemporaryFile(suffix='.cif', mode='w+', delete=False) as tmp1:
        tmp1.write(cif1)
        path1 = tmp1.name
    with tempfile.NamedTemporaryFile(suffix='.cif', mode='w+', delete=False) as tmp2:
        tmp2.write(cif2)
        path2 = tmp2.name
    
    parser = PDB.MMCIFParser()
    structure1 = parser.get_structure('struct1', path1)
    structure2 = parser.get_structure('struct2', path2)
    
    # Align structures using first chain
    ref_atoms = []
    alt_atoms = []
    for ref_res, alt_res in zip(structure1[0]['A'], structure2[0]['A']):
        if 'CA' in ref_res and 'CA' in alt_res:
            ref_atoms.append(ref_res['CA'])
            alt_atoms.append(alt_res['CA'])
    
    super_imposer = Superimposer()
    super_imposer.set_atoms(ref_atoms, alt_atoms)
    rmsd = super_imposer.rms
    super_imposer.apply(structure2[0].get_atoms())
    
    # Create combined structure with single model
    combined = PDB.Structure.Structure('combined')
    model = PDB.Model.Model(0)
    combined.add(model)
    
    # Add Boltz structure chains with unique IDs
    chain_count = 0
    for chain in structure1[0]:
        new_chain = chain.copy()
        new_chain.id = f'A{chain_count}'  # A0, A1, A2, etc.
        model.add(new_chain)
        chain_count += 1
    
    # Add Chai structure chains with unique IDs
    chain_count = 0
    for chain in structure2[0]:
        new_chain = chain.copy()
        new_chain.id = f'B{chain_count}'  # B0, B1, B2, etc.
        model.add(new_chain)
        chain_count += 1
    
    # Write combined structure
    io = PDB.MMCIFIO()
    io.set_structure(combined)
    
    with tempfile.NamedTemporaryFile(suffix='.cif', mode='w+', delete=False) as tmp:
        io.save(tmp.name)
        with open(tmp.name) as f:
            combined_cif = f.read()
    
    return combined_cif, rmsd

def results_dashboard():
    st.title("Structure Predictions")
    
    if 'prediction_history' not in st.session_state or not st.session_state.prediction_history:
        st.info("No predictions available yet. Run some predictions first!")
        st.button("Go back to Structure Prediction", 
                 on_click=lambda: st.switch_page("pages/03_structure_prediction.py"))
        return
    
    if 'selected_methods' in st.session_state:
        selected_methods = st.session_state.selected_methods
    else:
        selected_methods = []  # Default if none were selected
    
    # Group predictions by design name
    predictions = st.session_state.prediction_history
    design_predictions = {}
    for pred_id, pred_data in predictions.items():
        design_name = pred_data['design_name']
        if design_name not in design_predictions:
            design_predictions[design_name] = {}
        design_predictions[design_name][pred_data['method']] = pred_data
    
    # Show predictions for each design
    for design_name, methods in design_predictions.items():
        st.header(f"Design: {design_name}")
        
        # Structure visibility controls
        st.subheader("Structure Controls")
        col1, col2 = st.columns(2)
        with col1:
            show_boltz = st.checkbox("Show Boltz-1", 
                                    value="Boltz-1" in selected_methods)
        with col2:
            show_chai = st.checkbox("Show Chai-1", 
                                   value="Chai-1" in selected_methods)
        
        # Get structures based on visibility
        structures = {}
        if show_boltz:
            if 'prediction_history' in st.session_state:
                # Find the boltz prediction (if any)
                boltz_predictions = [v for k, v in st.session_state.prediction_history.items() 
                                     if k.startswith('boltz_') and v['method'] == 'Boltz-1']
                if boltz_predictions:
                    boltz_result = boltz_predictions[0]
                    structures["Boltz-1"] = boltz_result['cif_content'].decode() if isinstance(boltz_result['cif_content'], bytes) else boltz_result['cif_content']
        if show_chai:
            if 'prediction_history' in st.session_state:
                # Find the chai prediction (if any)
                chai_predictions = [v for k, v in st.session_state.prediction_history.items() 
                                   if k.startswith('chai_') and v['method'] == 'Chai-1']
                if chai_predictions:
                    chai_result = chai_predictions[0]
                    structures["Chai-1"] = chai_result['cif_content'].decode() if isinstance(chai_result['cif_content'], bytes) else chai_result['cif_content']
        
        if len(structures) == 2:
            # Align and combine both structures
            combined_cif, rmsd = align_and_combine_structures(
                structures["Boltz-1"],
                structures["Chai-1"]
            )
            st.info(f"RMSD between structures: {rmsd:.2f} Å")
        elif len(structures) == 1:
            # Show single structure with correct chain ID
            method = next(iter(structures.keys()))
            structure = structures[method]
            is_boltz = method == "Boltz-1"
            combined_cif, _ = align_and_combine_structures(structure, is_boltz=is_boltz)
        else:
            st.warning("Please select at least one structure to display")
            continue
        
        # Save combined CIF to temporary file
        with tempfile.NamedTemporaryFile(suffix='.cif', mode='w+', delete=False) as tmp:
            tmp.write(combined_cif)
            tmp_path = tmp.name
        
        # Display combined structure in Mol*
        st.subheader("Structure Visualization")
        st.write("""
    **Structure Colors:**
    - Boltz-1: Target in green ribbon, binder in green ball-stick
    - Chai-1: Target in blue ribbon, binder in blue ball-stick
    
    Use the visibility controls in Mol* to show/hide individual chains.
    """)
        st_molstar(tmp_path, key=f"molstar_{design_name}_{show_boltz}_{show_chai}")
        
        # Add download buttons for individual structures
        st.subheader("Download Structures")
        cols = st.columns(len(methods))
        for i, (method, pred_data) in enumerate(methods.items()):
            with cols[i]:
                st.download_button(
                    f"Download {method} Structure",
                    pred_data['cif_content'],
                    file_name=f"{design_name}_{method}.cif",
                    mime="chemical/x-cif"
                )

    # Add this debug section at the start of the dashboard
    st.subheader("Debug Information")
    with st.expander("Session State Debug"):
        st.write("Prediction History Keys:")
        if 'prediction_history' in st.session_state:
            for key, value in st.session_state.prediction_history.items():
                st.write(f"Key: {key}, Method: {value.get('method')}")
                # Check if the CIF content is valid
                cif_content = value.get('cif_content')
                if cif_content:
                    cif_size = len(cif_content) if isinstance(cif_content, str) else len(cif_content) if isinstance(cif_content, bytes) else 0
                    st.write(f"  CIF Content Size: {cif_size} bytes")
                    if isinstance(cif_content, bytes):
                        st.write(f"  CIF Content Type: bytes")
                    else:
                        st.write(f"  CIF Content Type: {type(cif_content)}")
                else:
                    st.write("  CIF Content: None")
        else:
            st.write("No prediction history in session state")

if __name__ == "__main__":
    results_dashboard() 