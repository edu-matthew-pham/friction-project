import streamlit as st
from utils import data, standards_map, compression_warnings

def show():
    st.subheader("Curriculum Setup")
    st.caption("Select standards, lesson count and assessment items for this unit.")

    all_titles = [f"{s['code']} — {s['title']}" for s in data["standards"]]
    selected_display = st.multiselect(
        "Standards covered by this unit",
        options=all_titles,
        default=[all_titles[4], all_titles[5]]
    )
    selected_codes = [t.split(" — ")[0] for t in selected_display]

    num_lessons = st.number_input(
        "Total lessons available",
        min_value=4, max_value=40, value=st.session_state.num_lessons, step=1
    )

    if selected_codes:
        total_nodes = sum(len(standards_map[c]["nodes"]) for c in selected_codes if c in standards_map)
        st.info(f"**{total_nodes} waypoints** across {len(selected_codes)} standard(s) · ~**{num_lessons / total_nodes:.1f} lessons/waypoint**")
        for w in compression_warnings(selected_codes, num_lessons):
            st.warning(w)
    else:
        st.warning("Select at least one standard to continue.")

    # ── Assessment items ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("Assessment Items")
    st.caption("Add one or more summative assessment items for this unit.")

    # Initialise assessments list in session state
    if "assessments" not in st.session_state or not st.session_state.assessments:
        st.session_state.assessments = [
            {"id": 1, "label": "Assessment 1", "type": "Test", "timing": "End of unit"}
        ]

    assessments = st.session_state.assessments

    for i, item in enumerate(assessments):
        with st.expander(f"{item['label']} — {item['type']}", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                label = st.text_input(
                    "Label", value=item["label"],
                    key=f"label_{item['id']}"
                )
            with col2:
                atype = st.radio(
                    "Type",
                    ["Test", "Investigation"],
                    index=["Test", "Investigation"].index(item.get("type", "Test")),
                    horizontal=True,
                    key=f"type_{item['id']}",
                    captions=["Closed response", "Practical/extended task"]
                )
            with col3:
                timing = st.radio(
                    "Timing",
                    ["Mid-unit", "End of unit"],
                    index=["Mid-unit", "End of unit"].index(item.get("timing", "End of unit")),
                    horizontal=True,
                    key=f"timing_{item['id']}"
                )

            # Update item
            assessments[i] = {"id": item["id"], "label": label, "type": atype, "timing": timing}

            if len(assessments) > 1:
                if st.button(f"Remove", key=f"remove_{item['id']}"):
                    assessments.pop(i)
                    st.session_state.assessments = assessments
                    st.rerun()

    if st.button("+ Add assessment item"):
        new_id = max(a["id"] for a in assessments) + 1
        assessments.append({"id": new_id, "label": f"Assessment {new_id}", "type": "Test", "timing": "End of unit"})
        st.session_state.assessments = assessments
        st.rerun()

    st.session_state.assessments = assessments

    # ── Continue ──────────────────────────────────────────────────────────────
    st.divider()
    ready = bool(selected_codes)

    if st.button("Review Waypoint Map →", type="primary", disabled=not ready, use_container_width=True):
        st.session_state.selected_codes = selected_codes
        st.session_state.num_lessons = num_lessons
        # Keep backward compat — set assessment_type from first item
        st.session_state.assessment_type = assessments[0]["type"] if assessments else "Test"
        st.session_state.page = "s2_nodes"
        st.rerun()