import streamlit as st
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from streamlit_app.utils.prediction_utils import (
    prepare_prediction_input,
    run_chai_prediction,
    run_af3_prediction
)
from streamlit_app.utils.boltz_predictor import predict_structure

def structure_prediction_page():
    st.title("Step 3: Structure Prediction")

    if 'selected_binder' not in st.session_state:
        st.error("Please select a binder design first")
        st.button("Go back to binder selection", 
                 on_click=lambda: st.switch_page("pages/02_binder_gallery.py"))
        return

    # Display selected binder info
    st.subheader("Selected Binder Design")
    binder = st.session_state.selected_binder
    col1, col2 = st.columns([1, 2])
    with col1:
        # Display structure preview of selected binder
        st.write("Preview:")
        # Add structure preview here
    with col2:
        st.write("Sequence:", binder.get('sequence', 'N/A'))
        st.write("Score:", binder.get('score', 'N/A'))

    # Prediction method selection
    st.subheader("Select Prediction Methods")
    
    methods = {
        'Boltz-1': {
            'selected': st.checkbox('Boltz-1', value=True),
            'options': {}  # Removed MSA server option since it's always required
        },
        'Chai-1': {
            'selected': st.checkbox('ChAI-1'),
            'options': {}
        },
        'AlphaFold3': {
            'selected': st.checkbox('AlphaFold3'),
            'options': {}
        }
    }

    if st.button("Run Selected Predictions"):
        if 'prediction_results' not in st.session_state:
            st.session_state.prediction_results = {}
            
        predictions_made = False
        
        for method, config in methods.items():
            if config['selected']:
                with st.spinner(f"Running {method}..."):
                    try:
                        if method == 'Boltz-1':
                            # Get run_id and design_name from the selected binder
                            run_id = binder.get('run_id')
                            design_name = binder.get('design_name')
                            
                            if not run_id or not design_name:
                                raise ValueError("Missing run ID or design name for selected binder")
                            
                            result = predict_structure(run_id, design_name)
                            if result:
                                st.session_state.prediction_results[method] = result
                                predictions_made = True
                                st.success(f"{method} prediction completed!")
                        elif method == 'ChAI-1':
                            result = run_chai_prediction(binder)
                            if result:
                                st.session_state.prediction_results[method] = result
                                predictions_made = True
                                st.success(f"{method} prediction completed!")
                        elif method == 'AlphaFold3':
                            result = run_af3_prediction(binder)
                            if result:
                                st.session_state.prediction_results[method] = result
                                predictions_made = True
                                st.success(f"{method} prediction completed!")
                            
                    except Exception as e:
                        st.error(f"Error in {method}: {str(e)}")

        if predictions_made:
            st.button(
                "Continue to Results Dashboard",
                on_click=lambda: st.switch_page("pages/04_results_dashboard.py")
            )

if __name__ == "__main__":
    structure_prediction_page() 