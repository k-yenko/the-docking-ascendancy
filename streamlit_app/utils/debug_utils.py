def print_dependencies():
    """Print all import dependencies to verify connections"""
    import sys
    import importlib
    
    modules = [
        "streamlit_app.modal_services.boltz_service",
        "streamlit_app.modal_services.chai_service",
        "streamlit_app.utils.boltz_utils",
        "streamlit_app.utils.bindcraft_utils",
        "streamlit_app.utils.common_utils"
    ]
    
    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
            print(f"✅ Successfully imported {module_name}")
        except ImportError as e:
            print(f"❌ Failed to import {module_name}: {e}") 