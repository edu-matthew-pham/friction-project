import streamlit as st
from utils import init_session_state
import screen1, screen2, screen3, screen4

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Learning Waypoints", page_icon="✦", layout="wide")

# ── Session state ─────────────────────────────────────────────────────────────
init_session_state()

# ── Progress indicator ────────────────────────────────────────────────────────
PAGES = ["s1_curriculum", "s2_nodes", "s3_assessment", "s4_planning"]
LABELS = ["1. Curriculum Setup", "2. Waypoint Review", "3. Assessment", "4. Class Planning"]

def show_progress():
    idx = PAGES.index(st.session_state.page) if st.session_state.page in PAGES else 0
    cols = st.columns(len(LABELS))
    for i, (col, label) in enumerate(zip(cols, LABELS)):
        if i < idx:
            col.success(label)
        elif i == idx:
            col.info(label)
        else:
            col.caption(label)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("✦ Learning Waypoints")
st.caption("Year 7 Science · Beta")
show_progress()
st.divider()

# ── Routing ───────────────────────────────────────────────────────────────────
page = st.session_state.page

if page == "s1_curriculum":
    screen1.show()
elif page == "s2_nodes":
    screen2.show()
elif page == "s3_assessment":
    screen3.show()
elif page == "s4_planning":
    screen4.show()