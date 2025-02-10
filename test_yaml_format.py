from pathlib import Path
import pandas as pd
import yaml
from Bio import PDB
from Bio.PDB.Polypeptide import protein_letters_3to1

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
                        three_letter = residue.get_resname()
                        one_letter = protein_letters_3to1.get(three_letter, 'X')
                        seq += one_letter
                    except:
                        seq += 'X'
            if seq:  # Only store non-empty sequences
                sequences[chain.id] = seq
    
    return sequences

def test_yaml_creation():
    # Test data
    run_id = "2501290927"
    design_name = "6x18_l82_s426888_mpnn20_model2"
    pdb_path = Path("bindcraft") / run_id / "Accepted" / f"{design_name}.pdb"
    
    # Get sequences from PDB and stats
    sequences = extract_sequences_from_pdb(str(pdb_path))
    target_sequence = sequences.get('A', '')  # Target is chain A
    
    stats_file = Path("bindcraft") / run_id / "final_design_stats.csv"
    df = pd.read_csv(stats_file)
    binder_sequence = df.iloc[0]['Sequence']
    
    # Create YAML content matching output_example.yaml exactly
    yaml_content = {
        'version': 1,
        'sequences': [
            {
                'protein': {
                    'id': 'A',  # Not a list anymore
                    'sequence': target_sequence
                }
            },
            {
                'protein': {
                    'id': 'B',  # Not a list anymore
                    'sequence': binder_sequence
                }
            }
        ]
    }
    
    # Print both for comparison
    print("\nGenerated YAML content:")
    print(yaml.dump(yaml_content, sort_keys=False, indent=2))
    
    print("\nExample YAML content:")
    with open('output_example.yaml', 'r') as f:
        print(f.read())
    
    # Write to file for inspection
    test_yaml_path = Path("test_input.yaml")
    with open(test_yaml_path, 'w') as f:
        yaml.dump(yaml_content, f, sort_keys=False, indent=2)  # Added indent=2
    
    print(f"\nWrote YAML to: {test_yaml_path}")
    
    return yaml_content

if __name__ == "__main__":
    test_yaml_creation() 