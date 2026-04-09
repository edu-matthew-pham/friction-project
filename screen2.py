import streamlit as st
import pandas as pd
from utils import standards_map, compression_warnings, node_lesson_budget, get_prior_chain

def show():
    selected_codes = st.session_state.selected_codes
    num_lessons = st.session_state.num_lessons

    if st.button("← Back"):
        st.session_state.page = "s1_curriculum"
        st.rerun()

    st.subheader("Waypoint Review")
    st.caption("Review the pre-built waypoint sequence for the selected standards. All waypoints are mandatory and ACARA-compliant.")

    total_nodes = sum(len(standards_map[c]["nodes"]) for c in selected_codes if c in standards_map)
    base_lessons = num_lessons / total_nodes if total_nodes else 1

    for w in compression_warnings(selected_codes, num_lessons):
        st.warning(w)

    # Summary table
    summary_rows = []
    for code in selected_codes:
        if code not in standards_map:
            continue
        for node in standards_map[code]["nodes"]:
            is_hinge = node["hinge"]
            n_lessons = node_lesson_budget(base_lessons, is_hinge)
            summary_rows.append({
                "Standard": code,
                "Waypoint": str(node["id"]) + ". " + node["label"],
                "Y Position": node.get("y_description") or "",
                "Hinge": "Yes" if is_hinge else "",
                "Hinge Reason": node.get("hinge_reason") or "",
                "Est. Lessons": n_lessons,
            })

    st.dataframe(
        pd.DataFrame(summary_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Standard": st.column_config.TextColumn(width="small"),
            "Waypoint": st.column_config.TextColumn(width="medium"),
            "Y Position": st.column_config.TextColumn(width="large"),
            "Hinge": st.column_config.TextColumn(width="small"),
            "Hinge Reason": st.column_config.TextColumn(width="large"),
            "Est. Lessons": st.column_config.NumberColumn(width="small"),
        }
    )
    st.caption("Est. Lessons are indicative only. Hinge waypoints are allocated slightly more time by default.")
    st.divider()

    # Prior knowledge chain
    st.subheader("Prior Knowledge Pathway")
    st.caption("Conceptual pathway leading to this unit — from Foundation to Year 7.")
    for code in selected_codes:
        chain = get_prior_chain(code)
        if chain:
            st.markdown(f"**{code} prior pathway:**")
            for item in chain:
                st.caption(f"Year {item['year_level']} · {item['code']} · {item['title']}: {item['y_goal']}")
        else:
            st.caption(f"{code}: no prior pathway found in progression map.")
    st.divider()

    # Full waypoint detail
    with st.expander("View full waypoint detail"):
        for code in selected_codes:
            if code not in standards_map:
                continue
            std = standards_map[code]
            st.subheader(f"{std['code']} — {std['title']}")
            st.caption(f"**Y-goal:** {std['y_goal']}")
            st.caption(f"**Assumed prior:** {std['prior_knowledge']}")
            for node in std["nodes"]:
                is_hinge = node["hinge"]
                hinge_prefix = "⚑ HINGE — " if is_hinge else ""
                st.markdown(f"**{hinge_prefix}Waypoint {node['id']}: {node['label']}**")
                st.caption(f"Y: {node['y_description']}")
                if node.get("success_criteria"):
                    st.markdown("**✓ Success criteria**")
                    for sc in node["success_criteria"]:
                        st.caption(f"• {sc}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**±Xmin**")
                    st.write(node["xmin"])
                with c2:
                    st.markdown("**Core width**")
                    st.write(node["width_core"])
                with c3:
                    st.markdown("**Enrichment options**")
                    for opt in node.get("width_enrich_options", []):
                        st.markdown(f"- {opt}")
                if is_hinge and node.get("hinge_reason"):
                    st.caption(f"⚑ {node['hinge_reason']}")
                st.divider()

    if st.button("Set Up Assessment →", type="primary", use_container_width=True):
        st.session_state.page = "s3_assessment"
        st.rerun()