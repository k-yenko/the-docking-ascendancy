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
from streamlit_app.utils.boltz_interface import predict_structure

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
    
    methods = {
        'Boltz-1': {
            'selected': st.checkbox('Boltz-1', value=True),
            'options': {}
        },
        'Chai-1': {
            'selected': st.checkbox('Chai-1'),
            'options': {}
        },
        'AlphaFold3': {
            'selected': st.checkbox('AlphaFold3'),
            'options': {}
        }
    }

    if st.button("Run Selected Predictions"):
        predictions_made = False
        
        for method, config in methods.items():
            if config['selected']:
                with st.spinner(f"Running {method}..."):
                    try:
                        if method == 'Boltz-1':
                            if run_prediction():
                                predictions_made = True
                        elif method == 'ChAI-1':
                            result = run_chai_prediction(binder)
                            if result:
                                st.session_state.prediction_results[method] = result
                                predictions_made = True
                        elif method == 'AlphaFold3':
                            result = run_af3_prediction(binder)
                            if result:
                                st.session_state.prediction_results[method] = result
                                predictions_made = True
                            
                    except Exception as e:
                        st.error(f"Error in {method}: {str(e)}")

        if predictions_made:
            st.write("Redirecting with results:", bool(st.session_state.prediction_results))
            st.success("Predictions complete! Redirecting to results...")
            st.switch_page("pages/04_results_dashboard.py")

def run_prediction():
    with st.spinner("Running Boltz-1 prediction..."):
        try:
            run_id = st.session_state.selected_binder['run_id']
            design_name = st.session_state.selected_binder['design_name']
            
            # Run prediction and store result
            result = predict_structure(run_id, design_name)
            
            if result is not None:
                # Store the result
                st.session_state["prediction_results"] = {
                    "Boltz-1": result
                }
                st.write("Stored prediction result:", bool(st.session_state.prediction_results))
                st.write("Result size:", len(result), "bytes")
                return True
            else:
                st.error("No result from prediction")
                return False
                
        except Exception as e:
            st.error(f"Error in run_prediction: {str(e)}")
            st.exception(e)
            return False

if __name__ == "__main__":
    structure_prediction_page() 