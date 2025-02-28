"""
Modal service for Boltz-1 structure prediction
"""
import modal
from pathlib import Path
import sys

# Path setup
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Initialize Modal
boltz_app = modal.App(name="boltz1-standard")  # Using a standard name

# Set up image with dependencies
boltz_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "boltz==0.3.2", 
    "biopython"
)

# Set up volume for model weights
boltz_model_volume = modal.Volume.from_name(
    "boltz1-weights", create_if_missing=True
)
boltz_models_dir = Path("/root/.cache/boltz/weights")  # Use Boltz's default location

@boltz_app.function(
    image=boltz_image,
    volumes={boltz_models_dir: boltz_model_volume},
    gpu="H100",
)
def boltz1_inference(yaml_content: str, pdb_content: bytes) -> tuple[bool, bytes, str]:
    """Runs Boltz-1 prediction on Modal"""
    import os
    import subprocess
    import tempfile
    from pathlib import Path
    
    print(f"Running Boltz-1 inference")
    
    # Download weights if needed
    try:
        print("Checking for Boltz weights...")
        weights_dir = Path("/root/.cache/boltz/weights")
        if not weights_dir.exists() or not list(weights_dir.glob("*.ckpt")):
            print("Downloading Boltz weights...")
            os.makedirs(weights_dir, exist_ok=True)
            result = subprocess.run(
                ["boltz", "download"], 
                check=False,
                capture_output=True,
                text=True
            )
            print(f"Download exit code: {result.returncode}")
            print(f"Download stdout: {result.stdout}")
            print(f"Download stderr: {result.stderr}")
    except Exception as e:
        print(f"Error checking/downloading weights: {e}")
    
    # Create temp directory
    tmp_dir = tempfile.mkdtemp()
    os.makedirs(f"{tmp_dir}/input", exist_ok=True)
    
    # Write input files
    yaml_path = f"{tmp_dir}/input.yaml"
    with open(yaml_path, "w") as f:
        f.write(yaml_content)
    
    pdb_path = f"{tmp_dir}/input/input.pdb"
    with open(pdb_path, "wb") as f:
        f.write(pdb_content)
    
    # Run prediction
    cmd = ["boltz", "predict", yaml_path, "--output", tmp_dir]
    print(f"Running command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"Command exit code: {result.returncode}")
    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr}")
    
    # Check for success
    if result.returncode != 0:
        print("Command failed")
        return False, b"", f"Boltz command failed: {result.stderr}"
    
    # Find output CIF file
    possible_cif_paths = [
        f"{tmp_dir}/predictions/input/input_model_0.cif",
        f"{tmp_dir}/input/input_model_0.cif",
        f"{tmp_dir}/input_model_0.cif"
    ]
    
    for path in possible_cif_paths:
        if os.path.exists(path):
            print(f"Found CIF file at {path}")
            with open(path, "rb") as f:
                cif_content = f.read()
            return True, cif_content, ""
    
    # If no specific path found, look for any .cif file
    for root, dirs, files in os.walk(tmp_dir):
        for file in files:
            if file.endswith(".cif"):
                path = os.path.join(root, file)
                print(f"Found CIF file at {path}")
                with open(path, "rb") as f:
                    cif_content = f.read()
                return True, cif_content, ""
    
    # No CIF file found
    return False, b"", "No CIF file found in output"

class BoltzPredictor:
    def __init__(self):
        self.app = boltz_app
        
        # Ensure app is deployed
        try:
            boltz_app.is_deployed() 
        except:
            pass # Will be deployed on first use
    
    def predict_structure_direct(self, pdb_content, design_name):
        """Run structure prediction with direct PDB content input"""
        import tempfile
        import shutil
        import traceback
        from streamlit_app.utils.bindcraft_utils import get_design_sequence
        from streamlit_app.utils.boltz_utils import create_yaml_content
        
        try:
            # Create temp files
            temp_dir = Path(tempfile.mkdtemp())
            temp_pdb = temp_dir / f"{design_name}.pdb"
            
            # Write the PDB content to the temp file
            with open(temp_pdb, 'wb') as f:
                f.write(pdb_content)
            
            # Get design sequence from CSV
            design_seq = get_design_sequence(design_name)
            
            # Create YAML using the proper format
            yaml_content = create_yaml_content(str(temp_pdb), design_seq)
            
            # Run Modal prediction
            try:
                print(f"[BOLTZ DEBUG] Starting Modal execution")
                with boltz_app.run():
                    success, cif_content, error_msg = boltz1_inference.remote(yaml_content, pdb_content)
                
                print(f"[BOLTZ DEBUG] Modal execution completed: success={success}, error_msg={error_msg}")
            except Exception as e:
                print(f"[BOLTZ DEBUG] ⚠️ Modal execution failed: {str(e)}")
                print(f"[BOLTZ DEBUG] Traceback: {traceback.format_exc()}")
                raise
            
            # Clean up
            shutil.rmtree(temp_dir)
            
            # Validate result
            if success:
                if not cif_content or len(cif_content) == 0:
                    raise ValueError("Received empty CIF content from Boltz")
                return cif_content
            else:
                raise Exception(f"Boltz prediction failed: {error_msg}")
        
        except Exception as e:
            print(f"[BOLTZ DEBUG] ❌ CRITICAL ERROR: {str(e)}")
            print(f"[BOLTZ DEBUG] Traceback: {traceback.format_exc()}")
            raise

# Create a singleton instance
boltz_predictor = BoltzPredictor() 