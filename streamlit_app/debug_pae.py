"""
Debug script to find and analyze PAE data from Boltz predictions
"""
import os
import glob
import json
import numpy as np
from pathlib import Path

def find_pae_files():
    """Find all PAE files in the output directory"""
    print("Searching for PAE files...")
    
    # Try different patterns
    pae_files = []
    for pattern in [
        "output/**/pae_*.npz",
        "output/boltz_*/pae_*.npz",
        "output/*_model_*.npz"
    ]:
        found = glob.glob(pattern, recursive=True)
        pae_files.extend(found)
        if found:
            print(f"  Found {len(found)} files with pattern {pattern}")
    
    if not pae_files:
        print("No PAE files found!")
        return
    
    print(f"Found {len(pae_files)} PAE files:")
    for pae_file in pae_files:
        file_size = os.path.getsize(pae_file) / 1024  # KB
        print(f"  {pae_file} ({file_size:.2f} KB)")
        
        # Examine file contents
        try:
            data = np.load(pae_file)
            print(f"    Keys: {list(data.keys())}")
            
            # Look for PAE matrix
            if 'predicted_aligned_error' in data:
                pae = data['predicted_aligned_error']
                print(f"    PAE matrix shape: {pae.shape}")
                print(f"    PAE range: {np.min(pae):.2f} to {np.max(pae):.2f}")
                print(f"    PAE mean: {np.mean(pae):.2f}")
                # Save sample for inspection
                sample_path = f"{pae_file}.sample.txt"
                with open(sample_path, 'w') as f:
                    f.write(f"Shape: {pae.shape}\n")
                    f.write(f"Min: {np.min(pae)}, Max: {np.max(pae)}, Mean: {np.mean(pae)}\n\n")
                    f.write("First 10x10 elements:\n")
                    sample = pae[:10, :10]
                    for row in sample:
                        f.write(" ".join([f"{x:.2f}" for x in row[:10]]) + "\n")
                print(f"    Saved sample to {sample_path}")
            else:
                print("    No 'predicted_aligned_error' key found!")
        except Exception as e:
            print(f"    Error examining file: {str(e)}")
    
    # Also examine confidence files
    print("\nSearching for confidence files...")
    confidence_files = glob.glob("output/**/confidence*.json", recursive=True)
    print(f"Found {len(confidence_files)} confidence files:")
    
    for conf_file in confidence_files:
        print(f"  {conf_file}")
        try:
            with open(conf_file, 'r') as f:
                data = json.load(f)
            
            # Check for PAE in confidence file
            if 'pae' in data:
                pae = np.array(data['pae'])
                print(f"    Contains PAE data with shape {pae.shape}")
            elif 'predicted_aligned_error' in data:
                pae = np.array(data['predicted_aligned_error'])
                print(f"    Contains PAE data with shape {pae.shape}")
            else:
                print("    No PAE data found in confidence file")
                # Print keys
                print(f"    Available keys: {list(data.keys())}")
        except Exception as e:
            print(f"    Error examining file: {str(e)}")

def check_dashboard_pae_detection():
    """Simulate the PAE detection logic in the dashboard"""
    from streamlit_app.utils.structure_metrics import extract_confidence_metrics
    
    print("\nTesting dashboard PAE detection logic...")
    
    # Try for a few designs
    designs = [d.name for d in Path("output").glob("boltz_*") if d.is_dir()]
    if not designs:
        print("No boltz output directories found")
        return
    
    for design in designs:
        design = design.replace("boltz_", "")
        print(f"\nChecking PAE detection for design: {design}")
        
        # Call the same function the dashboard uses
        confidence_data = extract_confidence_metrics(design, "Boltz-1")
        
        # Check for PAE
        if 'pae' in confidence_data:
            pae = np.array(confidence_data['pae'])
            print(f"  PAE data found with shape {pae.shape}")
            print(f"  PAE range: {np.min(pae):.2f} to {np.max(pae):.2f}")
            
            # Check if it would be detected as example data
            if pae.shape[0] == 50 or (pae.shape[0] == 100 and np.mean(pae) > 10):
                print("  ❌ Would be detected as EXAMPLE data")
                
                # Try to determine why
                if pae.shape[0] == 50:
                    print("    Reason: Shape is 50x50 (example data has this shape)")
                elif pae.shape[0] == 100 and np.mean(pae) > 10:
                    print(f"    Reason: Shape is 100x100 and mean value ({np.mean(pae):.2f}) is >10")
                    print(f"    This matches our example data pattern")
            else:
                print("  ✅ Would be detected as REAL data")
        else:
            print("  ❌ No PAE data found")
    
    print("\nSuggested fixes:")
    print("1. In 04_results_dashboard.py, update the detection logic:")
    print("   Remove the condition 'pae_data.shape[0] == 100 and np.mean(pae_data) > 10'")
    print("2. In structure_metrics.py, make the example data shape 50x50 only")
    print("   to avoid confusion with real 100x100 data")

if __name__ == "__main__":
    find_pae_files()
    check_dashboard_pae_detection() 