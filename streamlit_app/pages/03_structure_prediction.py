import streamlit as st
from pathlib import Path
import sys
from streamlit_app.modal_services.boltz_service import boltz_predictor
from streamlit_app.modal_services.chai_service import chai1_predictor
from streamlit_app.utils.boltz_utils import latest_yaml_content as boltz_yaml_content
from datetime import datetime
import modal
import concurrent.futures
import threading
import queue
import copy
import os
import numpy as np

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def reset_modal_state():
    """Reset the Modal client state to clear any conflicts"""
    try:
        # Force a client refresh
        modal.reset()
    except:
        pass

def run_boltz_prediction(binder_data, pdb_content, status_queue=None):
    """Run Boltz prediction in a separate thread"""
    try:
        # Don't use st.write here - not thread safe
        print("Running Boltz-1 prediction...")
        
        # Pass the PDB content directly instead of relying on session state
        design_name = binder_data['design_name']
        print(f"Starting Boltz prediction for {design_name} with PDB content of size {len(pdb_content)} bytes")
        
        # Signal that YAML generation is starting (if queue provided)
        if status_queue:
            status_queue.put(("status", "Generating YAML..."))
        
        # Get design sequence and generate YAML first
        from streamlit_app.utils.bindcraft_utils import get_design_sequence
        from streamlit_app.utils.boltz_utils import create_yaml_content
        import tempfile
        from pathlib import Path
        
        # Create temp files
        temp_dir = Path(tempfile.mkdtemp())
        temp_pdb = temp_dir / f"{design_name}.pdb"
        
        # Write the PDB content to the temp file
        with open(temp_pdb, 'wb') as f:
            f.write(pdb_content)
        
        # Get design sequence from CSV
        design_seq = get_design_sequence(design_name)
        
        # Generate YAML first and store it in a global variable
        yaml_content = create_yaml_content(str(temp_pdb), design_seq)
        
        # Signal that YAML is ready (if queue provided)
        if status_queue:
            status_queue.put(("yaml_ready", yaml_content))
            status_queue.put(("status", "Running Boltz-1 prediction..."))
        
        # Get Boltz options from session state
        boltz_options = st.session_state.get('boltz_options', {
            "use_msa_server": True
        })
        
        # Now proceed with prediction
        cif_content = boltz_predictor.predict_structure_direct(
            pdb_content, 
            design_name,
            use_msa_server=boltz_options["use_msa_server"],
            msa_content=boltz_options.get("msa_file"),
            msa_filename=boltz_options.get("msa_filename")
        )
        
        # Additional validation
        if not cif_content:
            raise ValueError("Boltz prediction returned empty result")
        
        print(f"Successfully completed Boltz prediction for {design_name}, got {len(cif_content)} bytes")
        
        # Return the result
        return {
            'success': True,
            'method': 'Boltz-1',
            'design_name': design_name,
            'cif_content': cif_content
        }
    except Exception as e:
        # Use print instead of st.error
        print(f"Error in Boltz-1 prediction: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {
            'success': False,
            'method': 'Boltz-1',
            'error': str(e)
        }

def run_chai_prediction(binder_data, pdb_content):
    """Run Chai prediction in a separate thread"""
    try:
        # Don't use st.write here - not thread safe
        print("Running Chai-1 prediction...")
        
        # Pass the PDB content directly instead of relying on session state
        design_name = binder_data['design_name']
        cif_content = chai1_predictor.predict_structure_direct(pdb_content, design_name)
        
        # Return the result
        return {
            'success': True,
            'method': 'Chai-1',
            'design_name': design_name,
            'cif_content': cif_content
        }
    except Exception as e:
        # Use print instead of st.error
        print(f"Error in Chai-1 prediction: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {
            'success': False,
            'method': 'Chai-1',
            'error': str(e)
        }

