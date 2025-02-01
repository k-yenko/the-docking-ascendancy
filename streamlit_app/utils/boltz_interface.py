import streamlit as st
import pandas as pd
import yaml
from pathlib import Path
from Bio import PDB
from Bio.PDB.Polypeptide import protein_letters_3to1
from .boltz_predictor import app, boltz1_inference

def extract_sequences_from_pdb(pdb_path: str):
    """Extract sequences from PDB file"""
    parser = PDB.PDBParser(QUIET=True)
    structure = parser.get_structure('structure', pdb_path)
    
    sequences = {}
    for model in structure:
        for chain in model:
            seq = ""
            for residue in chain:
                if PDB.is_aa(residue):
                    try:
                        # Convert three letter code to one letter code
                        three_letter = residue.get_resname()
                        one_letter = protein_letters_3to1.get(three_letter, 'X')
                        seq += one_letter
                    except:
                        seq += 'X'
            if seq:  # Only store non-empty sequences
                sequences[chain.id] = seq
    
    return sequences

def create_yaml_content(pdb_path: str) -> str:
    """Create YAML content for Boltz prediction - runs locally"""
    # Extract sequences from PDB
    sequences = extract_sequences_from_pdb(pdb_path)
    
    # In PDB, typically:
    # Chain A is the target protein
    # Chain B is the binder
    target_sequence = sequences.get('A', '')
    binder_sequence = sequences.get('B', '')
    
    if not target_sequence or not binder_sequence:
        raise ValueError("Could not extract both sequences from PDB")
    
    yaml_content = {
        "version": 1,
        "sequences": [
            {
                "protein": {
                    "id": ["A"],
                    "sequence": target_sequence,
                    "name": "target"
                }
            },
            {
                "protein": {
                    "id": ["B"],
                    "sequence": binder_sequence,
                    "name": "binder"
                }
            }
        ]
    }
    
    return yaml.dump(yaml_content, sort_keys=False)

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