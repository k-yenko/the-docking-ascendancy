"""
Common utilities shared across components
"""
from Bio.PDB import PDBParser, is_aa
from Bio.PDB.Polypeptide import protein_letters_3to1
from pathlib import Path

# For storing the latest YAML content for the UI
latest_yaml_content = ""

def extract_sequences_from_pdb(pdb_path):
    """Extract amino acid sequences from PDB file by chain"""
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure('structure', pdb_path)
    
    sequences = {}
    for model in structure:
        for chain in model:
            chain_id = chain.get_id()
            sequence = ""
            for residue in chain:
                if is_aa(residue):
                    try:
                        three_letter = residue.get_resname()
                        one_letter = protein_letters_3to1.get(three_letter, 'X')
                        sequence += one_letter
                    except:
                        sequence += 'X'
            if sequence:  # Only add non-empty sequences
                sequences[chain_id] = sequence
    
    return sequences

def extract_sequence_from_structure(structure):
    """Extract sequence from a Bio.PDB Structure object"""
    sequence = ""
    for model in structure:
        for chain in model:
            for residue in chain:
                if is_aa(residue):
                    try:
                        three_letter = residue.get_resname()
                        one_letter = protein_letters_3to1.get(three_letter, 'X')
                        sequence += one_letter
                    except:
                        sequence += 'X'
    return sequence 