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
            use_msa_server=boltz_options["use_msa_server"]
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
        # Clear previous predictions that don't match current selection
        if 'prediction_history' in st.session_state:
            # Keep track of which methods were selected in this run
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

        # Create log container
        debug_log = st.expander("Debug Logs", expanded=False)
        debug_log.info("Starting debug logs...")
        
        try:
            # Log the session state for debugging
            debug_log.code(f"Session state keys: {list(st.session_state.keys())}")
            debug_log.code(f"Selected methods: {selected_methods}")
            
            # Reset modal state before starting predictions
            reset_modal_state()
            
            # Get everything needed from session state once
            binder = st.session_state.selected_binder
            binder_data = copy.deepcopy(binder)  # Create a copy to avoid thread issues
            pdb_content = binder.get('pdb_content')
            
            # Debug information
            status_placeholder.info(f"Preparing prediction for {binder_data['design_name']} with PDB content size: {len(pdb_content)} bytes")
            print(f"Selected binder data: {binder_data.keys()}")
            print(f"PDB content size: {len(pdb_content)} bytes")
            
            if not pdb_content:
                status_placeholder.error("No PDB content found in selected binder!")
                return
            
            # Create tasks
            tasks = []
            if "Boltz-1" in selected_methods:
                status_placeholder.info("Adding Boltz-1 prediction task")
                debug_log.info("Boltz-1 prediction details will appear here after execution")
                tasks.append(('boltz', run_boltz_prediction, binder_data, pdb_content, task_queue))
            if "Chai-1" in selected_methods:
                status_placeholder.info("Adding Chai-1 prediction task")
                tasks.append(('chai', run_chai_prediction, binder_data, pdb_content))
            
            # Initialize status message
            status_placeholder.info("Starting predictions...")
            
            # Initialize session state for prediction history if needed
            if 'prediction_history' not in st.session_state:
                st.session_state.prediction_history = {}
            
            # Track progress in the main thread
            completed_tasks = []
            
            # When setting up prediction tasks, save the selected methods
            st.session_state.selected_methods = selected_methods
            
            # Run predictions in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                # Submit all tasks with the additional arguments
                future_to_task = {}
                for task_id, task_func, *args in tasks:
                    if task_id == 'boltz':
                        # Boltz task with queue
                        future = executor.submit(task_func, *args)
                    else:
                        # Other tasks without queue
                        future = executor.submit(task_func, args[0], args[1]) 
                    future_to_task[future] = (task_id, task_func)
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_task):
                    task_id, task_func = future_to_task[future]
                    try:
                        result = future.result()
                        method = result.get('method', task_id)
                        
                        # Update the status from the main thread
                        if result['success']:
                            design_name = result['design_name']
                            
                            # Store successful prediction
                            prediction_id = f"{task_id}_{design_name}"
                            st.session_state.prediction_history[prediction_id] = {
                                'timestamp': datetime.now().isoformat(),
                                'method': method,
                                'design_name': design_name,
                                'cif_content': result['cif_content']
                            }
                            
                            # Add to completed tasks
                            completed_tasks.append(f"{method} prediction complete for {design_name}")
                            
                            # Update status message
                            status_text = "\n".join(completed_tasks)
                            status_placeholder.success(status_text)
                        else:
                            error_msg = result.get('error', 'Unknown error')
                            # Make errors more prominent
                            status_placeholder.error(f"Error in {method} prediction: {error_msg}")
                            # Log the error for debugging
                            print(f"PREDICTION ERROR for {method}: {error_msg}")
                    except Exception as e:
                        status_placeholder.error(f"Error processing {task_id} result: {str(e)}")
                        import traceback
                        traceback_text = traceback.format_exc()
                        print(f"EXCEPTION in {task_id}: {traceback_text}")
                        status_placeholder.error(f"Stack trace: {traceback_text}")
            
            # At the end of your prediction processing
            if st.session_state.prediction_history:
                # Only navigate if we have SUCCESSFUL predictions
                has_successful_boltz = any(
                    v['method'] == 'Boltz-1' and v.get('cif_content') 
                    for k, v in st.session_state.prediction_history.items() 
                    if k.startswith('boltz_')
                )
                
                has_successful_chai = any(
                    v['method'] == 'Chai-1' and v.get('cif_content')
                    for k, v in st.session_state.prediction_history.items()
                    if k.startswith('chai_')
                )
                
                # Only navigate if we have the methods we requested
                should_navigate = True
                if "Boltz-1" in selected_methods and not has_successful_boltz:
                    status_placeholder.warning("Waiting for Boltz-1 prediction to complete...")
                    should_navigate = False
                    
                if "Chai-1" in selected_methods and not has_successful_chai:
                    status_placeholder.warning("Waiting for Chai-1 prediction to complete...")
                    should_navigate = False
                
                if should_navigate:
                    results_placeholder.success("All selected predictions completed!")
                    # Use session state to trigger navigation on next rerun
                    st.session_state.navigate_to = "pages/04_results_dashboard.py"
                    st.rerun()
                
            # After predictions complete, log results
            debug_log.info("Prediction summary:")
            if 'prediction_history' in st.session_state:
                for key, value in st.session_state.prediction_history.items():
                    debug_log.code(f"Prediction: {key}\n" + 
                                  f"  Method: {value.get('method')}\n" +
                                  f"  Design: {value.get('design_name')}\n" +
                                  f"  Success: {'Yes' if 'cif_content' in value and value['cif_content'] else 'No'}\n" +
                                  f"  CIF size: {len(value.get('cif_content', b''))} bytes")
                    
                    # Show Boltz YAML input for each Boltz-1 prediction
                    if value.get('method') == 'Boltz-1':
                        yaml_content = get_latest_yaml_content()
                        debug_log.subheader("Boltz-1 YAML Input Used")
                        debug_log.code(yaml_content)
            else:
                debug_log.warning("No prediction_history in session_state!")
                
            # In the debug log section, add this:
            debug_log.info("Current run methods:")
            debug_log.code(selected_methods)
            debug_log.info("Previous predictions:")
            if 'prediction_history' in st.session_state:
                for key, value in st.session_state.prediction_history.items():
                    debug_log.code(f"Key: {key}, Method: {value.get('method')}")
                
            # Add this to show the YAML that will be used
            if "Boltz-1" in selected_methods:
                debug_log.subheader("Boltz-1 YAML Template")
                debug_log.info("YAML will be generated during execution, check debug logs after prediction completes")
                
            # Add advanced options section with expander
            with st.expander("Advanced Boltz Options"):
                use_msa_server = st.checkbox("Use MSA Server", value=True, 
                                            help="Generate MSA using mmseqs2 server")
                
                # Store settings in session state
                st.session_state.boltz_options = {
                    "use_msa_server": use_msa_server
                }
                
        except Exception as e:
            status_placeholder.error(f"Error in prediction process: {str(e)}")
            import traceback
            status_placeholder.error(f"Traceback: {traceback.format_exc()}")

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