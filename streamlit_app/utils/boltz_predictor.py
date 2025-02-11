from pathlib import Path
import modal
import yaml
import io
import tarfile
import modal
from datetime import datetime

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

    def create_yaml_content(self, pdb_path: str) -> str:
        """Create YAML content for Boltz prediction - runs locally"""
        # Import pandas here since it's only needed locally
        import pandas as pd
        
        # Get binder sequence from stats file
        stats_file = Path(pdb_path).parent.parent / "final_design_stats.csv"
        df = pd.read_csv(stats_file)
        binder_sequence = df.iloc[0]['Sequence']
        
        # Extract target sequence from PDB
        sequences = self.extract_sequences_from_pdb(str(pdb_path))
        target_sequence = sequences.get('A', '')
        
        # Create YAML content matching output_example.yaml exactly
        yaml_content = {
            'version': 1,
            'sequences': [
                {
                    'protein': {
                        'id': 'A',
                        'sequence': target_sequence
                    }
                },
                {
                    'protein': {
                        'id': 'B',
                        'sequence': binder_sequence
                    }
                }
            ]
        }
        
        return yaml.dump(yaml_content, sort_keys=False, indent=2)

    @modal.method()
    def boltz1_inference(self, yaml_content: str, pdb_content: bytes, args: str = "--use_msa_server") -> bytes:
        """Runs on Modal - no streamlit dependency needed here"""
        import shlex
        import subprocess
        from pathlib import Path
        import os
        
        try:
            # Write input files
            input_path = Path("input.yaml")
            input_path.write_text(yaml_content)
            print(f"\nYAML file written to: {input_path.absolute()}")
            
            pdb_path = Path("input.pdb")
            pdb_path.write_bytes(pdb_content)
            print(f"PDB file written to: {pdb_path.absolute()}")
            
            # Run Boltz prediction
            args = shlex.split(args)
            cmd = ["boltz", "predict", str(input_path), "--cache", str(self.models_dir)] + args
            print(f"\nRunning command: {' '.join(cmd)}")
            print(f"Current working directory: {os.getcwd()}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            print("\nCommand output:")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            
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
            
            print("\nAll files in current directory (recursive):")
            for item in Path().glob("**/*"):
                print(f"- {item}")
            
            # Try to find any .cif file
            cif_files = list(Path().glob("**/*.cif"))
            if cif_files:
                print(f"\nFound CIF files: {cif_files}")
                cif_path = cif_files[0]  # Use the first one found
                return cif_path.read_bytes()
            else:
                raise FileNotFoundError("No .cif files found in any subdirectory")
            
        except Exception as e:
            print(f"Error in boltz1_inference: {str(e)}")
            print("\nFinal directory contents:")
            for item in Path().glob("**/*"):
                print(f"- {item}")
            raise

    def predict_structure(self, run_id: str, design_name: str):
        """Main prediction function that interfaces with Streamlit"""
        import streamlit as st
        
        try:
            # Get PDB file path
            if 'pdb_path' in st.session_state.selected_binder:
                pdb_path = Path(st.session_state.selected_binder['pdb_path'])
            else:
                pdb_path = Path("bindcraft") / run_id / "Accepted" / f"{design_name}.pdb"
            
            if not pdb_path.exists():
                raise FileNotFoundError(f"PDB file not found: {pdb_path}")
            
            # Create and display YAML content
            yaml_content = self.create_yaml_content(str(pdb_path))
            st.write("### YAML Configuration:")
            st.code(yaml_content, language="yaml")
            
            # Run prediction
            st.write("Starting Boltz prediction...")
            with app.run():
                cif_content = self.boltz1_inference.remote(yaml_content, pdb_path.read_bytes())
            
            if cif_content:
                st.write(f"Boltz prediction successful! Result size: {len(cif_content)} bytes")
                
                # Store in session state
                if 'prediction_history' not in st.session_state:
                    st.session_state.prediction_history = {}
                    
                prediction_id = f"{run_id}_{design_name}"
                st.session_state.prediction_history[prediction_id] = {
                    'timestamp': datetime.now().isoformat(),
                    'method': 'Boltz-1',
                    'run_id': run_id,
                    'design_name': design_name,
                    'cif_content': cif_content,  # Store CIF directly
                    'yaml_config': yaml_content
                }
                
                # Success message and return
                st.success("Prediction complete! Redirecting to results dashboard...")
                return cif_content
            
        except Exception as e:
            st.error(f"Error in predict_structure: {str(e)}")
            raise

# Create a singleton instance
predictor = BoltzPredictor()