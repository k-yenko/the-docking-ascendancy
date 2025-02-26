from pathlib import Path
import modal
from datetime import datetime
import hashlib
from uuid import uuid4
from Bio.PDB import PDBParser, is_aa
from Bio.PDB.Polypeptide import protein_letters_3to1

# Initialize Modal
app = modal.App(name="chai1-prediction")

# Set up image with dependencies
image = modal.Image.debian_slim(python_version="3.12").run_commands(
    "uv pip install --system --compile-bytecode chai_lab==0.5.0 hf_transfer==0.1.8"
)

# Set up volumes
chai_model_volume = modal.Volume.from_name("chai1-models", create_if_missing=True)
models_dir = Path("/models/chai1")

# Configure image environment
image = image.env({
    "CHAI_DOWNLOADS_DIR": str(models_dir),
    "HF_HUB_ENABLE_HF_TRANSFER": "1",
})

@app.function(
    timeout=15 * 60,  # 15 minutes
    gpu="H100",
    volumes={models_dir: chai_model_volume},
    image=image,
)
def chai1_inference(fasta_content: str) -> list[(bytes, str)]:
    """Runs Chai-1 prediction on Modal"""
    from pathlib import Path
    import torch
    from chai_lab import chai1
    
    # Generate a unique run ID
    run_id = hashlib.sha256(uuid4().bytes).hexdigest()[:8]
    
    # Set up paths
    fasta_file = Path("/tmp/inputs.fasta")
    fasta_file.write_text(fasta_content.strip())
    output_dir = Path("/tmp/predictions") / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run prediction
    chai1.run_inference(
        fasta_file=fasta_file,
        output_dir=output_dir,
        device=torch.device("cuda")
    )
    
    # Return results directly (no need to save locally)
    results = []
    for i in range(5):  # Chai-1 produces 5 models by default
        scores = (output_dir / f"scores.model_idx_{i}.npz").read_bytes()
        cif = (output_dir / f"pred.model_idx_{i}.cif").read_text()
        results.append((scores, cif))
    
    return results

@app.cls(
    image=image,
    volumes={models_dir: chai_model_volume},
    gpu="H100",
)
class Chai1Predictor:
    def predict_structure(self, run_id, design_name):
        """Predict structure using Chai-1"""
        import streamlit as st
        
        # Check if we should use a selected binder
        if run_id is None and design_name is None:
            if 'selected_binder' not in st.session_state:
                raise ValueError("No binder selected and no run_id/design_name provided")
            
            # Use the selected binder from session state
            selected_binder = st.session_state.selected_binder
            design_name = selected_binder['design_name']
            
            # Get the PDB content directly from the session state
            if 'pdb_content' in selected_binder:
                # Use the PDB content we already have in memory
                pdb_content = selected_binder['pdb_content']
                
                # Create a temporary file to use for the prediction
                import tempfile
                temp_dir = Path(tempfile.mkdtemp())
                temp_pdb = temp_dir / f"{design_name}.pdb"
                
                # Write the PDB content to the temp file
                with open(temp_pdb, 'wb') as f:
                    f.write(pdb_content)
                    
                pdb_path = str(temp_pdb)
                st.info(f"Using in-memory PDB content for {design_name}")
                
                # Extract sequence from PDB
                parser = PDBParser(QUIET=True)
                structure = parser.get_structure('structure', pdb_path)
                
                # Create FASTA content from structure
                sequence = self._extract_sequence_from_structure(structure)
                fasta_content = f">{design_name}\n{sequence}"
                
                try:
                    # Run prediction
                    st.write("Starting Chai-1 prediction...")
                    with app.run():
                        cif_content = chai1_inference.remote(fasta_content)
                    
                    # Clean up the temporary file
                    import shutil
                    shutil.rmtree(temp_dir)
                    
                    if cif_content:
                        return cif_content
                    else:
                        raise Exception("Chai-1 prediction failed to return results")
                except Exception as e:
                    st.error(f"Error in Chai-1 prediction: {str(e)}")
                    import traceback
                    st.error(f"Traceback:\n{traceback.format_exc()}")
                    raise
            else:
                raise ValueError("No PDB content found in selected binder")
        else:
            raise ValueError("Direct file access mode not supported - please select a binder from the gallery")
    
    def _create_fasta_content(self, run_id: str, design_name: str) -> str:
        """Helper method to create FASTA content"""
        import pandas as pd
        from Bio import PDB
        from Bio.PDB.Polypeptide import protein_letters_3to1
        import streamlit as st
        
        # Get binder sequence from selected binder
        binder_sequence = st.session_state.selected_binder.get('sequence')
        if not binder_sequence:
            # Fallback to reading from CSV if not in session state
            stats_file = Path(f"bindcraft/{run_id}/final_design_stats.csv")
            df = pd.read_csv(stats_file)
            binder_sequence = df.iloc[0]['Sequence']
        
        # Get target sequence from PDB
        pdb_path = Path(f"bindcraft/{run_id}/Accepted/{design_name}.pdb")
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure('structure', str(pdb_path))
        target_sequence = ""
        for residue in structure[0]['A']:
            if is_aa(residue):
                try:
                    three_letter = residue.get_resname()
                    one_letter = protein_letters_3to1.get(three_letter, 'X')
                    target_sequence += one_letter
                except:
                    target_sequence += 'X'
        
        # Create FASTA content matching the default input format
        fasta_content = f">protein|name=target\n{target_sequence}\n>protein|name=binder\n{binder_sequence}"
        return fasta_content

    def _extract_sequence_from_structure(self, structure):
        sequence = ""
        for residue in structure[0]['A']:
            if is_aa(residue):
                try:
                    three_letter = residue.get_resname()
                    one_letter = protein_letters_3to1.get(three_letter, 'X')
                    sequence += one_letter
                except:
                    sequence += 'X'
        return sequence

# Create singleton instance
predictor = Chai1Predictor() 