import streamlit as st
from pathlib import Path
import sys
import requests
from modal import Stub, Image
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from streamlit_app.utils.bindcraft_utils import validate_sequence, run_bindcraft
from modal_bindcraft import app, bindcraft, image

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

def protein_input_page():
    # Deploy Modal app if not already deployed
    try:
        logger.info("Checking Modal app deployment status...")
        
        # Create a new stub for this session
        stub = Stub("bindcraft", image=image)
        
        # Try to deploy the app
        logger.info("Attempting to deploy Modal app...")
        with st.spinner("Initializing BindCraft..."):
            try:
                # First try to deploy the stub
                logger.info("Deploying stub...")
                stub.deploy()
                
                # Then deploy the app
                logger.info("Deploying app...")
                app.deploy()
                
                logger.info("BindCraft initialization successful!")
                st.success("BindCraft initialized successfully!")
            except Exception as e:
                logger.error(f"Error during Modal deployment: {str(e)}", exc_info=True)
                st.error(f"Error initializing BindCraft: {str(e)}")
                return
            
    except Exception as e:
        logger.error(f"Error checking Modal deployment: {str(e)}", exc_info=True)
        st.error(f"Error with Modal setup: {str(e)}")
        return

    st.title("Step 1: Protein Input")
    
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
                                results = bindcraft.remote(
                                    design_path=str(design_path),
                                    binder_name=f"binder_{pdb_id}",
                                    pdb_str=pdb_content,
                                    chains="A",
                                    target_hotspot_residues="",
                                    lengths="50,100",
                                    number_of_final_designs=3
                                )
                                logger.info("BindCraft execution completed")
                                
                                # Store results in session state
                                st.session_state.bindcraft_results = results
                                logger.info("Stored results in session state")
                                
                                # Success message and navigation
                                st.success("BindCraft design completed!")
                                st.button("View Results Gallery", 
                                        on_click=lambda: st.switch_page("pages/02_binder_gallery.py"))
                                
                            except Exception as e:
                                logger.error(f"Error during BindCraft execution: {str(e)}", exc_info=True)
                                st.error(f"Error running BindCraft: {str(e)}")
                    
            except Exception as e:
                logger.error(f"Error fetching PDB: {str(e)}", exc_info=True)
                st.error(f"Error fetching PDB: {str(e)}")

if __name__ == "__main__":
    protein_input_page() 