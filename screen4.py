import streamlit as st
import pandas as pd
from utils import (standards_map, science_band, classify_friction, get_prior_chain,
                   width_emphasis, width_level_label, node_lesson_budget)
from prompts import build_lesson_prompt

def show():
    selected_codes = st.session_state.selected_codes
    num_lessons = st.session_state.num_lessons
    assessment_type = st.session_state.assessment_type

    if st.button("← Back"):
        st.session_state.page = "s3_assessment"
        st.rerun()

    st.subheader("Class Planning")

    # ── Friction setup ────────────────────────────────────────────────────────
    with st.expander("Pace Profile Setup", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            uploaded = st.file_uploader("Upload class CSV (student_id, science_score, gpa)", type="csv")
            if uploaded:
                df = pd.read_csv(uploaded)
                if not {"science_score", "gpa"}.issubset(df.columns):
                    st.error("CSV must contain: science_score, gpa")
                else:
                    df["science_band"] = df["science_score"].apply(science_band)
                    df["gpa_band"] = df["gpa"].clip(1, 5).round().astype(int)
                    df["rfi"] = df["gpa_band"] - df["science_band"]
                    mean_rfi = df["rfi"].mean()
                    st.session_state.mean_rfi = mean_rfi
                    auto_label = classify_friction(mean_rfi)
                    st.session_state.friction_label = auto_label

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Students", len(df))
                    c2.metric("Mean RFI", f"{mean_rfi:.2f}")
                    c3.metric("Calculated Pace Profile", auto_label)

                    with st.expander("View class data"):
                        st.dataframe(
                            df[["student_id", "science_score", "science_band", "gpa", "gpa_band", "rfi"]],
                            use_container_width=True
                        )

        with col2:
            friction_options = ["Advancing", "Steady", "Consolidating"]
            st.session_state.friction_label = st.radio(
                "Pace profile (override if needed)",
                friction_options,
                index=friction_options.index(st.session_state.friction_label),
                captions=[
                    "Science outperforming GPA — needs pace control",
                    "Science aligned with GPA — standard pace",
                    "Science underperforming GPA — needs consolidation",
                ]
            )
            st.session_state.prior = st.select_slider(
                "Prior knowledge vs ACARA assumption (affects width emphasis only)",
                options=["Well below", "Below", "At", "Above"],
                value=st.session_state.prior
            )

    friction = st.session_state.friction_label
    prior = st.session_state.prior
    prior_factor = {"Well below": 1.4, "Below": 1.2, "At": 1.0, "Above": 0.8}[prior]

    friction_guidance = {
        "Advancing": "Faster pace: Keep early waypoints near ±Xmin. Widen at hinge waypoints. All enrichment options available.",
        "Steady": "Typical pace: Minimum width at most waypoints. Selective enrichment at hinge waypoints only.",
        "Consolidating": "Slower pace: Stay near ±Xmin throughout. Targeted supports. No enrichment until core is secure."
    }
    st.info(friction_guidance[friction])
    if st.session_state.mean_rfi is not None:
        st.caption(f"Calculated Mean RFI: {st.session_state.mean_rfi:.2f} (GPA-adjusted method)")

    st.divider()

    # ── Diagnostic results ────────────────────────────────────────────────────
    st.subheader("Diagnostic Results")
    st.caption("Rate each prior knowledge standard based on diagnostic task results. This informs early waypoint pacing.")

    if "diagnostic_ratings" not in st.session_state:
        st.session_state.diagnostic_ratings = {}

    traffic_options = ["🟢 Secure", "🟡 Partial", "🔴 Gap"]

    for code in selected_codes:
        chain = get_prior_chain(code)
        if not chain:
            continue
        with st.expander(f"Prior pathway for {code}", expanded=False):
            # Bulk toggle
            prior_keys = [f"diag_{code}_{item['code']}" for item in chain]
            cols = st.columns(3)
            for ci, label in enumerate(traffic_options):
                if cols[ci].button(f"All {label}", key=f"bulk_prior_{code}_{ci}"):
                    for k in prior_keys:
                        st.session_state.diagnostic_ratings[k] = label
                    st.rerun()
            for item in chain:
                key = f"diag_{code}_{item['code']}"
                current = st.session_state.diagnostic_ratings.get(key, "🟢 Secure")
                rating = st.radio(
                    f"**Year {item['year_level']} · {item['code']}** — {item['y_goal']}",
                    traffic_options,
                    index=traffic_options.index(current),
                    horizontal=True,
                    key=f"radio_{key}"
                )
                st.session_state.diagnostic_ratings[key] = rating

    # Y7 waypoint-level ratings
    st.caption("Update waypoint progress as the unit unfolds — reflects current class understanding, not just the initial diagnostic.")
    for code in selected_codes:
        if code not in standards_map:
            continue
        with st.expander(f"Y7 Waypoint Progress — {code}", expanded=False):
            # Bulk toggle
            y7_keys = [f"diag_y7_{code}_node_{node['id']}" for node in standards_map[code]["nodes"]]
            cols = st.columns(3)
            for ci, label in enumerate(traffic_options):
                if cols[ci].button(f"All {label}", key=f"bulk_y7_{code}_{ci}"):
                    for k in y7_keys:
                        st.session_state.diagnostic_ratings[k] = label
                    st.rerun()
            for node in standards_map[code]["nodes"]:
                key = f"diag_y7_{code}_node_{node['id']}"
                current = st.session_state.diagnostic_ratings.get(key, "🔴 Gap")
                rating = st.radio(
                    f"Waypoint {node['id']}: {node['label']}",
                    traffic_options,
                    index=traffic_options.index(current),
                    horizontal=True,
                    key=f"radio_{key}"
                )
                st.session_state.diagnostic_ratings[key] = rating

    diagnostic_notes = st.text_area(
        "Diagnostic notes (optional)",
        value=st.session_state.get("diagnostic_notes", ""),
        height=80,
        placeholder="Overall observations from the diagnostic — misconceptions, surprises, patterns..."
    )
    st.session_state["diagnostic_notes"] = diagnostic_notes

    st.divider()

    total_nodes = sum(len(standards_map[c]["nodes"]) for c in selected_codes if c in standards_map)
    base_lessons = num_lessons / total_nodes if total_nodes else 1

    # ── Summary table ─────────────────────────────────────────────────────────
    st.subheader("Sequence Overview")
    summary_rows = []
    for code in selected_codes:
        if code not in standards_map:
            continue
        for node in standards_map[code]["nodes"]:
            is_hinge = node["hinge"]
            n_lessons = node_lesson_budget(base_lessons * prior_factor, is_hinge)
            summary_rows.append({
                "Standard": code,
                "Waypoint": str(node["id"]) + ". " + node["label"],
                "Y Position": node.get("y_description") or "",
                "Hinge": "Yes" if is_hinge else "",
                "Hinge Reason": node.get("hinge_reason") or "",
                "Width Level": width_level_label(friction, is_hinge),
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
            "Width Level": st.column_config.TextColumn(width="medium"),
            "Est. Lessons": st.column_config.NumberColumn(width="small"),
        }
    )
    st.caption("See waypoint detail below for tasks at each width level.")
    st.divider()

    # ── Waypoint cards with lesson prompt generators ──────────────────────────────
    for code in selected_codes:
        if code not in standards_map:
            continue
        std = standards_map[code]
        st.subheader(f"{std['code']} — {std['title']}")
        st.caption(f"**Y-goal:** {std['y_goal']}")
        st.caption(f"**Assumed prior:** {std['prior_knowledge']}")
        st.divider()

        for node in std["nodes"]:
            is_hinge = node["hinge"]
            core_task, enrich_opts = width_emphasis(friction, node)
            n_lessons = node_lesson_budget(base_lessons * prior_factor, is_hinge)

            hinge_prefix = "⚑ HINGE — " if is_hinge else ""
            lessons_suffix = "s" if n_lessons != 1 else ""
            label = f"{hinge_prefix}Waypoint {node['id']}: {node['label']}  ·  ~{n_lessons} lesson{lessons_suffix}"

            if is_hinge:
                st.warning(label)
            else:
                st.markdown(f"**{label}**")
            st.caption(f"Y: {node['y_description']}")
            if node.get("success_criteria"):
                st.markdown("**✓ Success criteria**")
                for sc in node["success_criteria"]:
                    st.caption(f"• {sc}")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**±Xmin** *(minimum before advancing)*")
                st.write(node["xmin"])
            with c2:
                st.markdown("**Core width task**")
                st.write(core_task)
            with c3:
                st.markdown("**Enrichment options**")
                if enrich_opts:
                    for opt in enrich_opts:
                        st.markdown(f"- {opt}")
                else:
                    st.caption("Not recommended at this pace profile — consolidate core width first.")

            if is_hinge and node.get("hinge_reason"):
                st.caption(f"⚑ {node['hinge_reason']}")

            # Lesson prompt generator
            with st.expander("Generate lesson prompt for this waypoint"):
                node_key = f"{code}_node_{node['id']}"
                override_lessons = st.number_input(
                    "Number of lessons",
                    min_value=1, max_value=10,
                    value=n_lessons,
                    key=f"lessons_{node_key}"
                )

                assessments_list = st.session_state.get("assessments", [])
                assessment_summary = st.session_state.get("assessment_summary", "")
                diagnostic_ratings = st.session_state.get("diagnostic_ratings", {})
                diagnostic_notes = st.session_state.get("diagnostic_notes", "")

                lesson_prompt = build_lesson_prompt(
                    code=code,
                    node=node,
                    friction=friction,
                    assessment_type=assessment_type,
                    override_lessons=override_lessons,
                    enrich_opts=enrich_opts,
                    assessments=assessments_list,
                    assessment_summary=assessment_summary,
                    diagnostic_ratings=diagnostic_ratings,
                    diagnostic_notes=diagnostic_notes
                )
                st.code(lesson_prompt, language=None)
                st.caption("Copy and paste into Claude.ai, ChatGPT, or Gemini.")

            st.divider()