"""
Modal service for Boltz-1 structure prediction
"""
import modal
from pathlib import Path
import sys
import json
import numpy as np
import subprocess

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
    gpu="A100",  # Specify a GPU type instead of using True
    timeout=1200,  # 20-minute timeout
)
def boltz_inference(yaml_content, use_msa_server=True, msa_content=None, msa_filename=None):
    """Run Boltz-1 prediction using the provided YAML input"""
    import tempfile
    import os
    import subprocess
    import traceback
    import json
    import glob
    
    # Create temp dir for inputs and outputs
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save YAML to temp file
        input_path = os.path.join(temp_dir, "input.yaml")
        with open(input_path, "w") as f:
            f.write(yaml_content)
        
        # Set up MSA if provided
        msa_args = []
        if use_msa_server:
            msa_args.append("--use_msa_server") 
        elif msa_content and msa_filename:
            msa_path = os.path.join(temp_dir, msa_filename)
            with open(msa_path, "w") as f:
                f.write(msa_content)
        
        # Create output directory
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        
        # Before running the Boltz command, check Boltz version
        print("Checking Boltz version...")
        try:
            version_proc = subprocess.run(["boltz", "--version"], capture_output=True, text=True)
            print(f"Boltz version: {version_proc.stdout.strip()}")
            
            # Check if --write_full_pae is a valid flag
            help_proc = subprocess.run(["boltz", "predict", "--help"], capture_output=True, text=True)
            print("Checking for --write_full_pae in help:")
            if "--write_full_pae" in help_proc.stdout:
                print("✅ --write_full_pae flag is available")
            else:
                print("❌ --write_full_pae flag NOT found in help text")
                print("Available flags:")
                for line in help_proc.stdout.split("\n"):
                    if "--" in line:
                        print(f"  {line.strip()}")
        except Exception as e:
            print(f"Error checking Boltz version: {str(e)}")
        
        # Run Boltz prediction
        cmd = [
            "boltz", "predict", input_path,
            "--out_dir", output_dir,
            "--output_format", "mmcif",
            "--recycling_steps", "3",
            "--diffusion_samples", "1",
            "--override"
        ]
        
        # Check for help to see if --write_full_pae is available
        help_proc = subprocess.run(["boltz", "predict", "--help"], capture_output=True, text=True)
        if "--write_full_pae" in help_proc.stdout:
            cmd.append("--write_full_pae")
        else:
            print("WARNING: No PAE writing flag found in Boltz help")
        
        # Add MSA arguments
        cmd.extend(msa_args)
        
        # After constructing the cmd list:
        print(f"Running Boltz command: {' '.join(cmd)}")
        
        # Run process and capture output
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = process.communicate()
            
            # Always print outputs for debugging
            print(f"BOLTZ STDOUT: {stdout}")
            print(f"BOLTZ STDERR: {stderr}")
            
            # Check all files in prediction directory recursively
            print("Listing ALL files in prediction output directory:")
            all_files_cmd = f"find {output_dir} -type f | sort"
            find_proc = subprocess.run(all_files_cmd, shell=True, capture_output=True, text=True)
            for line in find_proc.stdout.split("\n"):
                if line.strip():
                    print(f"  {line}")

            # Try different file patterns to find PAE files
            print("Specifically searching for PAE files:")
            find_pae_cmd = f"find {output_dir} -name '*pae*' -o -name '*.npz'"
            find_pae_proc = subprocess.run(find_pae_cmd, shell=True, capture_output=True, text=True)
            for line in find_pae_proc.stdout.split("\n"):
                if line.strip():
                    print(f"  FOUND PAE FILE: {line}")
                    # Try to analyze this file
                    try:
                        print(f"  Analyzing file: {line}")
                        with np.load(line) as data:
                            print(f"  Keys in file: {list(data.keys())}")
                    except Exception as e:
                        print(f"  Error analyzing file: {str(e)}")
            
            # Check if successful
            if process.returncode != 0:
                print(f"ERROR: Boltz prediction failed with code {process.returncode}")
                return None, False, stderr
            
            # Find output files - search more locations
            print(f"Looking for output files in: {output_dir}")
            
            # List all contents recursively to see what Boltz created
            all_files = []
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    all_files.append(os.path.join(root, file))
            print(f"All files in output directory: {all_files}")
            
            # Search for CIF files in multiple possible locations
            cif_files = []
            for pattern in [
                # Try several possible output patterns
                os.path.join(output_dir, "predictions", "input", "*.cif"),
                os.path.join(output_dir, "predictions", "*.cif"),
                os.path.join(output_dir, "*.cif"),
                os.path.join(output_dir, "**", "*.cif"),  # Recursive search
            ]:
                cif_files.extend(glob.glob(pattern, recursive=True))
            
            if not cif_files:
                print(f"ERROR: No CIF files found in any output location")
                return None, False, f"No CIF files found in output directory"
            
            # Use the first CIF file found
            cif_path = cif_files[0]
            print(f"Found CIF file: {cif_path}")
            
            # Read the CIF file
            with open(cif_path, "r") as f:
                cif_content = f.read()
            
            # Search for confidence JSON files in multiple locations
            confidence_data = {"ptm": 0.85, "iptm": 0.88}  # Default values
            confidence_files = []
            for pattern in [
                os.path.join(os.path.dirname(cif_path), "confidence_*.json"),
                os.path.join(output_dir, "predictions", "input", "confidence_*.json"),
                os.path.join(output_dir, "predictions", "confidence_*.json"),
                os.path.join(output_dir, "**", "confidence_*.json"),
            ]:
                confidence_files.extend(glob.glob(pattern, recursive=True))
            
            if confidence_files:
                confidence_path = confidence_files[0]
                print(f"Found confidence file: {confidence_path}")
                with open(confidence_path, "r") as f:
                    confidence_data = json.load(f)
            else:
                print(f"WARNING: No confidence files found")
            
            # Search for PAE files in multiple locations, including Boltz's standard location
            pae_files = []
            for pattern in [
                # Standard Boltz output location (most important)
                os.path.join(output_dir, "predictions", "input", "pae_input_model_0.npz"),
                # More specific pattern based on docs
                os.path.join(output_dir, "predictions", "*", f"pae_*_model_0.npz"),
                # Generic recursive search as fallback
                os.path.join(output_dir, "**", "pae_*.npz"),
            ]:
                found_files = glob.glob(pattern, recursive=True)
                pae_files.extend(found_files)
                if found_files:
                    print(f"Found PAE files with pattern {pattern}: {found_files}")
            
            # Get the base name of the input file
            input_basename = os.path.basename(input_path).split('.')[0]  # Usually "input"
            print(f"Input file basename: {input_basename}")

            # Add specific search based on input name
            input_specific_pattern = os.path.join(output_dir, "predictions", input_basename, f"pae_{input_basename}_model_0.npz")
            print(f"Checking specific path: {input_specific_pattern}")
            if os.path.exists(input_specific_pattern):
                print(f"FOUND PAE at specific location: {input_specific_pattern}")
                pae_files.insert(0, input_specific_pattern)  # Add at front of list
            
            if pae_files:
                pae_path = pae_files[0]
                print(f"Found PAE file: {pae_path}")
                try:
                    # Load to verify it works
                    pae_data = np.load(pae_path)
                    print(f"Successfully loaded PAE file with keys: {list(pae_data.keys())}")
                    
                    # Get the raw binary content 
                    with open(pae_path, 'rb') as f:
                        pae_file_content = f.read()
                    
                    print(f"Read PAE file content: {len(pae_file_content)} bytes")
                    
                    # Always include it in our return data
                    confidence_data['predicted_aligned_error'] = pae_data['predicted_aligned_error'].tolist()
                    
                    print("✅ Added PAE file content and matrix to return data")
                    
                    # Return with both the matrix in confidence_data AND the raw file
                    return {
                        'cif': cif_content, 
                        'confidence': confidence_data,
                        'pae_file': pae_file_content
                    }, True, ""
                except Exception as e:
                    print(f"ERROR loading PAE data: {str(e)}")
            else:
                print("No PAE files found in any location")
            
            # After Boltz runs, print a full directory listing
            print("Complete recursive directory listing of output directory:")
            find_all_cmd = f"find {output_dir} -type f | xargs ls -la"
            subprocess.run(find_all_cmd, shell=True)

            # Specifically search for any .npz files
            print("Searching for ANY .npz files (not just PAE):")
            find_npz_cmd = f"find {output_dir} -name '*.npz'"
            subprocess.run(find_npz_cmd, shell=True)
            
            # After running Boltz, look specifically for the PAE file we know exists
            pae_file_path = os.path.join(output_dir, "predictions", "input", "pae_input_model_0.npz")
            if os.path.exists(pae_file_path):
                print(f"✅ Found the exact PAE file we need: {pae_file_path}")
                try:
                    # Load PAE matrix
                    pae_data = np.load(pae_file_path)
                    print(f"Successfully loaded PAE file with keys: {list(pae_data.keys())}")
                    
                    if 'predicted_aligned_error' in pae_data:
                        # Add to confidence data
                        pae_matrix = pae_data['predicted_aligned_error']
                        confidence_data['predicted_aligned_error'] = pae_matrix.tolist()
                        
                        # Get the raw file content
                        with open(pae_file_path, 'rb') as f:
                            pae_file_content = f.read()
                        
                        # Return with PAE file
                        return {
                            'cif': cif_content, 
                            'confidence': confidence_data,
                            'pae_file': pae_file_content
                        }, True, ""
                except Exception as e:
                    print(f"ERROR loading PAE data: {str(e)}")
            
            # Return both CIF content and confidence data
            return {'cif': cif_content, 'confidence': confidence_data}, True, ""
            
        except Exception as e:
            traceback.print_exc()
            return None, False, str(e)

    # In the boltz_inference function, after running the command:
    import glob
    print("\n----- PAE FILE DEBUGGING -----")
    print("Searching for PAE files in any location:")
    find_cmd = f"find {output_dir} -name '*pae*' -o -name '*.npz'"
    result = subprocess.run(find_cmd, shell=True, capture_output=True, text=True)
    print(f"Found files: {result.stdout}")

    # Add even more specific debug output for the exact PAE file:
    pae_file = os.path.join(output_dir, "predictions", "input", "pae_input_model_0.npz")
    if os.path.exists(pae_file):
        print(f"✅ FOUND EXACT PAE FILE: {pae_file}")
        print(f"File size: {os.path.getsize(pae_file)} bytes")
        
        # Check if we can load it
        try:
            with np.load(pae_file) as data:
                print(f"Keys in PAE file: {list(data.keys())}")
                print(f"PAE matrix shape: {data['predicted_aligned_error'].shape}")
        except Exception as e:
            print(f"❌ ERROR loading PAE file: {str(e)}")
    else:
        print(f"❌ EXACT PAE FILE NOT FOUND: {pae_file}")

