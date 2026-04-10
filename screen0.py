import streamlit as st

def show():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500&display=swap');

/* Main page container */
.main > div {
    padding-top: 1rem;
}                

.hero-wrap {
    font-family: 'DM Sans', sans-serif;
    max-width: 720px;
    margin: 0 auto;
    padding: 0.5rem 0.5rem 1rem;
    text-align: center;
}
.hero-title {
    font-family: 'DM Serif Display', serif;
    font-size: clamp(2.2rem, 4vw, 3.2rem);
    line-height: 1.1;
    color: #0f1f17;
    margin-bottom: 1.4rem;
    font-weight: 400;
}
.hero-title em {
    font-style: italic;
    color: #2e6e4e;
}
.hero-sub {
    font-size: 1.05rem;
    line-height: 1.75;
    color: #3a4a40;
    font-weight: 300;
    margin-bottom: 0.8rem;
}
</style>

<div class="hero-wrap">
  <h1 class="hero-title">Keep every class on the<br><em>same conceptual path</em></h1>
  <p class="hero-sub">
    When classes move at different speeds, the usual fix (accelerating some, simplifying for others)
    breaks alignment and makes common assessment hard to justify.
  </p>
  <p class="hero-sub">
    Learning Waypoints manages pace differences horizontally by adjusting pacing, challenge and support, rather than pushing some classes ahead of the shared conceptual sequence.
  </p>
  <p class="hero-sub">
    This supports deeper understanding of core concepts where appropriate, while also helping identify and address gaps to consolidate learning.
  </p>
</div>
""", unsafe_allow_html=True)

    pdf_url = "https://raw.githubusercontent.com/edu-matthew-pham/friction-project/main/learning_waypoints_onboarding.pdf"

    col_a, col_b, col_c = st.columns(3)
    with col_b:
        if st.button("Get Started →", type="primary", use_container_width=True):
            st.session_state.page = "s1_curriculum"
            st.rerun()
        st.link_button("Read the guide →", pdf_url, use_container_width=True)