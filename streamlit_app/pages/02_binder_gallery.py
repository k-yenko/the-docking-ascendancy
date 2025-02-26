import streamlit as st
from pathlib import Path
import pandas as pd
import sys
import io

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def load_target_designs(output_dir: str):
    """Load all designs from an existing BindCraft output directory
    
    Args:
        output_dir: Path to BindCraft output directory
        
    Returns:
        Dictionary of target designs
    """
    designs_by_target = {}
    
    # Convert to Path
    output_path = Path(output_dir)
    
    # Find the stats CSV file
    stats_file = output_path / "final_design_stats.csv"
    if not stats_file.exists():
        st.warning(f"No stats file found at {stats_file}")
        return {}
    
    # Load dataframe from CSV
    df = pd.read_csv(stats_file)
    
    # Debug info
    st.write("Available columns in CSV:", df.columns.tolist())
    st.write("First few rows of CSV:", df.head())
    
    # Find PDB files in the Accepted directory
    accepted_dir = output_path / "Accepted"
    if not accepted_dir.exists():
        st.warning(f"No Accepted directory found at {accepted_dir}")
        return {}
        
    pdb_files = list(accepted_dir.glob("*.pdb"))
    st.write(f"Found {len(pdb_files)} PDB files:", [f.name for f in pdb_files])
    
    # Process each PDB file
    for pdb_file in pdb_files:
        design_name = pdb_file.stem
        st.write(f"Processing design: {design_name}")
        
        # Load PDB content
        pdb_content = pdb_file.read_bytes()
        
        # Extract target name from design name
        target_name = design_name.split('_')[0]
        
        # Try different name formats to find a match in the CSV
        # First try exact match
        matching_designs = df[df['Design'] == design_name]
        
        # If no match, try without model suffix
        if matching_designs.empty:
            base_name = design_name.rsplit('_model', 1)[0]
            matching_designs = df[df['Design'] == base_name]
            
        # If still no match, try using the base name
        if matching_designs.empty:
            st.warning(f"No matching design found in CSV for {design_name}")
            # Create minimal design info
            design_info = {
                'design_name': design_name,
                'pdb_content': pdb_content,
                'pdb_path': str(pdb_file),
                'full_path': str(project_root / "out" / "bindcraft" / "2502221700" / "Accepted" / f"{design_name}.pdb"),
                'sequence': "Sequence not available",
                'score': "N/A"
            }
        else:
            design_stats = matching_designs.iloc[0]
            design_info = {
                'design_name': design_name,
                'pdb_content': pdb_content,
                'pdb_path': str(pdb_file),
                'full_path': str(project_root / "out" / "bindcraft" / "2502221700" / "Accepted" / f"{design_name}.pdb"),
                'sequence': design_stats.get('Sequence', 'N/A'),
                'score': design_stats.get('MPNN_score', 'N/A'),
                'interface_score': design_stats.get('Interface_Score', 'N/A'),
                'plddt': design_stats.get('pLDDT', 'N/A'),
                'ptm': design_stats.get('pTM', 'N/A')
            }
            
        if target_name not in designs_by_target:
            designs_by_target[target_name] = []
        designs_by_target[target_name].append(design_info)
    
    return designs_by_target

