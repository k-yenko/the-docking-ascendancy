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
from streamlit_app.utils.structure_metrics import (
    load_structure, extract_confidence_metrics, create_pae_plot,
    calculate_bsa, count_interface_hbonds
)
import os

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
    
    # Debug Information in expandable section
    with st.expander("Debug Information"):
        st.write("Prediction History Keys:")
        if 'prediction_history' in st.session_state:
            for key, value in st.session_state.prediction_history.items():
                st.write(f"Key: {key}, Method: {value.get('method')}")
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
        
        # Create a tab for each prediction method
        if len(methods) > 0:
            method_tabs = st.tabs(list(methods.keys()))
            
            # Display each method in its own tab
            for i, (method, pred_data) in enumerate(methods.items()):
                with method_tabs[i]:
                    # Get CIF content
                    cif_content = pred_data['cif_content']
                    cif_str = cif_content.decode() if isinstance(cif_content, bytes) else cif_content
                    
                    # Structure info and metrics
                    metrics_col1, metrics_col2 = st.columns(2)
                    with metrics_col1:
                        st.subheader("Structure Information")
                        st.write(f"Method: {method}")
                        st.write(f"Prediction Time: {pred_data.get('timestamp', 'N/A')}")
                        
                        # Download button
                        st.download_button(
                            f"Download {method} Structure",
                            cif_content,
                            file_name=f"{design_name}_{method}.cif",
                            mime="chemical/x-cif"
                        )
                    
                    with metrics_col2:
                        st.subheader("Quality Metrics")
                        
                        # Try to load confidence data from prediction output files
                        confidence_data = extract_confidence_metrics(design_name, method)
                        
                        # Display pTM and ipTM scores if available
                        if confidence_data and 'pTM' in confidence_data:
                            st.write(f"pTM Score: {confidence_data['pTM']:.3f}")
                        elif confidence_data and 'ptm' in confidence_data:
                            st.write(f"pTM Score: {confidence_data['ptm']:.3f}")
                        else:
                            st.write("pTM Score: Not available")
                            
                        if confidence_data and 'ipTM' in confidence_data:
                            st.write(f"ipTM Score: {confidence_data['ipTM']:.3f}")
                        elif confidence_data and 'iptm' in confidence_data:
                            st.write(f"ipTM Score: {confidence_data['iptm']:.3f}")
                        else:
                            st.write("ipTM Score: Not available")
                        
                        # Calculate BSA and H-bonds on the fly
                        try:
                            structure = load_structure(cif_str)
                            bsa = calculate_bsa(structure)
                            hbonds = count_interface_hbonds(structure)
                            
                            st.write(f"Buried Surface Area: {bsa:.1f} Å²")
                            st.write(f"Interface H-Bonds: {hbonds}")
                        except Exception as e:
                            st.write("Metrics calculation failed")
                            st.write(f"Error: {str(e)}")
                    
                    # Structure visualization
                    st.subheader("Structure Visualization")
                    
                    # Write to temp file for visualization
                    with tempfile.NamedTemporaryFile(suffix='.cif', mode='w+', delete=False) as tmp:
                        tmp.write(cif_str)
                        tmp_path = tmp.name
                    
                    # Display structure
                    st_molstar(tmp_path, key=f"molstar_{design_name}_{method}")
                    
                    # PAE Plot
                    st.subheader("Predicted Aligned Error (PAE)")

                    # More flexible PAE file search - look for any pae*.npz files
                    output_dir = Path("output")
                    pae_files = []

                    # Search in multiple possible locations with a simple pattern
                    search_dirs = [
                        output_dir / f"boltz_{design_name}",  # The main output directory
                        output_dir / "predictions" / "input",  # Where boltz1.py puts it
                        output_dir                            # Root output directory
                    ]

                    # Look for any file starting with "pae" and ending with ".npz"
                    for search_dir in search_dirs:
                        if search_dir.exists():
                            pae_files.extend(list(search_dir.glob("pae*.npz")))

                    # To track if we've found usable PAE data
                    found_usable_pae = False
                    pae_matrix = None

                    # Debug information in expandable section
                    with st.expander("PAE Data Debugging Information"):
                        st.write("### PAE Data Lookup Process")
                        
                        if pae_files:
                            st.write(f"Found {len(pae_files)} potential PAE files:")
                            for i, path in enumerate(pae_files):
                                st.success(f"✅ PAE file #{i+1} found: {path}")
                                try:
                                    with np.load(path) as pae_data:
                                        st.write(f"PAE file contains keys: {list(pae_data.keys())}")
                                        if 'predicted_aligned_error' in pae_data:
                                            pae_matrix_temp = pae_data['predicted_aligned_error']
                                            st.write(f"PAE matrix shape: {pae_matrix_temp.shape}")
                                            
                                            # Store the first valid PAE matrix we find
                                            if not found_usable_pae:
                                                pae_matrix = pae_matrix_temp
                                                found_usable_pae = True
                                                st.write("✅ Using this PAE matrix for visualization")
                                        else:
                                            st.warning(f"PAE file doesn't contain 'predicted_aligned_error' key")
                                except Exception as e:
                                    st.error(f"Error reading PAE file: {str(e)}")
                        else:
                            st.warning("No PAE files found in any location")
                        
                        # Show confidence data
                        st.write("\n### Confidence Data Contents")
                        if confidence_data:
                            st.write("Keys in confidence data:", list(confidence_data.keys()))
                            keys_to_check = ['pae', 'predicted_aligned_error']
                            found_key = None
                            for key in keys_to_check:
                                if key in confidence_data:
                                    found_key = key
                                    pae_array = np.array(confidence_data[key])
                                    st.write(f"PAE data found in key '{key}'")
                                    st.write(f"Shape: {pae_array.shape}")
                                    break
                            
                            if not found_key:
                                st.warning("No PAE data found in confidence data")
                        else:
                            st.error("No confidence data loaded")

                    # Use the PAE data we found (if any)
                    if found_usable_pae and pae_matrix is not None:
                        st.success(f"Using PAE data from file: shape {pae_matrix.shape}")
                        pae_plot = create_pae_plot(pae_matrix)
                        if pae_plot is not None:
                            st.image(pae_plot, use_container_width=True)
                        else:
                            st.error("Failed to generate PAE plot from data")
                    # If no PAE file was found, check confidence data
                    elif confidence_data:
                        # Try different possible keys for PAE data
                        keys_to_check = ['pae', 'predicted_aligned_error']
                        for key in keys_to_check:
                            if key in confidence_data:
                                pae_data = np.array(confidence_data[key])
                                st.success(f"Using PAE data from confidence file (key: {key})")
                                
                                pae_plot = create_pae_plot(pae_data)
                                if pae_plot is not None:
                                    st.image(pae_plot, use_container_width=True)
                                    break
                                else:
                                    st.error("Failed to generate PAE plot")
                        else:  # This else belongs to the for loop (executes if no break occurred)
                            st.warning("No PAE data found in confidence data")
                    else:
                        st.warning("No PAE data available.")
                        st.info(f"""To generate PAE data for this design:
                        
1. When running through the web app:
   - The PAE matrix is now automatically requested with `--write_full_pae`
   - Re-run the prediction for {design_name} to generate fresh PAE data

2. If running Boltz locally:
   ```bash
   boltz predict {design_name}.yaml --write_full_pae --out_dir output/boltz_{design_name}
   ```
   """)

        else:
            st.warning("No predictions available for this design")
        
        # Comparison section (only if multiple methods)
        if len(methods) > 1:
            st.subheader("Structure Comparison")
            st.info("Select two methods to compare their structures and calculate RMSD")
            
            # Structure selection for comparison
            comparison_col1, comparison_col2 = st.columns(2)
            with comparison_col1:
                method1 = st.selectbox("First Structure", list(methods.keys()), key=f"comp1_{design_name}")
            with comparison_col2:
                method2 = st.selectbox("Second Structure", list(methods.keys()), key=f"comp2_{design_name}")
            
            if method1 != method2:
                # Get structures
                cif1 = methods[method1]['cif_content']
                cif1_str = cif1.decode() if isinstance(cif1, bytes) else cif1
                
                cif2 = methods[method2]['cif_content']
                cif2_str = cif2.decode() if isinstance(cif2, bytes) else cif2
                
                # Align and combine structures for comparison
                try:
                    combined_cif, rmsd = align_and_combine_structures(cif1_str, cif2_str)
                    st.success(f"RMSD between {method1} and {method2}: {rmsd:.2f} Å")
                    
                    # Write to temp file for visualization
                    with tempfile.NamedTemporaryFile(suffix='.cif', mode='w+', delete=False) as tmp:
                        tmp.write(combined_cif)
                        tmp_path = tmp.name
                    
                    # Display combined structure with color coding
                    st.write(f"""
                    **Structure Colors:**
                    - {method1}: Target in green ribbon, binder in green stick
                    - {method2}: Target in blue ribbon, binder in blue stick
                    
                    Use the visibility controls in Mol* to show/hide individual chains.
                    """)
                    st_molstar(tmp_path, key=f"molstar_comp_{design_name}_{method1}_{method2}")
                    
                except Exception as e:
                    st.error(f"Error comparing structures: {str(e)}")
            else:
                st.warning("Please select different methods to compare")

if __name__ == "__main__":
    results_dashboard() 