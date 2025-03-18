import streamlit as st
from pathlib import Path
import sys
import tarfile
import io
import tempfile
import numpy as np
from streamlit_molstar import st_molstar
from datetime import datetime
from Bio import PDB
from Bio.PDB import Superimposer
import nglview as nv
from streamlit_app.utils.boltz_utils import latest_yaml_content
from streamlit_app.utils.common_utils import extract_sequences_from_pdb
from streamlit_app.utils.structure_metrics import (
    load_structure, extract_confidence_metrics, create_pae_plot,
    calculate_bsa, count_interface_hbonds
)
import os
from streamlit_app.utils.dev_config import USE_FALLBACK_PAE, FALLBACK_PAE_PATH
from io import BytesIO
import json

# Try importing matplotlib, but don't fail if not available
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    st.warning("Matplotlib is not installed. Some visualizations will not be available.")

# Try importing nglview, but don't fail if not available
try:
    import nglview as nv
    NGLVIEW_AVAILABLE = True
except ImportError:
    NGLVIEW_AVAILABLE = False
    st.warning("nglview is not installed. Some 3D visualizations will not be available.")

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
        
        # Create columns for the standalone PAE visualization
        col1, col2 = st.columns(2)
        
        with col1:
            st.header("Example Metrics")
            st.write("When you run predictions, quality metrics will appear here:")
            st.write("pTM Score: Example")
            st.write("ipTM Score: Example")
            st.write("Buried Surface Area: Example")
            st.write("Interface H-Bonds: Example")
        
        with col2:
            st.header("PAE Visualization")
            st.write("Sample PAE data from Boltz results:")
            
            try:
                from streamlit_app.utils.structure_metrics import create_viridis_pae_plot
                
                # Look for any available PAE files from previous runs
                pae_found = False
                pae_dirs = []
                
                # Look in output directory for any boltz_* directories
                if os.path.exists("output"):
                    for dir_name in os.listdir("output"):
                        if dir_name.startswith("boltz_") and os.path.isdir(os.path.join("output", dir_name)):
                            pae_dirs.append(os.path.join("output", dir_name))
                
                # Check each directory for PAE files
                for pae_dir in pae_dirs:
                    design_name = pae_dir.split("boltz_")[1]
                    pae_path = os.path.join(pae_dir, f"pae_{design_name}_model_0.npz")
                    
                    if os.path.exists(pae_path):
                        # Show cleaner PAE source info with tooltip
                        with st.container():
                            st.markdown(f"<span title='{pae_path}'>Using PAE from previous run ({design_name}) ℹ️</span>", unsafe_allow_html=True)
                        
                        with np.load(pae_path) as data:
                            key_used = None
                            if 'pae' in data:
                                pae_matrix = data['pae']
                                key_used = 'pae'
                            elif 'predicted_aligned_error' in data:
                                pae_matrix = data['predicted_aligned_error']
                                key_used = 'predicted_aligned_error'
                            
                            if key_used:
                                pae_image = create_viridis_pae_plot(pae_matrix)
                                st.image(pae_image, caption=f"PAE from {design_name}")
                                pae_found = True
                                break
                
                # Show error if no PAE files found
                if not pae_found:
                    st.warning("No PAE files found from previous predictions.")
                    st.info("Run a Boltz prediction to generate PAE data for visualization.")
                    
                    # Show debug info about where we looked
                    with st.expander("Debug Info"):
                        if pae_dirs:
                            st.write(f"Checked these directories: {pae_dirs}")
                        else:
                            st.write("No Boltz output directories found in 'output/'")
                
            except Exception as e:
                st.error("Error loading PAE data")
                st.info(f"Details: {str(e)}")
                
        # Add explanation of PAE
        with st.expander("What is PAE (Predicted Aligned Error)?"):
            st.write("""
            Predicted Aligned Error (PAE) is a confidence metric that estimates the expected distance error 
            between each pair of residues in the predicted structure.
            
            - **Lower values (dark purple)** indicate higher confidence in the relative position of the residues.
            - **Higher values (yellow/green)** indicate lower confidence.
            
            PAE is particularly useful for identifying:
            - Flexible regions within the protein
            - Domain boundaries
            - Overall confidence in the predicted structure
            
            A good prediction typically shows distinct blocks of dark purple along the diagonal, 
            representing well-structured domains.
            """)
        
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
                    
                    # Create metrics and PAE visualization section
                    metrics_col1, metrics_col2 = st.columns(2)
                    
                    # Left column: Quality metrics
                    with metrics_col1:
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
                    
                    # Right column: PAE visualization
                    with metrics_col2:
                        st.subheader("PAE")
                        
                        # Add expandable PAE debug information
                        with st.expander("PAE File Debug Info", expanded=False):
                            st.write("Checking for PAE files in these locations:")
                            debug_paths = [
                                f"output/boltz_{design_name}/pae_{design_name}_model_0.npz",
                                f"output/{design_name}/pae_{design_name}_model_0.npz",
                            ]
                            
                            for debug_path in debug_paths:
                                if os.path.exists(debug_path):
                                    st.write(f"✅ Found: {debug_path} ({os.path.getsize(debug_path)} bytes)")
                                    try:
                                        with np.load(debug_path) as data:
                                            st.write(f"   Keys: {list(data.keys())}")
                                    except Exception as e:
                                        st.write(f"   Error loading: {str(e)}")
                                else:
                                    st.write(f"❌ Not found: {debug_path}")
                        
                        # Automatically display PAE visualization
                        try:
                            from streamlit_app.utils.structure_metrics import create_viridis_pae_plot
                            
                            # Look for design-specific PAE file first (from actual prediction run)
                            pae_found = False
                            pae_file_paths = [
                                f"output/boltz_{design_name}/pae_{design_name}_model_0.npz",  # Primary location from Boltz
                                f"output/{design_name}/pae_{design_name}_model_0.npz",        # Alternative location
                            ]
                            
                            for pae_path in pae_file_paths:
                                if os.path.exists(pae_path):
                                    # Show cleaner PAE source info with tooltip
                                    with st.container():
                                        st.markdown(f"<span title='{pae_path}'>Using PAE data from this prediction ℹ️</span>", unsafe_allow_html=True)
                                    
                                    with np.load(pae_path) as data:
                                        if 'pae' in data:
                                            pae_matrix = data['pae']
                                            pae_image = create_viridis_pae_plot(pae_matrix)
                                            st.image(pae_image, caption="Predicted Aligned Error (PAE)")
                                            pae_found = True
                                            break
                                        elif 'predicted_aligned_error' in data:
                                            pae_matrix = data['predicted_aligned_error']
                                            pae_image = create_viridis_pae_plot(pae_matrix)
                                            st.image(pae_image, caption="Predicted Aligned Error (PAE)")
                                            pae_found = True
                                            break
                            
                            if not pae_found:
                                st.error("PAE data not found for this prediction.")
                                st.info("The PAE file should be generated by Boltz and saved to the output directory. Check the debug information above for more details.")
                                
                        except Exception as e:
                            st.error("Error loading or displaying PAE data.")
                            st.info(f"Details: {str(e)}")
                            with st.expander("Technical Details"):
                                st.code(str(e))
                    
                    # Structure visualization first
                    st.subheader("Structure Visualization")
                    
                    # Write to temp file for visualization
                    with tempfile.NamedTemporaryFile(suffix='.cif', mode='w+', delete=False) as tmp:
                        tmp.write(cif_str)
                        tmp_path = tmp.name
                        
                        # Add debug information to the expanded debug section
                        if 'debug_temp_files' not in st.session_state:
                            st.session_state.debug_temp_files = []
                        st.session_state.debug_temp_files.append(tmp_path)
                    
                    # Display structure
                    st_molstar(tmp_path, key=f"molstar_{design_name}_{method}")
                    
                    # Structure information below the visualization
                    st.subheader("Structure Information")
                    
                    # Format prediction time as duration (if possible)
                    try:
                        # Try to extract a duration from the timestamp format
                        # Most timestamps are stored as ISO format strings
                        timestamp = pred_data.get('timestamp', 'N/A')
                        
                        # If we have execution time directly
                        if 'execution_time_seconds' in pred_data:
                            seconds = pred_data['execution_time_seconds']
                            hours = seconds // 3600
                            minutes = (seconds % 3600) // 60
                            secs = seconds % 60
                            duration_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
                            st.write(f"Prediction Time: {duration_str}")
                        else:
                            # For now, just show the timestamp
                            # In a real implementation, you'd calculate the duration from start/end timestamps
                            st.write(f"Prediction Time: {timestamp}")
                    except Exception as e:
                        # Fallback to raw timestamp
                        st.write(f"Prediction Time: {pred_data.get('timestamp', 'N/A')}")
                    
                    # Download button
                    st.download_button(
                        f"Download {method} Structure",
                        cif_content,
                        file_name=f"{design_name}_{method}.cif",
                        mime="chemical/x-cif"
                    )

            # If we have two different methods, show a comparison tab
            if len(methods) > 1:
                st.header("Structure Comparison")
                
                # Get the methods
                method_names = list(methods.keys())
                method1 = method_names[0]
                method2 = method_names[1]
                
                # Get CIF content
                cif1 = methods[method1]['cif_content']
                cif2 = methods[method2]['cif_content']
                
                # Convert bytes to string if needed
                cif1_str = cif1.decode() if isinstance(cif1, bytes) else cif1
                cif2_str = cif2.decode() if isinstance(cif2, bytes) else cif2
                
                # Create combined visualization
                try:
                    combined_cif, rmsd = align_and_combine_structures(cif1_str, cif2_str)
                    
                    # Show RMSD
                    st.write(f"Root Mean Square Deviation (RMSD): {rmsd:.2f} Å")
                    
                    # Display combined structure
                    st.subheader(f"Aligned Structures: {method1} (A chains) vs {method2} (B chains)")
                    
                    # Write to temp file for visualization
                    with tempfile.NamedTemporaryFile(suffix='.cif', mode='w+', delete=False) as tmp:
                        tmp.write(combined_cif)
                        tmp_path = tmp.name
                    
                    st_molstar(tmp_path, key=f"molstar_comparison_{design_name}")
                except Exception as e:
                    st.error(f"Failed to align structures: {str(e)}")
        else:
            st.warning("No predictions found for this design")

    # Replace the dedicated PAE visualization section with a more informative section
    st.header("About PAE Visualization")
    with st.expander("What is PAE (Predicted Aligned Error)?"):
        st.write("""
        Predicted Aligned Error (PAE) is a confidence metric that estimates the expected distance error 
        between each pair of residues in the predicted structure.
        
        - **Lower values (dark purple)** indicate higher confidence in the relative position of the residues.
        - **Higher values (yellow/green)** indicate lower confidence.
        
        PAE is particularly useful for identifying:
        - Flexible regions within the protein
        - Domain boundaries
        - Overall confidence in the predicted structure
        
        A good prediction typically shows distinct blocks of dark purple along the diagonal, 
        representing well-structured domains.
        """)

    # Add a temp file debug expander at the bottom
    with st.expander("Debug: Temporary Files", expanded=False):
        st.write("Temporary directory: ", tempfile.gettempdir())
        if 'debug_temp_files' in st.session_state and st.session_state.debug_temp_files:
            st.write("Temporary files created in this session:")
            for i, temp_file in enumerate(st.session_state.debug_temp_files):
                st.write(f"{i+1}. {temp_file}")
                
                # Add a button to view file content
                if st.button(f"View file {i+1}", key=f"view_temp_{i}"):
                    try:
                        with open(temp_file, 'r') as f:
                            file_content = f.read()
                            st.text_area("File content (first 1000 chars)", file_content[:1000], height=200)
                    except Exception as e:
                        st.error(f"Error reading file: {str(e)}")
                        
                # Add button to delete the file
                if st.button(f"Delete file {i+1}", key=f"delete_temp_{i}"):
                    try:
                        os.unlink(temp_file)
                        st.success(f"Deleted {temp_file}")
                        # Remove from list
                        st.session_state.debug_temp_files.pop(i)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting file: {str(e)}")
        else:
            st.write("No temporary files tracked in this session yet.")
            
        # Add a button to clean up all temporary files
        if 'debug_temp_files' in st.session_state and st.session_state.debug_temp_files:
            if st.button("Clean up all temporary files"):
                for temp_file in st.session_state.debug_temp_files:
                    try:
                        os.unlink(temp_file)
                    except:
                        pass
                st.session_state.debug_temp_files = []
                st.success("All tracked temporary files have been deleted")
                st.rerun()
                
    # Add a new section to display Boltz output directories
    with st.expander("Debug: Boltz Output Directories", expanded=False):
        st.subheader("Boltz Prediction Output Files")
        
        if os.path.exists("output"):
            boltz_dirs = [d for d in os.listdir("output") if d.startswith("boltz_") and os.path.isdir(os.path.join("output", d))]
            
            if boltz_dirs:
                st.write(f"Found {len(boltz_dirs)} Boltz output directories:")
                
                for i, boltz_dir in enumerate(boltz_dirs):
                    with st.container():
                        st.write(f"**{i+1}. {boltz_dir}**")
                        dir_path = os.path.join("output", boltz_dir)
                        
                        # List files in the directory
                        files = os.listdir(dir_path)
                        st.write(f"Files in directory: {', '.join(files)}")
                        
                        # Look for PAE files specifically
                        pae_files = [f for f in files if f.startswith("pae_") and f.endswith(".npz")]
                        if pae_files:
                            st.write("✅ Found PAE files:")
                            for pae_file in pae_files:
                                pae_path = os.path.join(dir_path, pae_file)
                                st.write(f"  - {pae_file} ({os.path.getsize(pae_path)} bytes)")
                                
                                # Add option to view PAE metadata
                                if st.button(f"View PAE metadata for {pae_file}", key=f"pae_meta_{i}_{pae_file}"):
                                    try:
                                        with np.load(os.path.join(dir_path, pae_file)) as data:
                                            st.write(f"Keys in file: {list(data.keys())}")
                                            for key in data.keys():
                                                st.write(f"Shape of '{key}': {data[key].shape}")
                                                if data[key].size < 100:  # Only show small arrays
                                                    st.write(f"Data sample: {data[key]}")
                                    except Exception as e:
                                        st.error(f"Error loading PAE file: {str(e)}")
                        else:
                            st.write("❌ No PAE files found in this directory")
                        
                        # Check confidence.json
                        conf_path = os.path.join(dir_path, "confidence.json")
                        if os.path.exists(conf_path):
                            st.write("✅ Found confidence.json")
                            if st.button(f"View confidence data for {boltz_dir}", key=f"conf_{i}"):
                                try:
                                    with open(conf_path, 'r') as f:
                                        conf_data = json.load(f)
                                        st.json(conf_data)
                                except Exception as e:
                                    st.error(f"Error loading confidence file: {str(e)}")
                        else:
                            st.write("❌ No confidence.json found")
                        
                        st.markdown("---")
            else:
                st.write("No Boltz output directories found")
        else:
            st.write("Output directory does not exist")
            
        # Add debugging for the file system paths
        st.subheader("Filesystem Information")
        st.write(f"Current working directory: {os.getcwd()}")
        st.write(f"Absolute path to output dir: {os.path.abspath('output')}")
                
if __name__ == "__main__":
    results_dashboard()
    
                    