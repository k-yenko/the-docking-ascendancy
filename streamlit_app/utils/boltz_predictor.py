from pathlib import Path
import modal
import yaml
import io
import tarfile
from datetime import datetime
import sys
import importlib.util
from modal import Stub, Image

# Initialize Modal
app = modal.App(name="boltz1-prediction")

# Set up image with dependencies
image = modal.Image.debian_slim(python_version="3.12").run_commands(
    "uv pip install --system --compile-bytecode boltz==0.3.2 biopython"
)

# Set up volume for model weights  
boltz_model_volume = modal.Volume.from_name(
    "boltz1-models", create_if_missing=True
)
models_dir = Path("/models/boltz1")

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

@app.cls(
    image=image,
    volumes={models_dir: boltz_model_volume},
    gpu="H100",
)
class BoltzPredictor:
    def __init__(self):
        # Store models_dir as instance variable
        self.models_dir = models_dir
        
    def extract_sequences_from_pdb(self, pdb_path: str):
        """Extract sequences from PDB file - runs locally"""
        from Bio import PDB
        from Bio.PDB.Polypeptide import protein_letters_3to1
        
        parser = PDB.PDBParser(QUIET=True)
        structure = parser.get_structure('structure', pdb_path)
        
        sequences = {}
        for model in structure:
            for chain in model:
                seq = ""
                for residue in chain:
                    if PDB.is_aa(residue):
                        try:
                            three_letter = residue.get_resname()
                            one_letter = protein_letters_3to1.get(three_letter, 'X')
                            seq += one_letter
                        except:
                            seq += 'X'
                if seq:  # Only store non-empty sequences
                    sequences[chain.id] = seq
        
        return sequences

    def create_yaml_content(self, pdb_path):
        """Create YAML content for Boltz-1 prediction"""
        # Extract sequences from the PDB file
        sequences = self.extract_sequences_from_pdb(pdb_path)
        
        # Create the YAML content with the expected "sequences" field
        yaml_content = {
            "version": 1,
            "sequences": []
        }
        
        # Add the sequences to the YAML
        for chain_id, sequence in sequences.items():
            yaml_content["sequences"].append({
                "protein": {
                    "id": chain_id,
                    "sequence": sequence
                }
            })
        
        # Convert to YAML string
        return yaml.dump(yaml_content, sort_keys=False)

    @modal.method()
    def boltz1_inference(self, yaml_content: str, pdb_content: bytes, args: str = "--use_msa_server") -> tuple[bool, bytes, str]:
        """Runs on Modal - returns success flag, data and error message instead of raising exceptions"""
        import shlex
        import subprocess
        from pathlib import Path
        import os
        import sys
        
        # Write input files
        input_path = Path("input.yaml")
        input_path.write_text(yaml_content)
        print(f"\nYAML file written to: {input_path.absolute()}")
        print(f"YAML content:\n{yaml_content}")
        
        pdb_path = Path("input.pdb")
        pdb_path.write_bytes(pdb_content)
        print(f"PDB file written to: {pdb_path.absolute()}")
        
        # Run Boltz prediction
        args = shlex.split(args)
        cmd = ["boltz", "predict", str(input_path), "--cache", str(self.models_dir)] + args
        print(f"\nRunning command: {' '.join(cmd)}")
        print(f"Current working directory: {os.getcwd()}")
        
        # Run without check=True to allow error inspection
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        # Print the output regardless of success/failure
        print("\nCommand output:")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print(f"Return code: {result.returncode}")
        
        # If command failed, return error info instead of raising exception
        if result.returncode != 0:
            error_msg = f"Boltz command failed with code {result.returncode}.\nSTDERR: {result.stderr}"
            print(error_msg)
            return (False, b"", error_msg)
        
        # Look for the CIF file in multiple possible locations
        possible_paths = [
            Path("predictions/input/input_model_0.cif"),
            Path("input/input_model_0.cif"),
            Path("boltz_results/predictions/input/input_model_0.cif"),
            Path("input_model_0.cif")
        ]
        
        print("\nSearching for CIF file in:")
        for path in possible_paths:
            print(f"- {path.absolute()} (exists: {path.exists()})")
            if path.exists():
                return (True, path.read_bytes(), "")
        
        # Try to find any .cif file
        cif_files = list(Path().glob("**/*.cif"))
        if cif_files:
            print(f"\nFound CIF files: {cif_files}")
            cif_path = cif_files[0]  # Use the first one found
            return (True, cif_path.read_bytes(), "")
        
        # If no CIF file found, return error
        error_msg = "No .cif files found in any subdirectory"
        print(error_msg)
        
        # Print directory contents to debug
        print("\nDirectory contents:")
        for item in Path().glob("**/*"):
            print(f"- {item}")
            
        return (False, b"", error_msg)

    def predict_structure(self, run_id, design_name):
        """
        Run structure prediction for a specific design
        
        Args:
            run_id: The run ID or None for selected binder
            design_name: The design name or None for selected binder
            
        Returns:
            The AlphaFold prediction as a string in mmCIF format
        """
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
            else:
                raise ValueError("No PDB content found in selected binder")
        else:
            raise ValueError("Direct file access mode not supported - please select a binder from the gallery")
        
        try:
            # Create YAML content
            yaml_content = self.create_yaml_content(pdb_path)
            
            # Run prediction
            st.write("Starting Boltz prediction...")
            with app.run():
                # Use self.boltz1_inference since it's an instance method
                success, cif_content, error_msg = self.boltz1_inference.remote(yaml_content, pdb_content)
            
            # Clean up the temporary file
            if 'temp_pdb' in locals():
                import shutil
                shutil.rmtree(temp_dir)
            
            if success:
                return cif_content
            else:
                raise Exception(error_msg)
        except Exception as e:
            st.error(f"Error in prediction: {str(e)}")
            import traceback
            st.error(f"Traceback:\n{traceback.format_exc()}")
            raise

# Create a singleton instance
predictor = BoltzPredictor()