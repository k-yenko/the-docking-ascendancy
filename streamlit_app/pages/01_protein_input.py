import streamlit as st
from pathlib import Path
import sys
import requests
from modal import Stub
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from modal_bindcraft import app, bindcraft

def fetch_pdb(pdb_id: str) -> str:
    """
    Fetch PDB file from RCSB using the PDB ID
    
    Args:
        pdb_id: 4-character PDB identifier (e.g. 4Z18)
        
    Returns:
        PDB file content as string
    """
    # Standardize PDB ID format
    pdb_id = pdb_id.upper().strip()
    
    # RCSB PDB download URL
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    
    # Fetch PDB file
    response = requests.get(url)
    
    if response.status_code != 200:
        raise ValueError(f"Failed to fetch PDB {pdb_id}. Check if the ID is correct.")
    
    # Return PDB file content
    return response.text

def save_bindcraft_results(results, pdb_id):
    """Save BindCraft results to local directory
    
    Args:
        results: List of (path, content) tuples from BindCraft
        pdb_id: PDB ID for this run
        
    Returns:
        Path to output directory
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_dir = project_root / "bindcraft_output" / f"{pdb_id}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Saving BindCraft results to {output_dir}")
    
    # Save all files
    for rel_path, content in results:
        file_path = output_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(content)
    
    logger.info(f"Saved {len(results)} files to {output_dir}")
    return output_dir

def load_existing_bindcraft_results(run_id="2502221700"):
    """Load existing BindCraft results into session state
    
    Args:
        run_id: The run ID folder to load from
    
    Returns:
        List of (path, content) tuples mimicking Modal output
    """
    logger.info(f"Loading existing BindCraft results from run {run_id}")
    
    # Path to the existing results
    output_dir = project_root / "out" / "bindcraft" / run_id
    if not output_dir.exists():
        raise ValueError(f"Output directory {output_dir} not found")
    
    # Collect all files in the output directory
    results = []
    for file_path in output_dir.glob("**/*.*"):
        if file_path.is_file():
            # Create relative path from the output directory
            rel_path = file_path.relative_to(output_dir)
            # Read file content
            content = file_path.read_bytes()
            # Add to results
            results.append((rel_path, content))
    
    logger.info(f"Loaded {len(results)} files from {output_dir}")
    return results

def protein_input_page():
    # Handle navigation FIRST, before any UI elements
    if 'navigate_to' in st.session_state:
        navigate_to = st.session_state.navigate_to
        del st.session_state.navigate_to
        st.switch_page(navigate_to)
    
    st.title("Step 1: Protein Input")
    
    # Add a "Dev Mode" checkbox at the top
    dev_mode = st.checkbox("Development Mode", help="Load existing results for testing")
    
    if dev_mode:
        st.warning("Development Mode Active")
        st.write("This will load existing BindCraft results instead of running a new job")
        run_id = st.text_input("Run ID to load:", value="2502221700")
        
        # First button only loads results
        if st.button("Load Existing Results"):
            try:
                # Load existing results
                results = load_existing_bindcraft_results(run_id)
                
                # Store results in session state
                st.session_state.bindcraft_results = results
                
                # Set a flag to show we have results
                st.session_state.results_loaded = True
                
                # Show success message
                st.success(f"Loaded {len(results)} files from run {run_id}")
                
            except Exception as e:
                logger.error(f"Error loading existing results: {str(e)}", exc_info=True)
                st.error(f"Error: {str(e)}")
        
        # Show navigation button separately, only if results are loaded
        if st.session_state.get('results_loaded', False):
            if st.button("Go to Binder Gallery"):
                st.session_state.navigate_to = "pages/02_binder_gallery.py"
                st.rerun()
        
        # Add a horizontal line to separate dev mode from regular mode
        st.markdown("---")
    
    # Initialize session state
    if 'pdb_content' not in st.session_state:
        st.session_state.pdb_content = None
    if 'pdb_id' not in st.session_state:
        st.session_state.pdb_id = None
    
    # Input method selection
    input_method = st.radio(
        "Choose input method:",
        ["Enter sequence", "Upload FASTA file", "Fetch from PDB"]
    )
    
    if input_method == "Enter sequence":
        sequence = st.text_area("Enter protein sequence:")
        if sequence:
            if validate_sequence(sequence):
                st.session_state.protein_sequence = sequence
            else:
                st.error("Invalid protein sequence")
                
    elif input_method == "Upload FASTA file":
        fasta_file = st.file_uploader("Upload FASTA file", type=['fasta', 'fa'])
        if fasta_file:
            # Process FASTA file
            pass
            
    else:  # Fetch from PDB
        pdb_id = st.text_input("Enter PDB ID (e.g. 4Z18):")
        if pdb_id:
            try:
                with st.spinner(f"Fetching PDB {pdb_id}..."):
                    logger.info(f"Fetching PDB {pdb_id}...")
                    pdb_content = fetch_pdb(pdb_id)
                    
                    # Store PDB content and ID
                    st.session_state.pdb_content = pdb_content
                    st.session_state.pdb_id = pdb_id
                    
                    # Show success and preview
                    st.success(f"Successfully fetched PDB {pdb_id}")
                    st.text_area("PDB File Preview:", pdb_content[:500] + "...", height=200, disabled=True)
                    
                    # Add verification download button
                    st.download_button(
                        "Download PDB file for verification",
                        pdb_content,
                        file_name=f"{pdb_id}.pdb",
                        mime="chemical/x-pdb"
                    )
                    
                    # Add BindCraft button
                    if st.button("Run BindCraft Design"):
                        with st.spinner("Running BindCraft..."):
                            try:
                                logger.info("Setting up BindCraft run...")
                                
                                # Create temporary directory for design
                                design_path = Path(f"/tmp/bindcraft_{pdb_id}")
                                design_path.mkdir(parents=True, exist_ok=True)
                                logger.info(f"Created design directory: {design_path}")
                                
                                # Save PDB file
                                pdb_file = design_path / f"{pdb_id}.pdb"
                                pdb_file.write_text(pdb_content)
                                logger.info(f"Saved PDB file to: {pdb_file}")
                                
                                # Run BindCraft with proper string arguments
                                logger.info("Starting BindCraft remote execution...")
                                try:
                                    # Log all parameters for debugging
                                    logger.info(f"Parameters being sent to BindCraft:")
                                    logger.info(f"- design_path: {str(design_path)} (type: {type(str(design_path))})")
                                    logger.info(f"- binder_name: {f'binder_{pdb_id}'} (type: {type(f'binder_{pdb_id}')})")
                                    logger.info(f"- pdb_str length: {len(pdb_content)} chars")
                                    logger.info(f"- chains: 'A' (type: {type('A')})")
                                    logger.info(f"- target_hotspot_residues: '' (type: {type('')})")
                                    logger.info(f"- lengths: '50,100' (type: {type('50,100')})")
                                    logger.info(f"- number_of_final_designs: 3 (type: {type(3)})")
                                    
                                    with app.run():
                                        results = bindcraft.remote(
                                            design_path=str(design_path),
                                            binder_name=f"binder_{pdb_id}",
                                            pdb_str=pdb_content,
                                            chains="A",
                                            target_hotspot_residues="",
                                            lengths=[50, 100],
                                            number_of_final_designs="3"
                                        )
                                except Exception as e:
                                    logger.error(f"Error calling BindCraft: {str(e)}")
                                    logger.error(f"Error type: {type(e)}")
                                    import traceback
                                    logger.error(f"Traceback: {traceback.format_exc()}")
                                    # Re-raise to show in Streamlit
                                    raise
                                
                                # Store results in session state
                                st.session_state.bindcraft_results = results
                                logger.info("Stored results in session state")
                                
                                # Save results locally
                                output_dir = save_bindcraft_results(results, pdb_id)
                                st.success(f"BindCraft design completed! Results saved to {output_dir}")
                                
                                # Replace callback with direct navigation
                                if st.button("Go to Binder Gallery"):
                                    st.session_state.navigate_to = "pages/02_binder_gallery.py"
                                    st.rerun()
                                
                            except Exception as e:
                                logger.error(f"Error during BindCraft execution: {str(e)}", exc_info=True)
                                st.error(f"Error running BindCraft: {str(e)}")
                    
            except Exception as e:
                logger.error(f"Error fetching PDB: {str(e)}", exc_info=True)
                st.error(f"Error fetching PDB: {str(e)}")

if __name__ == "__main__":
    protein_input_page() 