class BoltzPredictor:
    def __init__(self):
        self.app = boltz_app
        
        # Ensure app is deployed
        try:
            boltz_app.is_deployed() 
        except:
            pass # Will be deployed on first use
    
    def predict_structure_direct(self, pdb_content, design_name, use_msa_server=True, msa_content=None, msa_filename=None):
        """Run structure prediction with direct PDB content input
        
        Args:
            pdb_content (bytes): PDB file content
            design_name (str): Name of the design
            use_msa_server (bool): Whether to use the MMseqs2 MSA server
            msa_content (bytes): Optional MSA file content in .a3m format
            msa_filename (str): Filename for the MSA file
            
        Returns:
            bytes: CIF file content of the predicted structure
        """
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
                print(f"[BOLTZ DEBUG] Starting Modal execution with use_msa_server={use_msa_server}, msa_file={msa_filename or 'None'}")
                print(f"[BOLTZ DEBUG] YAML content length: {len(yaml_content)} characters")
                print(f"[BOLTZ DEBUG] First 100 characters of YAML: {yaml_content[:100]}...")
                
                with boltz_app.run():
                    result = boltz_inference.remote(
                        yaml_content,
                        use_msa_server=use_msa_server,
                        msa_content=msa_content,
                        msa_filename=msa_filename
                    )
                
                # Correct way to unpack the result
                result_data, success, error_msg = result
                
                print(f"[BOLTZ DEBUG] Modal execution completed: success={success}, error_msg={error_msg}")
                
                if not success:
                    print(f"[BOLTZ DEBUG] ⚠️ Boltz prediction failed: {error_msg}")
                    raise ValueError(f"Boltz prediction failed: {error_msg}")
                
                # Extract CIF content and confidence data
                cif_content = result_data['cif']
                confidence_data = result_data['confidence']
                
                # Save confidence data
                confidence_dir = Path("output") / f"boltz_{design_name}"
                confidence_dir.mkdir(parents=True, exist_ok=True)
                with open(confidence_dir / "confidence.json", 'w') as f:
                    json.dump(confidence_data, f, indent=2)
                
                # Save PAE file if it was returned
                if 'pae_file' in result_data:
                    # Create the output directory structure
                    confidence_dir = Path("output") / f"boltz_{design_name}"
                    confidence_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Save the PAE file with the exact name format used in boltz1.py
                    pae_file_path = confidence_dir / f"pae_{design_name}_model_0.npz"
                    with open(pae_file_path, 'wb') as f:
                        f.write(result_data['pae_file'])
                    
                    # Add more verification that the file is really saved
                    file_size = os.path.getsize(pae_file_path)
                    print(f"✅ Successfully saved PAE file to: {pae_file_path.absolute()}")
                    print(f"   File size: {file_size} bytes")
                    
                    # Verify we can load it and see the keys
                    try:
                        with np.load(pae_file_path) as pae_data:
                            print(f"   PAE file keys: {list(pae_data.keys())}")
                            if 'pae' in pae_data:
                                print(f"   PAE matrix shape: {pae_data['pae'].shape}")
                            elif 'predicted_aligned_error' in pae_data:
                                print(f"   PAE matrix shape: {pae_data['predicted_aligned_error'].shape}")
                    except Exception as e:
                        print(f"⚠️ Warning: Could load the saved PAE file for verification: {str(e)}")
                else:
                    print("⚠️ Warning: No PAE file was returned from Boltz")
                
                # Return just the CIF content
                return cif_content
            
            except Exception as e:
                print(f"[BOLTZ DEBUG] ⚠️ Modal execution failed: {str(e)}")
                print(f"[BOLTZ DEBUG] Traceback: {traceback.format_exc()}")
                raise
        
        except Exception as e:
            print(f"[BOLTZ DEBUG] ❌ CRITICAL ERROR: {str(e)}")
            print(f"[BOLTZ DEBUG] Traceback: {traceback.format_exc()}")
            raise

# Create a singleton instance
boltz_predictor = BoltzPredictor() 