import streamlit as st
import base64
import os

def show():
    st.subheader("Welcome to Learning Waypoints")
    st.caption("Read the guide below before getting started.")

    # Embed onboarding PDF if it exists
    pdf_path = "learning_waypoints_onboarding.pdf"
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600px"></iframe>',
            unsafe_allow_html=True
        )
    else:
        st.info("Place `learning_waypoints_onboarding.pdf` in the app root folder to display the guide here.")

    st.divider()
    col_a, col_b, col_c = st.columns([2, 1, 2])
    with col_b:
        if st.button("Get Started →", type="primary", use_container_width=True):
            st.session_state.page = "s1_curriculum"
            st.rerun()