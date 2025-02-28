"""
Utilities specific to Boltz-1 predictor
"""
import yaml
from pathlib import Path
from streamlit_app.utils.common_utils import extract_sequences_from_pdb

# For storing the latest YAML content for the UI
latest_yaml_content = ""

def create_yaml_content(pdb_path, design_seq=None):
    """
    Create YAML content for Boltz prediction in exact format as example.yaml
    
    Args:
        pdb_path: Path to the PDB file
        design_seq: Optional design sequence from final_design_stats.csv
    """
    # Extract sequences from the PDB file
    pdb_sequences = extract_sequences_from_pdb(pdb_path)
    
    print(f"[YAML_UTILS] Extracted sequences from PDB: {pdb_sequences}")
    
    # Start building the YAML content
    yaml_content = {
        "sequences": []
    }
    
    # Add the first protein entry from PDB chains
    chain_ids = list(pdb_sequences.keys())
    combined_sequence = ""
    for chain_id in sorted(chain_ids):
        combined_sequence += pdb_sequences[chain_id]
    
    print(f"[YAML_UTILS] Combined sequence length: {len(combined_sequence)}")
    
    # Add the target protein from PDB
    yaml_content["sequences"].append({
        "protein": {
            "id": chain_ids,
            "sequence": combined_sequence
        }
    })
    
    # If we have a design sequence from CSV, add it as a second protein
    if design_seq:
        print(f"[YAML_UTILS] Adding design sequence: {design_seq}")
        yaml_content["sequences"].append({
            "protein": {
                "id": ["B"],  # Assuming the design is chain B
                "sequence": design_seq
            }
        })
    else:
        print("[YAML_UTILS] No design sequence provided")
    
    # Convert to YAML string - no sort_keys to maintain order
    yaml_string = yaml.dump(yaml_content, sort_keys=False)
    
    print(f"[YAML_UTILS] Created YAML content for {pdb_path}:\n{yaml_string}")
    
    # Store for UI access
    global latest_yaml_content
    latest_yaml_content = yaml_string
    
    return yaml_string 