from pathlib import Path
import modal
import yaml
import pandas as pd
import sys
import os

# Initialize Modal
app = modal.App(name="boltz1-prediction")

# Set up image with dependencies - only what's needed in Modal
image = modal.Image.debian_slim(python_version="3.12").run_commands(
    "uv pip install --system --compile-bytecode boltz==0.3.2"
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

@app.function(
    image=image,
    volumes={models_dir: boltz_model_volume},
    timeout=600,
    gpu="H100",
)
def boltz1_inference(yaml_content: str, pdb_content: bytes, args: str = "--use_msa_server") -> bytes:
    """Runs on Modal - no streamlit dependency needed here"""
    import shlex
    import subprocess
    from pathlib import Path
    import io
    import tarfile
    
    try:
        # Write input files
        input_path = Path("input.yaml")
        input_path.write_text(yaml_content)
        print("\nYAML content:")
        print(yaml_content)
        
        pdb_path = Path("input.pdb")
        pdb_path.write_bytes(pdb_content)
        print(f"\nPDB file written to {pdb_path}, size: {len(pdb_content)} bytes")
        
        # Check model directory
        print(f"\nModel directory {models_dir}:")
        print(f"Exists: {models_dir.exists()}")
        if models_dir.exists():
            print("Contents:", list(models_dir.glob("*")))
        
        # Run prediction with full error output
        args = shlex.split(args)
        cmd = ["boltz", "predict", str(input_path), "--cache", str(models_dir)] + args
        print(f"\nRunning command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            error_msg = f"""
            Command failed with exit code {result.returncode}
            STDOUT: {result.stdout}
            STDERR: {result.stderr}
            """
            raise RuntimeError(error_msg)
            
        print("\nCommand output:", result.stdout)
        
        # Package outputs
        print("🧬 packaging up outputs")
        output_dir = Path("boltz_results")
        if not output_dir.exists():
            raise FileNotFoundError(f"Output directory not found: {output_dir}")
        
        # Create tar archive
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            tar.add(output_dir)
        
        return tar_buffer.getvalue()
        
    except Exception as e:
        error_msg = f"""
        Error in boltz1_inference:
        {str(e)}
        
        Working directory: {Path.cwd()}
        Python path: {sys.path}
        Environment: {os.environ}
        """
        print(error_msg, file=sys.stderr)
        raise RuntimeError(error_msg)

@app.function(
    volumes={models_dir: boltz_model_volume},
    timeout=20 * 60,  # 20 minutes
    image=download_image,
)
def download_model(force_download: bool = False):
    from huggingface_hub import snapshot_download
    
    snapshot_download(
        repo_id="boltz-community/boltz-1",
        local_dir=models_dir,
        force_download=force_download,
    )
    boltz_model_volume.commit()
    print(f"🧬 model downloaded to {models_dir}")

# These functions run locally, can use streamlit
def create_yaml_content(pdb_path: str) -> str:
    """Create YAML content for Boltz prediction - runs locally"""
    # Get binder sequence from stats file
    stats_file = Path(pdb_path).parent.parent / "final_design_stats.csv"
    df = pd.read_csv(stats_file)
    binder_sequence = df.iloc[0]['Sequence']
    
    # Create YAML content matching the schema
    yaml_content = {
        "sequences": [
            {
                "id": ["B"],  # List of chain IDs
                "protein": {
                    "sequence": binder_sequence,
                    "pdb": "input.pdb",  # Local path in Modal
                    "chain": "B"
                }
            }
        ]
    }
    
    print("Generated YAML content:")
    print(yaml.dump(yaml_content, sort_keys=False))
    
    return yaml.dump(yaml_content, sort_keys=False)

def predict_structure(run_id: str, design_name: str):
    """Run Boltz-1 prediction for a specific design - runs locally"""
    import streamlit as st
    
    try:
        # Download model first
        with app.run():
            download_model.remote()
        
        # Get PDB file path
        if 'pdb_path' in st.session_state.selected_binder:
            pdb_path = Path(st.session_state.selected_binder['pdb_path'])
        else:
            pdb_path = Path("bindcraft") / run_id / "Accepted" / f"{design_name}.pdb"
        
        if not pdb_path.exists():
            raise FileNotFoundError(f"PDB file not found: {pdb_path}")
        
        # Create YAML content
        yaml_content = create_yaml_content(str(pdb_path))
        
        # Run prediction
        st.write("Starting Boltz prediction...")
        with app.run():
            result = boltz1_inference.remote(yaml_content, pdb_path.read_bytes())
            
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