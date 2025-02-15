from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def get_bindcraft_runs(base_path):
    """Get all available BindCraft run directories"""
    base_path = Path(base_path)
    if not base_path.exists():
        return []
    
    # Look for directories containing final_design_stats.csv
    run_dirs = []
    for dir_path in base_path.iterdir():
        if dir_path.is_dir() and (dir_path / 'final_design_stats.csv').exists():
            run_dirs.append(dir_path)
    
    # Sort by creation time, newest first
    run_dirs.sort(key=lambda x: x.stat().st_ctime, reverse=True)
    return run_dirs

def load_binder_designs(run_id: str):
    """Load binder designs from a specific run"""
    run_dir = Path("bindcraft") / run_id
    stats_file = run_dir / "final_design_stats.csv"
    
    # Load sequences from stats file
    df = pd.read_csv(stats_file)
    sequences = df['Sequence'].tolist()
    
    # Get all PDB files in the Accepted directory
    pdb_files = list((run_dir / "Accepted").glob("*.pdb"))
    designs = []
    
    for idx, pdb_file in enumerate(pdb_files):
        design_name = pdb_file.stem
        designs.append({
            'run_id': run_id,
            'design_name': design_name,
            'pdb_path': str(pdb_file),
            'sequence': sequences[idx],  # Use actual sequence from CSV
            'score': df.iloc[idx]['MPNN_score'] if 'MPNN_score' in df.columns else f"Score {idx+1}"
        })
    
    return designs

def binder_gallery_page():
    st.title("Binder Gallery")
    
    # For testing, hardcode the run ID
    run_id = "2501290927"
    
    try:
        designs = load_binder_designs(run_id)
        
        if not designs:
            st.error(f"No PDB files found in bindcraft/{run_id}/Accepted")
            return
        
        # Display designs in a grid
        cols = st.columns(3)
        for i, design in enumerate(designs):
            with cols[i % 3]:
                st.write(f"Design: {design['design_name']}")
                st.write(f"PDB: {Path(design['pdb_path']).name}")
                
                if st.button(f"Select Design", key=f"select_{i}"):
                    st.session_state.selected_binder = design
                    st.switch_page("pages/03_structure_prediction.py")
    
    except Exception as e:
        st.error(f"Error loading designs: {str(e)}")

if __name__ == "__main__":
    binder_gallery_page() 