def get_latest_yaml_content():
    """Gets the latest YAML content"""
    from streamlit_app.utils.boltz_utils import latest_yaml_content
    return latest_yaml_content

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

    # Create a queue for inter-thread communication
    task_queue = queue.Queue()

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

    # Create method containers with their own options
    method_col1, method_col2 = st.columns(2)

    with method_col1:
        # Boltz-1 container with options
        boltz_container = st.container()
        with boltz_container:
            use_boltz = st.checkbox('Boltz-1', help="Boltz-1 structure prediction model")
            
            # Indented container for Boltz options
            if use_boltz:
                with st.container():
                    st.markdown("#### Boltz-1 Options")
                    st.divider()
                    
                    # MSA options
                    msa_option = st.radio(
                        "MSA Source for Boltz-1",
                        ["Auto-generate MSA", "Upload MSA File"],
                        index=0,
                        help="Multiple Sequence Alignments improve prediction accuracy"
                    )
                    
                    # Set default options
                    use_msa_server = (msa_option == "Auto-generate MSA")
                    msa_file = None
                    
                    # Show file uploader only if "Upload MSA File" is selected
                    if msa_option == "Upload MSA File":
                        msa_file = st.file_uploader("Upload MSA file (.a3m format)", type=['a3m'])
                        if msa_file:
                            # Read MSA content
                            msa_content = msa_file.read()
                            st.success(f"MSA file loaded: {msa_file.name} ({len(msa_content)} bytes)")
                        else:
                            st.warning("Please upload an .a3m MSA file")
                    
                    # Store settings in session state
                    st.session_state.boltz_options = {
                        "use_msa_server": use_msa_server,
                        "msa_file": msa_file.getvalue() if msa_option == "Upload MSA File" and 'msa_file' in locals() and msa_file else None,
                        "msa_filename": msa_file.name if msa_option == "Upload MSA File" and 'msa_file' in locals() and msa_file else None
                    }

    with method_col2:
        # Chai-1 container (with potential future options)
        chai_container = st.container()
        with chai_container:
            use_chai = st.checkbox('Chai-1', help="Chai-1 structure prediction model")
        
        # AlphaFold3 container
        af3_container = st.container()
        with af3_container:
            st.checkbox('AlphaFold3', disabled=True, help="Coming soon!")

    # Build selected_methods from the checkboxes
    selected_methods = []
    if use_boltz:
        selected_methods.append("Boltz-1")
    if use_chai:
        selected_methods.append("Chai-1")

    if not selected_methods:
        st.warning("Please select at least one prediction method")
        return

    # Create a placeholder for status updates that's updated from the main thread
    status_placeholder = st.empty()
    results_placeholder = st.empty()

    # Add YAML display section
    yaml_placeholder = st.empty()
    
    # Add this to monitor the prediction status messages
    status_update_thread = threading.Thread(
        target=monitor_prediction_status,
        args=(task_queue, status_placeholder, yaml_placeholder),
        daemon=True
    )
    status_update_thread.start()

    if st.button("Run predictions"):
        # Prepare UI elements
        status_placeholder.empty()
        with status_placeholder.container():
            st.info("Preparing predictions...")
        
        # Clear previous predictions that don't match current selection
        if 'prediction_history' in st.session_state:
            st.session_state.current_run_methods = selected_methods
            
            # Remove predictions from previous runs for methods not selected in current run
            keys_to_remove = []
            for key, value in st.session_state.prediction_history.items():
                method = value.get('method')
                if method == 'Chai-1' and 'Chai-1' not in selected_methods:
                    keys_to_remove.append(key)
                elif method == 'Boltz-1' and 'Boltz-1' not in selected_methods:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del st.session_state.prediction_history[key]
        
        # Run predictions sequentially to better handle errors
        try:
            # Get everything needed from session state once
            binder = st.session_state.selected_binder
            binder_data = copy.deepcopy(binder)  # Create a copy
            pdb_content = binder.get('pdb_content')
            
            # Debug information
            if not pdb_content:
                status_placeholder.error("No PDB content found in selected binder!")
                return
            
            # Initialize session state for prediction history if needed
            if 'prediction_history' not in st.session_state:
                st.session_state.prediction_history = {}
            
            # Run Boltz-1 prediction first if selected
            if "Boltz-1" in selected_methods:
                with status_placeholder.container():
                    st.info("Running Boltz-1 prediction...")
                
                boltz_result = run_boltz_prediction(binder_data, pdb_content, task_queue)
                
                if not boltz_result['success']:
                    status_placeholder.error(f"❌ Boltz-1 prediction failed: {boltz_result.get('error', 'Unknown error')}")
                    # Stop all predictions if Boltz fails
                    return
                else:
                    # Store successful prediction
                    prediction_id = f"boltz_{boltz_result['design_name']}"
                    st.session_state.prediction_history[prediction_id] = {
                        'timestamp': datetime.now().isoformat(),
                        'method': 'Boltz-1',
                        'design_name': boltz_result['design_name'],
                        'cif_content': boltz_result['cif_content']
                    }
                    with status_placeholder.container():
                        st.success("✅ Boltz-1 prediction completed successfully")
                    
                    # Show PAE debugging information after successful prediction
                    with st.expander("Boltz Modal Debug Output", expanded=False):
                        st.subheader("Modal Execution Logs")
                        
                        # Get the logs from Modal (if available)
                        try:
                            from modal.functions import FunctionCall
                            from modal import Client
                            
                            client = Client()
                            app = client.apps.get("boltz1-standard")
                            
                            # Try to get recent function calls
                            calls = list(app.functions["boltz_inference"].function_calls.list(limit=5))
                            
                            if calls:
                                # Show the most recent call
                                latest_call = calls[0]
                                st.write(f"Latest call ID: {latest_call.id}")
                                st.write(f"Status: {latest_call.status}")
                                
                                # Get logs
                                logs = list(latest_call.logs())
                                
                                # Display logs with PAE-related information highlighted
                                log_text = ""
                                for entry in logs:
                                    log_line = entry.data.decode('utf-8')
                                    log_text += log_line + "\n"
                                    
                                    # Highlight PAE-related lines
                                    if "pae" in log_line.lower() or "predicted_aligned_error" in log_line.lower():
                                        st.write(f"**PAE Info:** {log_line.strip()}")
                                
                                # Show full logs in a text area
                                st.text_area("Full Logs", log_text, height=300)
                            else:
                                st.warning("No recent Boltz function calls found")
                        except Exception as e:
                            st.error(f"Error fetching Modal logs: {str(e)}")
            
            # Run Chai-1 prediction if selected
            if "Chai-1" in selected_methods:
                with status_placeholder.container():
                    st.info("Running Chai-1 prediction...")
                
                chai_result = run_chai_prediction(binder_data, pdb_content)
                
                if not chai_result['success']:
                    status_placeholder.error(f"❌ Chai-1 prediction failed: {chai_result.get('error', 'Unknown error')}")
                    # Continue with other results if available
                else:
                    # Store successful prediction
                    prediction_id = f"chai_{chai_result['design_name']}"
                    st.session_state.prediction_history[prediction_id] = {
                        'timestamp': datetime.now().isoformat(),
                        'method': 'Chai-1',
                        'design_name': chai_result['design_name'],
                        'cif_content': chai_result['cif_content']
                    }
                    # Debug print to confirm
                    print(f"Stored Chai-1 prediction with ID: {prediction_id}, content size: {len(chai_result['cif_content']) if isinstance(chai_result['cif_content'], bytes) else 'unknown'}")
                    with status_placeholder.container():
                        st.success("✅ Chai-1 prediction completed successfully")
            
            # Check if we have any successful predictions
            if any(v.get('cif_content') for v in st.session_state.prediction_history.values()):
                results_placeholder.success("At least one prediction completed successfully!")
                # Navigate to results page
                st.session_state.navigate_to = "pages/04_results_dashboard.py"
                st.rerun()
            else:
                status_placeholder.error("All structure predictions failed.")
        
        except Exception as e:
            status_placeholder.error(f"Error in prediction process: {str(e)}")
            import traceback
            status_placeholder.error(f"Traceback: {traceback.format_exc()}")

    # After running a prediction and getting back the result:
    st.subheader("PAE File Status Check")
    design_name = selected_methods[0]  # Assuming the first method is selected
    expected_pae_path = f"output/boltz_{design_name}/pae_{design_name}_model_0.npz" 

    if os.path.exists(expected_pae_path):
        st.success(f"✅ PAE file found at: {expected_pae_path}")
        try:
            with np.load(expected_pae_path) as pae_data:
                st.write(f"PAE file keys: {list(pae_data.keys())}")
                if 'predicted_aligned_error' in pae_data:
                    st.write(f"PAE matrix shape: {pae_data['predicted_aligned_error'].shape}")
        except Exception as e:
            st.error(f"Error reading PAE file: {str(e)}")
    else:
        st.error(f"❌ PAE file not found at: {expected_pae_path}")
        
        # Show all files in the output directory
        output_dir = Path("output")
        if output_dir.exists():
            all_files = list(output_dir.glob("**/*.*"))
            st.write(f"Found {len(all_files)} files in output directory:")
            for file in all_files[:20]:  # Show first 20 files
                st.write(f"  - {file}")

def monitor_prediction_status(q, status_placeholder, yaml_placeholder):
    """Monitor prediction status messages from the queue"""
    while True:
        try:
            message_type, message = q.get(timeout=0.5)
            
            if message_type == "status":
                # Update status message
                status_placeholder.info(message)
            elif message_type == "yaml_ready":
                # Display YAML as soon as it's generated
                yaml_placeholder.subheader("Generated Boltz-1 YAML Input")
                yaml_placeholder.code(message)
            
            q.task_done()
        except queue.Empty:
            # No new messages, continue checking
            continue
        except Exception as e:
            print(f"Error in monitor thread: {e}")
            break

if __name__ == "__main__":
    structure_prediction_page() 