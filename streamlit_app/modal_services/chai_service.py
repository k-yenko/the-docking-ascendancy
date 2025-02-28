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
    gpu="H100",
    volumes={chai_models_dir: chai_model_volume},
    image=chai_image,
)
def chai1_inference(fasta_content: str) -> list:
    """Runs Chai-1 prediction on Modal"""
    from pathlib import Path
    import torch
    from chai_lab import chai1
    
    results = chai1.predict_structure([fasta_content])
    return results

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
        from Bio.PDB import PDBParser
        
        try:
            # Create temp file for PDB
            temp_dir = Path(tempfile.mkdtemp())
            temp_pdb = temp_dir / f"{design_name}.pdb"
            
            # Write PDB content
            with open(temp_pdb, "wb") as f:
                f.write(pdb_content)
                
            # Parse PDB and extract sequence
            parser = PDBParser(QUIET=True)
            structure = parser.get_structure('structure', temp_pdb)
            sequence = self._extract_sequence_from_structure(structure)
            fasta_content = f">protein|name={design_name}\n{sequence}"
            
            # Run prediction
            print("Starting Chai-1 prediction...")
            with chai_app.run():
                results = chai1_inference.remote(fasta_content)
            
            # Clean up the temporary file
            shutil.rmtree(temp_dir)
            
            if results:
                # Extract just the first model's CIF content and convert to bytes
                first_model = results[0]
                scores, cif_content = first_model
                print(f"Generated {len(results)} models. Using the first one.")
                # Convert string to bytes since that's what the dashboard expects
                return cif_content.encode('utf-8')
            else:
                raise Exception("Chai-1 prediction failed to return results")
        except Exception as e:
            print(f"Error in Chai-1 prediction: {str(e)}")
            print(f"Traceback:\n{traceback.format_exc()}")
            raise

# Create singleton instance
chai1_predictor = Chai1Predictor() 