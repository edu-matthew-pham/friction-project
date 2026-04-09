import streamlit as st
import pandas as pd
from utils import (standards_map, science_band, classify_friction, get_prior_chain,
                   width_emphasis, width_level_label, node_lesson_budget)

def show():
    selected_codes = st.session_state.selected_codes
    num_lessons = st.session_state.num_lessons
    assessment_type = st.session_state.assessment_type

    if st.button("← Back"):
        st.session_state.page = "s3_assessment"
        st.rerun()

    st.subheader("Class Planning")

    # ── Friction setup ────────────────────────────────────────────────────────
    with st.expander("Class Friction Setup", expanded=True):
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
                    c3.metric("Calculated Friction", auto_label)

                    with st.expander("View class data"):
                        st.dataframe(
                            df[["student_id", "science_score", "science_band", "gpa", "gpa_band", "rfi"]],
                            use_container_width=True
                        )

        with col2:
            friction_options = ["Low", "Typical", "Medium–High"]
            st.session_state.friction_label = st.radio(
                "Friction level (override if needed)",
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
        "Low": "Low friction: Keep early nodes near ±Xmin. Widen at hinge nodes. All enrichment options available.",
        "Typical": "Typical friction: Minimum width at most nodes. Selective enrichment at hinge nodes only.",
        "Medium–High": "Medium–High friction: Stay near ±Xmin throughout. Targeted supports. No enrichment until core is secure."
    }
    st.info(friction_guidance[friction])
    if st.session_state.mean_rfi is not None:
        st.caption(f"Calculated Mean RFI: {st.session_state.mean_rfi:.2f} (GPA-adjusted method)")

    st.divider()

    # ── Diagnostic results ────────────────────────────────────────────────────
    st.subheader("Diagnostic Results")
    st.caption("Rate each prior knowledge standard based on diagnostic task results. This informs early node pacing.")

    if "diagnostic_ratings" not in st.session_state:
        st.session_state.diagnostic_ratings = {}

    traffic_options = ["🟢 Secure", "🟡 Partial", "🔴 Gap"]

    for code in selected_codes:
        chain = get_prior_chain(code)
        if not chain:
            continue
        with st.expander(f"Prior pathway for {code}", expanded=False):
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

    # Y7 node-level ratings
    st.caption("Optionally rate Y7 nodes if students showed partial knowledge in the diagnostic.")
    for code in selected_codes:
        if code not in standards_map:
            continue
        with st.expander(f"Y7 node ratings for {code} (optional)", expanded=False):
            for node in standards_map[code]["nodes"]:
                key = f"diag_y7_{code}_node_{node['id']}"
                current = st.session_state.diagnostic_ratings.get(key, "🔴 Gap")
                rating = st.radio(
                    f"Node {node['id']}: {node['label']}",
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
                "Node": str(node["id"]) + ". " + node["label"],
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
            "Node": st.column_config.TextColumn(width="medium"),
            "Y Position": st.column_config.TextColumn(width="large"),
            "Hinge": st.column_config.TextColumn(width="small"),
            "Hinge Reason": st.column_config.TextColumn(width="large"),
            "Width Level": st.column_config.TextColumn(width="medium"),
            "Est. Lessons": st.column_config.NumberColumn(width="small"),
        }
    )
    st.caption("See node detail below for tasks at each width level.")
    st.divider()

    # ── Node cards with lesson prompt generators ──────────────────────────────
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
            label = f"{hinge_prefix}Node {node['id']}: {node['label']}  ·  ~{n_lessons} lesson{lessons_suffix}"

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
                    st.caption("Not recommended at this friction level — consolidate core width first.")

            if is_hinge and node.get("hinge_reason"):
                st.caption(f"⚑ {node['hinge_reason']}")

            # Lesson prompt generator
            with st.expander("Generate lesson prompt for this node"):
                node_key = f"{code}_node_{node['id']}"
                override_lessons = st.number_input(
                    "Number of lessons",
                    min_value=1, max_value=10,
                    value=n_lessons,
                    key=f"lessons_{node_key}"
                )

                enrich_text = (
                    "\n".join("- " + o for o in enrich_opts)
                    if enrich_opts else "Not applicable at this friction level."
                )
                hinge_note = (
                    f"\nIMPORTANT — This is a hinge concept: {node['hinge_reason']}"
                    if is_hinge else ""
                )
                friction_lesson_guidance = {
                    "Low": "Students are likely to move quickly. Prioritise enrichment options to deepen construction. Avoid racing ahead to the next node.",
                    "Typical": "Maintain minimum width at this node. Use the core width task. Add enrichment only if time allows.",
                    "Medium–High": "Stay near Xmin. Use targeted supports — worked examples, misconception repair, structured sentence starters. Do not widen prematurely."
                }.get(friction, "Use the core width task.")

                # Build assessment context from all items
                assessments = st.session_state.get("assessments", [])
                assessment_items_text = "\n".join(
                    f"- {a['label']}: {a['type']} · {a['timing']}"
                    for a in assessments
                ) if assessments else f"- {assessment_type}"

                assessment_summary = st.session_state.get("assessment_summary", "")
                task_context = (
                    f"\nASSESSMENT SUMMARY\n" + "─" * 34 + f"\n{assessment_summary}"
                    if assessment_summary.strip() else ""
                )

                # Prior knowledge chain with diagnostic ratings
                prior_chain = get_prior_chain(code)
                diagnostic_ratings = st.session_state.get("diagnostic_ratings", {})
                diagnostic_notes = st.session_state.get("diagnostic_notes", "")
                prior_chain_lines = []
                for item in prior_chain:
                    key = f"diag_{code}_{item['code']}"
                    rating = diagnostic_ratings.get(key, "Not rated")
                    prior_chain_lines.append(
                        f"Year {item['year_level']} · {item['code']} · {item['title']}: {item['y_goal']} [{rating}]"
                    )
                prior_chain_text = "\n".join(prior_chain_lines) if prior_chain_lines else "No prior pathway found."
                if diagnostic_notes.strip():
                    prior_chain_text += f"\nDiagnostic notes: {diagnostic_notes}"

                # Add Y7 node diagnostic rating for this specific node
                node_diag_key = f"diag_y7_{code}_node_{node['id']}"
                node_diag_rating = diagnostic_ratings.get(node_diag_key, "")
                node_diag_text = f"\nDiagnostic rating for this node: {node_diag_rating}" if node_diag_rating else ""

                # Build friction-aware success criteria
                sc_xmin = node.get("success_criteria", [])
                sc_lines = ["Xmin (target for all students):"]
                sc_lines += ["- " + sc for sc in sc_xmin]
                if friction in ["Typical", "Low"] and node.get("width_core"):
                    sc_lines += ["", "X+ (target for this class — core width):"]
                    sc_lines += ["- Demonstrate: " + node["width_core"]]
                if friction == "Low" and enrich_opts:
                    sc_lines += ["", "X++ (target for this class — enrichment):"]
                    sc_lines += ["- Demonstrate: " + enrich_opts[0]]
                sc_text_prompt = "\n".join(sc_lines)

                lesson_prompt = f"""You are helping a Year 7 Science teacher plan lessons for a single conceptual node.

CONTEXT
──────────────────────────────────
Subject: Year 7 Science
Standard: {code}
Node: {node['id']}. {node['label']}
Class Friction: {friction}
Assessment Type: {assessment_type}
Lessons available: {override_lessons}

CONCEPTUAL POSITION (Y) — overarching learning intention for this node
──────────────────────────────────
{node['y_description']}{node_diag_text}

PRIOR KNOWLEDGE (what students already know coming into this unit)
──────────────────────────────────
{prior_chain_text}

SUCCESS CRITERIA (friction-adjusted for {friction} class)
──────────────────────────────────
{sc_text_prompt}

MINIMUM CONSTRUCTION (±Xmin)
──────────────────────────────────
{node['xmin']}

CORE WIDTH TASK
──────────────────────────────────
{core_task}

ENRICHMENT OPTIONS
──────────────────────────────────
{enrich_text}{hinge_note}

FRICTION GUIDANCE
──────────────────────────────────
{friction_lesson_guidance}

ASSESSMENT CONTEXT
──────────────────────────────────
Assessment items for this unit:
{assessment_items_text}{task_context}

YOUR TASK
──────────────────────────────────
Planning structure:
- Learning intention (shared across all lessons for this node): the node Y description above — do not rewrite or decompose it
- Success criteria: distributed across lessons as targets; each lesson targets one or more from the list above
- Formative check: directly tests the success criterion(a) targeted in that lesson

Generate a lesson sequence for {override_lessons} lesson(s). For each lesson use this structure:

1. Learning intention — the node Y description (same for all lessons, all classes)
2. Success criterion(a) targeted this lesson — named from the friction-adjusted list above
3. Starter activity (5–10 min)
4. Main activity aligned to the appropriate width level for this friction class
5. Formative check — directly tests the success criterion(a) named in step 2
6. Misconceptions to watch for and how to address them

Keep all activities within the conceptual scope of this node. Do not introduce content from later nodes."""

                st.code(lesson_prompt, language=None)
                st.caption("Copy and paste into Claude.ai, ChatGPT, or Gemini.")

            st.divider()