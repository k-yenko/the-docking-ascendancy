"""
Utilities for working with BindCraft designs
"""
import pandas as pd
import os
from pathlib import Path

project_root = Path(__file__).parent.parent.parent

def get_design_sequence(design_name):
    """Get the sequence for a design from the CSV file"""
    try:
        csv_path = project_root / "out" / "bindcraft" / "2502221700" / "final_design_stats.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            design_row = df[df['Design'] == design_name]
            if not design_row.empty:
                design_seq = design_row['Sequence'].iloc[0]
                print(f"Found design sequence: {design_seq}")
                return design_seq
    except Exception as e:
        print(f"Error getting design sequence: {e}")
    
    return None

def validate_sequence(sequence: str) -> bool:
    """Validate protein sequence."""
    valid_residues = set("ACDEFGHIKLMNPQRSTVWY")
    sequence = sequence.upper().strip()
    return all(aa in valid_residues for aa in sequence)

def run_bindcraft(sequence: str) -> list:
    """Run BindCraft prediction."""
    # Implement BindCraft execution here
    # This should interface with your existing BindCraft implementation
    pass 

def get_bindcraft_output_dir():
    """Get the path to the BindCraft output directory"""
    return project_root / "out" / "bindcraft" / "2502221700" 