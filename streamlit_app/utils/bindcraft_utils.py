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