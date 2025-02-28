import streamlit as st

def main():
    st.title("BindCraft Structure Prediction")
    st.write("Welcome! Please use the navigation menu on the left to:")
    st.write("1. Input Target Protein (optional)")
    st.write("2. Select Binder from Gallery")
    st.write("3. Run Structure Predictions")
    st.write("4. View Results Dashboard")

def check_connections():
    """Check all service connections"""
    st.sidebar.subheader("Service Status")
    
    # Check Modal services
    services_status = check_services_ready()
    
    for service, status in services_status.items():
        if status:
            st.sidebar.success(f"✅ {service.capitalize()} service connected")
        else:
            st.sidebar.warning(f"⚠️ {service.capitalize()} service not connected")
    
    # Add reset button
    if st.sidebar.button("Reset Services"):
        from streamlit_app.utils.service_utils import reset_all_services
        reset_all_services()
        st.sidebar.info("Services reset requested. Refresh the page.")

if __name__ == "__main__":
    main() 