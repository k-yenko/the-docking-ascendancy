import re
from typing import Dict, List, Tuple
from Bio import PDB
from Bio.PDB.Polypeptide import protein_letters_3to1
import yaml

def convert_pdb_to_yaml(pdb_path: str, output_path: str):
    """
    Convert PDB file to YAML format with specified structure.
    
    Args:
        pdb_path (str): Path to input PDB file
        output_path (str): Path to output YAML file
    """
    # Parse PDB file
    parser = PDB.PDBParser(QUIET=True)
    structure = parser.get_structure('structure', pdb_path)
    
    # Initialize yaml dictionary
    yaml_dict = {
        'version': 1,
        'sequences': []
    }
    
    # Process each chain
    for chain in structure.get_chains():
        # Determine if chain is protein or ligand
        residues = list(chain.get_residues())
        is_protein = all(res.get_resname() in PDB.Polypeptide.standard_aa_names for res in residues)
        
        if is_protein:
            # Process protein chain
            sequence = ''
            for residue in residues:
                try:
                    one_letter = protein_letters_3to1[residue.get_resname()]
                    sequence += one_letter
                except KeyError:
                    continue
                    
            chain_dict = {
                'protein': {
                    'id': chain.id,
                    'sequence': sequence
                }
            }
        else:
            # For non-protein chains (assumed to be ligands)
            chain_dict = {
                'ligand': {
                    'id': chain.id,
                    'smiles': ''  # Placeholder
                }
            }
        
        yaml_dict['sequences'].append(chain_dict)
    
    # Write YAML file
    with open(output_path, 'w') as f:
        yaml.dump(yaml_dict, f, default_flow_style=False, sort_keys=False)

pdb_path = "bindcraft/2501290927/Accepted/6x18_l82_s426888_mpnn20_model2.pdb"
output_path = "output.yaml"
convert_pdb_to_yaml(pdb_path, output_path)