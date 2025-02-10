from pathlib import Path
import modal
import yaml
import io
import tarfile

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

# Set up download image
download_image = (
    modal.Image.debian_slim()
    .pip_install("huggingface_hub[hf_transfer]==0.26.3")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

# Create a separate function for downloading the model
@app.function(
    volumes={models_dir: boltz_model_volume},
    timeout=20 * 60,
    image=download_image,
)
def download_model_remote(force_download: bool = False):
    from huggingface_hub import snapshot_download
    
    snapshot_download(
        repo_id="boltz-community/boltz-1",
        revision="7c1d83b779e4c65ecc37dfdf0c6b2788076f31e1",
        local_dir=models_dir,
        force_download=force_download,
    )
    boltz_model_volume.commit()
    print(f"🧬 model downloaded to {models_dir}")

@app.cls(
    image=image,
    volumes={models_dir: boltz_model_volume},
    gpu="H100",
)
class BoltzPredictor:
    def __init__(self):
        pass
        
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
        import shlex
        import subprocess
        from pathlib import Path
        import os
        
        try:
            # Create output directory
            output_dir = Path("boltz_results")
            output_dir.mkdir(exist_ok=True)
            
            # Write input files
            input_path = Path("input.yaml")
            input_path.write_text(yaml_content)
            print("\nYAML content:")
            print(yaml_content)
            
            # Write PDB file
            pdb_path = Path("input.pdb")
            pdb_path.write_bytes(pdb_content)
            print(f"\nPDB file written: {pdb_path.exists()}, size: {len(pdb_content)} bytes")
            
            # Run prediction with full output capture
            args = shlex.split(args)
            cmd = ["boltz", "predict", str(input_path), "--cache", str(models_dir)] + args
            print(f"\nRunning command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False  # Don't raise error yet so we can see output
            )
            
            # Print full command output
            print("\nCommand stdout:")
            print(result.stdout)
            print("\nCommand stderr:")
            print(result.stderr)
            
            if result.returncode != 0:
                raise RuntimeError(f"Boltz command failed with code {result.returncode}")
            
            # Check what files were created
            print("\nCurrent directory contents:")
            for item in Path().glob("**/*"):  # Recursive glob to see all files
                print(f"- {item}")
            
            # Package outputs if they exist
            print("\n🧬 packaging up outputs")
            if not output_dir.exists():
                raise FileNotFoundError(f"Output directory not found: {output_dir}")
            
            if not any(output_dir.iterdir()):
                raise FileNotFoundError(f"Output directory is empty: {output_dir}")
            
            # Create tar archive
            tar_buffer = io.BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
                tar.add(output_dir)
                print(f"Added to tar: {[m.name for m in tar.getmembers()]}")
            
            return tar_buffer.getvalue()
            
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
            # Download model first using the standalone function
            with app.run():
                download_model_remote.remote()
            
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
                result = self.boltz1_inference.remote(yaml_content, pdb_path.read_bytes())
                
            if result:
                st.write(f"Boltz prediction successful! Result size: {len(result)} bytes")
                # Verify the result contains a CIF file
                tar_buffer = io.BytesIO(result)
                with tarfile.open(fileobj=tar_buffer, mode='r:gz') as tar:
                    cif_path = "boltz_results/predictions/input/input_model_0.cif"
                    try:
                        cif_info = tar.getmember(cif_path)
                        st.write(f"Found CIF file in results: {cif_path}")
                    except KeyError:
                        st.write("Available files in result:", [m.name for m in tar.getmembers()])
                        raise ValueError("No CIF file found in prediction results")
            else:
                st.write("Boltz prediction returned no result")
                
            return result
            
        except Exception as e:
            st.error(f"Error in predict_structure: {str(e)}")
            raise

# Create a singleton instance
predictor = BoltzPredictor()