from pathlib import Path
import sys
from streamlit_app.utils.boltz_predictor import extract_sequences_from_pdb, create_yaml_input

# Test paths
run_id = "2501290927"
design_name = "6x18_l82_s426888_mpnn20_model2"
pdb_path = Path("bindcraft") / run_id / "Accepted" / f"{design_name}.pdb"
stats_file = Path("bindcraft") / run_id / "final_design_stats.csv"

# Test sequence extraction
print("Testing sequence extraction from PDB...")
sequences = extract_sequences_from_pdb(str(pdb_path))
print("Found sequences:")
for chain_id, seq in sequences.items():
    print(f"Chain {chain_id}: {seq[:50]}...")  # Print first 50 residues

# Get binder sequence from stats
import pandas as pd
df = pd.read_csv(stats_file)
binder_sequence = df.iloc[0]['Sequence']
print("\nBinder sequence from stats:")
print(binder_sequence)

# Test YAML creation
print("\nCreating YAML file...")
yaml_path = create_yaml_input(str(pdb_path), binder_sequence)
print(f"Created YAML file at: {yaml_path}")

# Print YAML contents
print("\nYAML contents:")
with open(yaml_path) as f:
    print(f.read()) 