import streamlit as st
from pathlib import Path
import sys
from streamlit_app.utils.boltz_predictor import predictor as boltz_predictor
from streamlit_app.utils.chai1_predictor import predictor as chai1_predictor
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def structure_prediction_page():
    st.title("Step 3: Structure Prediction")

    if 'selected_binder' not in st.session_state:     
        st.error("Please select a binder design first")
        st.switch_page("pages/02_binder_gallery.py")
        return

    # Display selected binder info
    st.subheader("Selected Binder Design")
    binder = st.session_state.selected_binder
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("Preview:")
        # Add structure preview here
    with col2:
        st.write("Sequence:", binder.get('sequence', 'N/A'))
        st.write("Score:", binder.get('score', 'N/A'))

    # Prediction method selection
    st.subheader("Select Prediction Methods")
    
    selected_methods = []
    
    # Create checkboxes for each method
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.checkbox('Boltz-1'):
            selected_methods.append("Boltz-1")
    with col2:
        if st.checkbox('Chai-1'):
            selected_methods.append("Chai-1")
    with col3:
        st.checkbox('AlphaFold3', disabled=True, help="Coming soon!")

    if not selected_methods:
        st.warning("Please select at least one prediction method")
        return

    if st.button("Run Selected Predictions"):
        try:
            results = {}
            st.write("Selected binder:", st.session_state.selected_binder)
            run_id = st.session_state.selected_binder.get('run_id', '')
            design_name = st.session_state.selected_binder.get('design_name', '')
            
            # Clear previous prediction history
            st.session_state.prediction_history = {}
            
            # Run predictions for each selected method
            for method in selected_methods:
                if method == "Boltz-1":
                    with st.spinner("Running Boltz-1 prediction..."):
                        cif_content = boltz_predictor.predict_structure(run_id, design_name)
                        if cif_content:
                            prediction_id = f"{run_id}_{design_name}_boltz"
                            st.session_state.prediction_history[prediction_id] = {
                                'timestamp': datetime.now().isoformat(),
                                'method': 'Boltz-1',
                                'run_id': run_id,
                                'design_name': design_name,
                                'cif_content': cif_content
                            }
                            st.success("Boltz-1 prediction completed!")
                
                elif method == "Chai-1":
                    with st.spinner("Running Chai-1 prediction..."):
                        cif_content = chai1_predictor.predict_structure(run_id, design_name)
                        if cif_content:
                            prediction_id = f"{run_id}_{design_name}_chai1"
                            st.session_state.prediction_history[prediction_id] = {
                                'timestamp': datetime.now().isoformat(),
                                'method': 'Chai-1',
                                'run_id': run_id,
                                'design_name': design_name,
                                'cif_content': cif_content
                            }
                            st.success("Chai-1 prediction completed!")
            
            if st.session_state.prediction_history:
                st.success("All selected predictions completed!")
                st.switch_page("pages/04_results_dashboard.py")
                
        except Exception as e:
            st.error(f"Error in prediction: {str(e)}")
            raise

if __name__ == "__main__":
    structure_prediction_page() 