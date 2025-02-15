from pathlib import Path
import modal
from datetime import datetime
import hashlib
from uuid import uuid4

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
    def predict_structure(self, run_id: str, design_name: str):
        """Main prediction function that interfaces with Streamlit"""
        import streamlit as st
        
        try:
            # Create FASTA content from the selected binder
            fasta_content = self._create_fasta_content(run_id, design_name)
            st.write("### FASTA Input:")
            st.code(fasta_content, language="text")
            
            # Run prediction using Modal
            st.write("Starting Chai-1 prediction...")
            with app.run():
                results = chai1_inference.remote(fasta_content)
            
            if results:
                # Use first model for now
                scores, cif_content = results[0]
                st.write(f"Chai-1 prediction successful! Generated {len(results)} models")
                return cif_content.encode()
                
        except Exception as e:
            st.error(f"Error in predict_structure: {str(e)}")
            raise
    
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
        parser = PDB.PDBParser(QUIET=True)
        structure = parser.get_structure('structure', str(pdb_path))
        target_sequence = ""
        for residue in structure[0]['A']:
            if PDB.is_aa(residue):
                try:
                    three_letter = residue.get_resname()
                    one_letter = protein_letters_3to1.get(three_letter, 'X')
                    target_sequence += one_letter
                except:
                    target_sequence += 'X'
        
        # Create FASTA content matching the default input format
        fasta_content = f">protein|name=target\n{target_sequence}\n>protein|name=binder\n{binder_sequence}"
        return fasta_content

# Create singleton instance
predictor = Chai1Predictor() 