"""
Utilities for service readiness and management
"""
import modal

def check_services_ready():
    """Check if all Modal services are ready and deployed"""
    from streamlit_app.modal_services.boltz_service import boltz_app
    from streamlit_app.modal_services.chai_service import chai_app
    
    services_status = {}
    
    # Check Boltz service
    try:
        boltz_ready = boltz_app.is_deployed()
        services_status['boltz'] = boltz_ready
    except Exception as e:
        print(f"Error checking Boltz service: {e}")
        services_status['boltz'] = False
    
    # Check Chai service
    try:
        chai_ready = chai_app.is_deployed()
        services_status['chai'] = chai_ready
    except Exception as e:
        print(f"Error checking Chai service: {e}")
        services_status['chai'] = False
    
    return services_status 

def reset_all_services():
    """Reset all Modal services to clear any conflicts"""
    import modal
    
    try:
        modal.reset()
        print("Successfully reset Modal services")
        return True
    except Exception as e:
        print(f"Error resetting Modal services: {e}")
        return False 