from dataclasses import dataclass
from pathlib import Path
import modal

MINUTES = 60
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

@dataclass
class MSA:
    data: str
    path: Path

def create_yaml_content(pdb_path: str) -> str:
    """Create YAML content for Boltz prediction - runs locally"""
    pdb_path = Path(pdb_path)
    stats_file = pdb_path.parent.parent / "final_design_stats.csv"
    df = pd.read_csv(stats_file)
    binder_sequence = df.iloc[0]['Sequence']
    
    yaml_content = {
        "version": 1,
        "sequences": [
            {
                "protein": {
                    "sequence": binder_sequence,
                    "pdb": str(pdb_path),
                    "chain": "B"
                }
            }
        ]
    }
    
    return yaml.dump(yaml_content, sort_keys=False)

@app.function(
    image=image,
    volumes={models_dir: boltz_model_volume},
    timeout=10 * MINUTES,
    gpu="H100",
)
def boltz1_inference(yaml_content: str, pdb_path: str, args: str = "--use_msa_server") -> bytes:
    """Runs on Modal"""
    import shlex
    import subprocess
    from pathlib import Path
    
    # Write YAML file
    input_path = Path("input.yaml")
    input_path.write_text(yaml_content)
    
    # Print YAML content for debugging
    print("YAML content:")
    print(yaml_content)

    args = shlex.split(args)

    print(f"🧬 predicting structure using boltz model from {models_dir}")
    try:
        # Capture output and error
        result = subprocess.run(
            ["boltz", "predict", input_path, "--cache", str(models_dir)] + args,
            check=True,
            capture_output=True,
            text=True
        )
        print("Command output:", result.stdout)
    except subprocess.CalledProcessError as e:
        print("Command failed with error:", e.stderr)
        raise

    print("🧬 packaging up outputs")
    output_bytes = package_outputs(
        f"boltz_results_{input_path.with_suffix('').name}"
    )

    return output_bytes

def package_outputs(output_dir: str) -> bytes:
    import io
    import tarfile

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
        tar.add(output_dir, arcname=output_dir)
    return tar_buffer.getvalue()

def predict_structure(run_id: str, design_name: str):
    """Run Boltz-1 prediction for a specific design - runs locally"""
    # Get PDB file path locally
    if 'pdb_path' in st.session_state.selected_binder:
        pdb_path = Path(st.session_state.selected_binder['pdb_path'])
    else:
        pdb_path = Path("bindcraft") / run_id / "Accepted" / f"{design_name}.pdb"
        if not pdb_path.exists():
            raise FileNotFoundError(f"PDB file not found for design {design_name} in run {run_id}")
    
    # Create YAML content locally
    yaml_content = create_yaml_content(str(pdb_path))
    
    # Run prediction remotely
    with app.run():
        result = boltz1_inference.remote(yaml_content, str(pdb_path))
    
    return result