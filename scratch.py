# Analyzing sequences from BindCraft output

# From the CSV file, we have the BINDER sequence:
binder_sequence = "GMSPLEQYRSQIRFFIQFAIFAILDESPWLPMHVQFAVEELERMRREFGEDEAPDPEPLKRYEELSSVELYGILKEYLEYFS"
# Length: 82 residues
# This is the designed sequence that should bind to target protein 6x18

# The TARGET protein sequence (from 6x18) is not in the CSV
# We would need to extract it from the PDB file in bindcraft/2501290927/Accepted/6x18_l82_s426888_mpnn20_model2.pdb
# The target would typically be chain A in the PDB file

# We can verify this by:
# 1. The sequence length matches the 'Length' column (82)
# 2. The interface residues (B1,B2,...) are on chain B, which is the binder chain
# 3. The design name indicates this binds to target "6x18"

# Looking at the CSV, this appears to be a protein-protein design (not a protein-ligand design)
# as there's no SMILES string or ligand information. Instead, we have:
# - A binder protein sequence (82 residues)
# - A target protein (6x18) 