def process_bindcraft_results(results):
    """Process BindCraft results stored in session state
    
    Args:
        results: List of (path, content) tuples from BindCraft
        
    Returns:
        Dictionary of target designs
    """
    designs_by_target = {}
    
    # Add more debugging to see what's in the results
    st.write(f"Total files in results: {len(results)}")
    for i, (path, _) in enumerate(results[:5]):  # Show first 5 files
        st.write(f"File {i}: {path}")
    
    # Find CSV files in results
    stats_files = [r for r in results if 'final_design_stats.csv' in str(r[0])]
    
    # More flexible filtering for PDB files in Accepted directory
    pdb_files = []
    for path, content in results:
        path_str = str(path)
        if path_str.endswith('.pdb') and ('Accepted' in path_str or 'accepted' in path_str.lower()):
            pdb_files.append((path, content))
    
    if not stats_files:
        st.warning("No design stats found in results")
        return {}
        
    # Use the first stats file found
    stats_file = stats_files[0]
    
    # Load dataframe from CSV content
    csv_content = io.StringIO(stats_file[1].decode('utf-8'))
    df = pd.read_csv(csv_content)
    
    # Only show number of accepted PDB files
    st.write(f"Found {len(pdb_files)} accepted PDB files")
    
    # Process each PDB file
    for pdb_path, pdb_content in pdb_files:
        design_name = pdb_path.stem
        
        # Extract target name from design name
        target_name = design_name.split('_')[0]
        
        # Try different name formats to find a match in the CSV
        # First try exact match
        matching_designs = df[df['Design'] == design_name]
        
        # If no match, try without model suffix
        if matching_designs.empty:
            base_name = design_name.rsplit('_model', 1)[0]
            matching_designs = df[df['Design'] == base_name]
            
        # If still no match, try using the base name
        if matching_designs.empty:
            # Create minimal design info
            design_info = {
                'design_name': design_name,
                'pdb_content': pdb_content,
                'pdb_path': str(pdb_path),
                'full_path': str(project_root / "out" / "bindcraft" / "2502221700" / "Accepted" / f"{design_name}.pdb"),
                'sequence': "Sequence not available",
                'score': "N/A"
            }
        else:
            design_stats = matching_designs.iloc[0]
            design_info = {
                'design_name': design_name,
                'pdb_content': pdb_content,
                'pdb_path': str(pdb_path),
                'full_path': str(project_root / "out" / "bindcraft" / "2502221700" / "Accepted" / f"{design_name}.pdb"),
                'sequence': design_stats.get('Sequence', 'N/A'),
                'score': design_stats.get('MPNN_score', 'N/A'),
                'interface_score': design_stats.get('Interface_Score', 'N/A'),
                'plddt': design_stats.get('pLDDT', 'N/A'),
                'ptm': design_stats.get('pTM', 'N/A')
            }
            
        if target_name not in designs_by_target:
            designs_by_target[target_name] = []
        designs_by_target[target_name].append(design_info)
    
    return designs_by_target

def binder_gallery_page():
    # Handle navigation FIRST, before any UI elements
    if 'navigate_to' in st.session_state:
        navigate_to = st.session_state.navigate_to
        del st.session_state.navigate_to
        st.switch_page(navigate_to)
    
    st.title("Step 2: Binder Gallery")
    
    # Add back button to navigation area
    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("← Back"):
            st.session_state.navigate_to = "pages/01_protein_input.py"
            st.rerun()
    
    # Check if we have results from BindCraft
    if 'bindcraft_results' not in st.session_state:
        st.info("No BindCraft results available. Please run BindCraft design first.")
        if st.button("Go to Protein Input"):
            st.switch_page("pages/01_protein_input.py")
        return
        
    # Process results from BindCraft
    results = st.session_state.bindcraft_results
    designs_by_target = process_bindcraft_results(results)
    
    if not designs_by_target:
        st.error("No valid designs found in BindCraft results")
        return
    
    # Target selection
    target_names = list(designs_by_target.keys())
    selected_target = st.selectbox("Select Target", target_names)
    
    if selected_target:
        st.subheader(f"Binder Designs for {selected_target}")
        
        # Create columns for the design cards
        col1, col2, col3 = st.columns(3)
        columns = [col1, col2, col3]
        
        # Display designs for selected target
        target_designs = designs_by_target[selected_target]
        for i, design in enumerate(target_designs):
            with columns[i % 3]:
                # Create a card-like display for each design
                st.markdown("---")
                st.write(f"**Design**: {design['design_name']}")
                st.write(f"**Score**: {design.get('score', 'N/A')}")
                
                if 'interface_score' in design:
                    st.write(f"**Interface Score**: {design['interface_score']}")
                if 'plddt' in design:
                    st.write(f"**pLDDT**: {design['plddt']}")
                if 'ptm' in design:
                    st.write(f"**pTM**: {design['ptm']}")
                
                # Add a small sequence preview
                seq = design.get('sequence', 'Sequence not available')
                seq_preview = seq[:20] + "..." if len(seq) > 20 else seq
                st.write(f"**Sequence**: {seq_preview}")
                
                # Select button
                if st.button(f"Select Design", key=f"select_{design['design_name']}"):
                    st.session_state.selected_binder = design
                    st.switch_page("pages/03_structure_prediction.py")

if __name__ == "__main__":
    binder_gallery_page()