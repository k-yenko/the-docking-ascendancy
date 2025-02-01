import modal
from pathlib import Path
import sys
import streamlit as st

MINUTES = 60  # seconds
app = modal.App(name="boltz1-prediction")

# Set up the image with required dependencies
image = modal.Image.debian_slim(python_version="3.12").run_commands(
    "uv pip install --system --compile-bytecode boltz==0.3.2 biopython"
)

# Set up volume for model weights
boltz_model_volume = modal.Volume.from_name(
    "boltz1-models", create_if_missing=True
)
models_dir = Path("/models/boltz1")

def extract_sequences_from_pdb(pdb_path: str):
    """Extract sequences from PDB file using BioPython"""
    from Bio import PDB
    from Bio.PDB.Polypeptide import three_to_one

    parser = PDB.PDBParser()
    structure = parser.get_structure('structure', pdb_path)
    
    sequences = {}
    for model in structure:
        for chain in model:
            seq = ""
            for residue in chain:
                if PDB.is_aa(residue):
                    try:
                        seq += three_to_one(residue.get_resname())
                    except:
                        seq += 'X'
            if seq:  # Only store non-empty sequences
                sequences[chain.id] = seq
    
    return sequences

@app.function(
    image=image,
    volumes={models_dir: boltz_model_volume},
    timeout=10 * MINUTES,
    gpu="H100",
)
def run_boltz_prediction(pdb_path: str):
    import shlex
    import subprocess
    import yaml
    from pathlib import Path
    import os
    
    # Create a working directory
    work_dir = Path("work_dir")
    work_dir.mkdir(exist_ok=True)
    
    # Extract sequences from PDB
    sequences = extract_sequences_from_pdb(pdb_path)
    
    # Determine which sequence is the binder (usually shorter)
    # and which is the target (usually longer)
    seq_lengths = {chain_id: len(seq) for chain_id, seq in sequences.items()}
    binder_chain = min(seq_lengths, key=seq_lengths.get)
    target_chain = max(seq_lengths, key=seq_lengths.get)
    
    # Create YAML input
    input_yaml = {
        "sequences": [
            {
                "protein": {
                    "sequence": sequences[target_chain],
                    "name": "target"
                }
            },
            {
                "protein": {
                    "sequence": sequences[binder_chain],
                    "name": "binder",
                    "pdb": str(pdb_path),
                    "chain": binder_chain
                }
            }
        ]
    }
    
    input_path = work_dir / "input.yaml"
    with open(input_path, 'w') as f:
        yaml.dump(input_yaml, f)
    
    # Run Boltz prediction
    args = ["--use_msa_server"]
    subprocess.run(
        ["boltz", "predict", str(input_path), "--cache", str(models_dir)] + args,
        check=True,
        cwd=work_dir
    )
    
    # Package and return results
    output_bytes = package_outputs(str(work_dir))
    return output_bytes

def package_outputs(output_dir: str) -> bytes:
    import io
    import tarfile

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
        tar.add(output_dir, arcname=output_dir)
    return tar_buffer.getvalue()

def get_pdb_path(run_id: str, design_name: str) -> Path:
    """
    Get the path to the PDB file for a specific design
    
    Args:
        run_id (str): The BindCraft run ID (e.g., "2501290927")
        design_name (str): Name of the design
        
    Returns:
        Path: Path to the PDB file
    """
    pdb_path = Path("bindcraft") / run_id / "Accepted" / f"{design_name}.pdb"
    
    if not pdb_path.exists():
        raise FileNotFoundError(f"PDB file not found for design {design_name} in run {run_id}")
    
    return pdb_path

def predict_structure(run_id: str, design_name: str):
    """
    Run Boltz-1 prediction for a specific design
    
    Args:
        run_id (str): The BindCraft run ID (e.g., "2501290927")
        design_name (str): Name of the design
    
    Returns:
        dict: Prediction results
    """
    # Get PDB file path - use the path that was stored in the binder object
    if 'pdb_path' in st.session_state.selected_binder:
        pdb_path = Path(st.session_state.selected_binder['pdb_path'])
    else:
        # Fallback to constructing the path
        pdb_path = get_pdb_path(run_id, design_name)
    
    # Run prediction
    with app.run():
        result = run_boltz_prediction(str(pdb_path))
    
    return result