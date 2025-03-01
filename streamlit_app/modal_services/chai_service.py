"""
Modal service for Chai-1 structure prediction
"""
import modal
from pathlib import Path
import sys

# Path setup
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Initialize Modal
chai_app = modal.App(name="chai1-prediction")

# Set up image with dependencies
chai_image = modal.Image.debian_slim(python_version="3.12").run_commands(
    "uv pip install --system --compile-bytecode chai_lab==0.5.0 hf_transfer==0.1.8"
)

# Set up volumes with a unique name
chai_model_volume = modal.Volume.from_name(
    "chai1-models-v1", create_if_missing=True  # Changed name to ensure uniqueness
)
chai_models_dir = Path("/models/chai1")

# Configure image environment
chai_image = chai_image.env({
    "CHAI_DOWNLOADS_DIR": str(chai_models_dir),
    "HF_HUB_ENABLE_HF_TRANSFER": "1",
})

@chai_app.function(
    image=chai_image,
    gpu="A100",
)
def chai1_inference(fasta_content: str) -> bytes:
    """Runs Chai-1 prediction on Modal"""
    import os
    import tempfile
    from pathlib import Path
    import torch
    
    # Create temp directory for inputs and outputs
    tmp_dir = tempfile.mkdtemp()
    
    # Write input FASTA
    fasta_path = Path(f"{tmp_dir}/input.fasta")
    fasta_path.write_text(fasta_content.strip())
    
    # Create output directory
    output_dir = Path(f"{tmp_dir}/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Import chai_lab and run inference
    try:
        from chai_lab import chai1
        
        # Debug: Print available methods
        print(f"Available methods in chai_lab.chai1: {dir(chai1)}")
        
        # Use the correct method name based on Modal example
        chai1.run_inference(
            fasta_file=fasta_path,
            output_dir=output_dir,
            device=torch.device("cuda")
        )
        
        # Look for output files
        result_files = list(output_dir.glob("pred.model_idx_*.cif"))
        if not result_files:
            result_files = list(output_dir.glob("*.cif"))
        
        if result_files:
            # Return the first model's CIF content
            with open(result_files[0], "rb") as f:
                return f.read()
        else:
            raise ValueError(f"No CIF files found in output directory: {list(output_dir.glob('*'))}")
            
    except Exception as e:
        print(f"Error in Chai-1 prediction: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise

class Chai1Predictor:
    def __init__(self):
        self.app = chai_app
        
        # Ensure app is deployed
        try:
            chai_app.is_deployed() 
        except:
            pass # Will be deployed on first use
    
    def _extract_sequence_from_structure(self, structure):
        """Extract sequence from a Bio.PDB Structure object"""
        from Bio.PDB import is_aa
        from Bio.PDB.Polypeptide import protein_letters_3to1
        
        sequence = ""
        for model in structure:
            for chain in model:
                for residue in chain:
                    if is_aa(residue):
                        try:
                            three_letter = residue.get_resname()
                            one_letter = protein_letters_3to1.get(three_letter, 'X')
                            sequence += one_letter
                        except:
                            sequence += 'X'
        return sequence
    
    def predict_structure_direct(self, pdb_content, design_name):
        """Run structure prediction with direct PDB content input"""
        import tempfile
        import shutil
        import traceback
        from streamlit_app.utils.common_utils import extract_sequences_from_pdb
        from Bio import PDB
        
        try:
            # Create temp files
            temp_dir = Path(tempfile.mkdtemp())
            temp_pdb = temp_dir / f"{design_name}.pdb"
            
            # Write the PDB content to the temp file
            with open(temp_pdb, 'wb') as f:
                f.write(pdb_content)
            
            # Extract sequence from PDB
            sequences = extract_sequences_from_pdb(temp_pdb)
            
            # Create FASTA content
            fasta_content = ""
            for chain_id, seq in sequences.items():
                fasta_content += f">protein|name={design_name}_{chain_id}\n{seq}\n"
            
            # Run Modal prediction
            try:
                print(f"[CHAI DEBUG] Starting Modal execution")
                with chai_app.run():
                    # The modified function now returns CIF content directly
                    cif_content = chai1_inference.remote(fasta_content)
                
                print(f"[CHAI DEBUG] Modal execution completed")
            except Exception as e:
                print(f"[CHAI DEBUG] ⚠️ Modal execution failed: {str(e)}")
                print(f"[CHAI DEBUG] Traceback: {traceback.format_exc()}")
                raise
            
            # Clean up
            shutil.rmtree(temp_dir)
            
            # Validate result
            if not cif_content or len(cif_content) == 0:
                raise ValueError("Received empty CIF content from Chai-1")
            
            return cif_content
        
        except Exception as e:
            print(f"[CHAI DEBUG] ❌ CRITICAL ERROR: {str(e)}")
            print(f"[CHAI DEBUG] Traceback: {traceback.format_exc()}")
            raise

# Create singleton instance
chai1_predictor = Chai1Predictor() 