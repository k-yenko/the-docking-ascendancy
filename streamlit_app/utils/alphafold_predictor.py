import os
from pathlib import Path
from modal import Image, Mount, Stub

# Configure Modal settings
GPU = os.environ.get("MODAL_GPU", "L40S")
TIMEOUT = os.environ.get("MODAL_TIMEOUT", 20 * 60)

# Create Modal image for AF3
image = (
    Image.debian_slim(python_version="3.11")
    .micromamba()
    .apt_install("wget", "git")
    .pip_install(
        "alphafold @ git+https://github.com/google-deepmind/alphafold.git",
        "ml-collections",
        "dm-tree",
        "tensorflow-cpu",
    )
    .micromamba_install(
        "openmm=7.7.0",
        "pdbfixer",
        "kalign2=2.04",
        "hhsuite=3.3.0",
        channels=["conda-forge", "bioconda"]
    )
    .run_commands(
        'pip install --upgrade "jax[cuda12_pip]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html',
        gpu="a100",
    )
)

stub = Stub("alphafold3", image=image)

@stub.function(
    gpu=GPU,
    timeout=TIMEOUT,
)
def predict_structure(input_json: str):
    """
    Predict protein structure using AlphaFold 3
    
    Args:
        input_json: JSON string in AF3 format containing:
            - sequences
            - model seeds
            - other configuration
    
    Returns:
        List of (filename, content) tuples for prediction outputs
    """
    import json
    import tempfile
    from pathlib import Path
    
    # Create temp directories
    work_dir = Path("/tmp/af3_work")
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # Write input JSON
    input_path = work_dir / "input.json"
    with open(input_path, "w") as f:
        f.write(input_json)
    
    # Run AF3 prediction
    from alphafold.run_alphafold import predict_structure
    outputs = predict_structure(
        json_path=str(input_path),
        output_dir=str(work_dir),
        use_gpu=True
    )
    
    # Collect and return results
    results = []
    for output_path in work_dir.glob("*"):
        if output_path.is_file():
            with open(output_path, "rb") as f:
                results.append((output_path.name, f.read()))
                
    return results

def prepare_af3_input(
    sequence: str,
    name: str = "query",
    modifications: list = None,
    templates: list = None,
    model_seeds: list = None,
    unpaired_msa: str = None
) -> str:
    """
    Prepare input JSON for AF3 in the required format
    
    Args:
        sequence: Protein sequence
        name: Name for the prediction job
        modifications: List of protein modifications, each with ptmType and ptmPosition
        templates: List of template structures with mmcif and residue mappings
        model_seeds: List of random seeds for prediction (default: [42])
        unpaired_msa: Optional MSA in A3M format
        
    Returns:
        JSON string formatted for AF3
    """
    protein_dict = {
        "id": "A",
        "sequence": sequence,
    }
    
    # Add optional fields if provided
    if modifications:
        protein_dict["modifications"] = modifications
        
    if templates:
        protein_dict["templates"] = templates
        
    if unpaired_msa is not None:
        protein_dict["unpairedMsa"] = unpaired_msa
    
    input_json = {
        "name": name,
        "modelSeeds": model_seeds or [42],
        "sequences": [
            {
                "protein": protein_dict
            }
        ],
        "dialect": "alphafold3",
        "version": 2
    }
    
    return json.dumps(input_json)

def prepare_protein_modification(ptm_type: str, position: int) -> dict:
    """Helper function to create protein modification entries"""
    return {
        "ptmType": ptm_type,
        "ptmPosition": position
    }

def prepare_template(mmcif: str, query_indices: list, template_indices: list) -> dict:
    """Helper function to create template entries"""
    return {
        "mmcif": mmcif,
        "queryIndices": query_indices,
        "templateIndices": template_indices
    }
