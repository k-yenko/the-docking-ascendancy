import streamlit as st
from pathlib import Path
import sys
from streamlit_app.utils.boltz_predictor import predictor as boltz_predictor
from streamlit_app.utils.chai1_predictor import predictor as chai1_predictor
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def structure_prediction_page():
    # Handle navigation FIRST, before any UI elements
    if 'navigate_to' in st.session_state:
        navigate_to = st.session_state.navigate_to
        del st.session_state.navigate_to
        st.switch_page(navigate_to)
    
    st.title("Step 3: Structure Prediction")

    if 'selected_binder' not in st.session_state:     
        st.error("Please select a binder design first")
        st.switch_page("pages/02_binder_gallery.py")
        return

    # Add back button to navigation area
    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("← Back"):
            st.session_state.navigate_to = "pages/02_binder_gallery.py"
            st.rerun()

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
            st.write(f"Running predictions for design: {st.session_state.selected_binder['design_name']}")
            
            run_id = st.session_state.selected_binder.get('run_id', '')
            design_name = st.session_state.selected_binder.get('design_name', '')
            
            # Clear previous prediction history
            st.session_state.prediction_history = {}
            
            # Run predictions for each selected method
            for method in selected_methods:
                if method == "Boltz-1":
                    st.write("Running Boltz-1 prediction...")
                    try:
                        # Call predict_structure without run_id and design_name parameters
                        cif_content = boltz_predictor.predict_structure(None, None)
                        
                        # Store in session state
                        if 'prediction_history' not in st.session_state:
                            st.session_state.prediction_history = {}
                            
                        prediction_id = f"boltz1_{design_name}"
                        st.session_state.prediction_history[prediction_id] = {
                            'timestamp': datetime.now().isoformat(),
                            'method': 'Boltz-1',
                            'design_name': design_name,
                            'cif_content': cif_content
                        }
                        
                        st.success(f"Boltz-1 prediction complete for {design_name}")
                    except Exception as e:
                        st.error(f"Error in Boltz-1 prediction: {str(e)}")
                
                elif method == "Chai-1":
                    st.write("Running Chai-1 prediction...")
                    try:
                        # Call predict_structure without run_id and design_name parameters
                        cif_content = chai1_predictor.predict_structure(None, None)
                        
                        # Store in session state
                        if 'prediction_history' not in st.session_state:
                            st.session_state.prediction_history = {}
                            
                        prediction_id = f"chai1_{design_name}"
                        st.session_state.prediction_history[prediction_id] = {
                            'timestamp': datetime.now().isoformat(),
                            'method': 'Chai-1',
                            'design_name': design_name,
                            'cif_content': cif_content
                        }
                        
                        st.success(f"Chai-1 prediction complete for {design_name}")
                    except Exception as e:
                        st.error(f"Error in Chai-1 prediction: {str(e)}")
            
            if st.session_state.prediction_history:
                st.success("All selected predictions completed!")
                st.switch_page("pages/04_results_dashboard.py")
                
        except Exception as e:
            st.error(f"Error in prediction: {str(e)}")
            raise

if __name__ == "__main__":
    structure_prediction_page() 