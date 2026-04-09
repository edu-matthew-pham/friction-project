import streamlit as st
from utils import standards_map, get_prior_chain, generate_pdf


def build_context(selected_codes):
    hinge_nodes, y_goals, sc_lines, prior_lines = [], [], [], []
    for code in selected_codes:
        if code not in standards_map:
            continue
        std = standards_map[code]
        y_goals.append(f"{code}: {std['y_goal']}")
        for node in std["nodes"]:
            if node["hinge"]:
                hinge_nodes.append(f"- Node {node['id']} ({code}): {node['label']} — {node.get('hinge_reason', '')}")
            sc = node.get("success_criteria", [])
            if sc:
                sc_lines.append(f"Node {node['id']} ({code}) — {node['label']}:")
                for s in sc:
                    sc_lines.append(f"  • {s}")
        chain = get_prior_chain(code)
        if chain:
            prior_lines.append(f"{code} prior pathway:")
            for item in chain:
                prior_lines.append(f"  Year {item['year_level']} · {item['code']} · {item['title']}: {item['y_goal']}")

    return {
        "y_goal_text": "\n".join(y_goals),
        "prior_text": "\n".join(prior_lines) if prior_lines else "No prior pathway found.",
        "hinge_text": "\n".join(hinge_nodes) if hinge_nodes else "None identified",
        "sc_text": "\n".join(sc_lines) if sc_lines else "None defined",
    }


def build_assessment_prompt(selected_codes, assessments, existing_tasks, existing_summary):
    ctx = build_context(selected_codes)

    # Build assessment items section
    items_lines = []
    for a in assessments:
        items_lines.append(f"- {a['label']}: {a['type']} · {a['timing']}")
    items_text = "\n".join(items_lines)

    # Build task instructions per item
    task_instructions = []
    for a in assessments:
        existing = existing_tasks.get(a["id"], "").strip()
        if existing:
            task_instructions.append(
                f"OUTPUT {a['id']} — REVISED: {a['label']} ({a['type']}, {a['timing']})\n"
                f"Existing task to review:\n{existing}\n"
                f"Evaluate against X–Y requirements and rewrite items that do not meet them."
            )
        else:
            timing_note = (
                "This is a MID-UNIT assessment — cover nodes taught so far, not the full unit."
                if a["timing"] == "Mid-unit"
                else "This is an END-OF-UNIT assessment — cover all nodes in the unit."
            )
            task_instructions.append(
                f"OUTPUT {a['id']} — DRAFT: {a['label']} ({a['type']}, {a['timing']})\n"
                f"{timing_note}\n"
                f"Draft a complete assessment task with:\n"
                f"  Section A — Xmin (~60%): compulsory, tests minimum construction\n"
                f"  Section B — X+ (~30%): same concepts, broader integration\n"
                f"  Section C — X++ (~10%): open-access transfer and synthesis\n"
                f"Do not exceed Y-goals. Do not label any section as 'extension'."
            )

    summary_instruction = ""
    if existing_summary.strip():
        summary_instruction = (
            f"FINAL OUTPUT — REVISED SUMMARY\n"
            f"Existing summary to review:\n{existing_summary}\n"
            f"Revise to cover all assessment items above."
        )
    else:
        summary_instruction = (
            "FINAL OUTPUT — COMBINED SUMMARY (150 words max)\n"
            "Summarise all assessment items for lesson planning. Include:\n"
            "- Each item's type, timing and format\n"
            "- Key concepts per section (A/B/C) for each item\n"
            "- Which hinge concepts are tested and in which item\n"
            "- Mark weighting per section"
        )

    return f"""You are helping a Head of Department design Year 7 Science assessments aligned to the X–Y Constructivist Model.

CONTEXT
──────────────────────────────────
Year Level: 7
Subject: Science
Standards: {', '.join(selected_codes)}

ASSESSMENT ITEMS
──────────────────────────────────
{items_text}

Y-GOALS (do not exceed these)
──────────────────────────────────
{ctx['y_goal_text']}

PRIOR KNOWLEDGE PATHWAY
──────────────────────────────────
{ctx['prior_text']}

HINGE CONCEPTS (must be adequately assessed across items)
──────────────────────────────────
{ctx['hinge_text']}

SUCCESS CRITERIA PER NODE (Section A items must test these)
──────────────────────────────────
{ctx['sc_text']}

ASSESSMENT MODEL
──────────────────────────────────
- Xmin = minimum construction (~60%)
- X+ = extended width, same concepts (~30%)
- X++ = synthetic width, open-access transfer (~10%)

YOUR TASK
──────────────────────────────────
Provide one output per assessment item, then a combined summary.

{chr(10).join(task_instructions)}

{summary_instruction}"""


def build_diagnostic_prompt(selected_codes, existing_diagnostic=""):
    ctx = build_context(selected_codes)

    if existing_diagnostic.strip():
        task_instruction = f"""EXISTING DIAGNOSTIC TASK TO REVIEW
──────────────────────────────────
{existing_diagnostic}

YOUR TASK
──────────────────────────────────
Review and improve the existing diagnostic task. Ensure it:
- Targets prior knowledge from the pathway above, not Y7 content
- Is completable in 10–15 minutes
- Surfaces common misconceptions and gaps
- Generates actionable information for the teacher"""
    else:
        task_instruction = """YOUR TASK
──────────────────────────────────
Design a short pre-unit diagnostic task (10–15 minutes) that:
- Targets prior knowledge from the pathway above, not Y7 content
- Surfaces what students already know and common misconceptions
- Is accessible to all students regardless of prior achievement
- Generates actionable information: teacher can identify students who need more consolidation at early nodes
- Is not a test — frame it as a curiosity or thinking task"""

    # Build Xmin per node for Y7 standards
    xmin_lines = []
    for code in selected_codes:
        if code not in standards_map:
            continue
        std = standards_map[code]
        xmin_lines.append(f"{code} — {std['title']}:")
        for node in std["nodes"]:
            xmin_lines.append(f"  Node {node['id']}: {node['xmin']}")
    xmin_text = "\n".join(xmin_lines) if xmin_lines else "None defined"

    return f"""You are helping a Year 7 Science teacher design a pre-unit diagnostic assessment.

CONTEXT
──────────────────────────────────
Year Level: 7
Subject: Science
Standards: {', '.join(selected_codes)}

PURPOSE
──────────────────────────────────
This diagnostic is completed BEFORE teaching begins. It informs:
- Where students actually are relative to assumed prior knowledge
- Whether any students have partial knowledge of Y7 content already
- Which early nodes may need more consolidation time
- Initial friction/pace estimate for the class

PRIOR KNOWLEDGE PATHWAY (probe these — what students should already know)
──────────────────────────────────
{ctx['prior_text']}

Y7 NODE MINIMUMS (Xmin — optionally probe these to surface partial Y7 knowledge)
──────────────────────────────────
{xmin_text}

Y-GOALS FOR THIS UNIT (teaching destination — do not fully assess these)
──────────────────────────────────
{ctx['y_goal_text']}

{task_instruction}"""


def show():
    selected_codes = st.session_state.selected_codes
    assessments = st.session_state.get("assessments", [])

    if st.button("← Back"):
        st.session_state.page = "s2_nodes"
        st.rerun()

    st.subheader("Assessment Setup")
    st.caption(f"Standards: {', '.join(selected_codes)} · {len(assessments)} assessment item(s)")

    # ── Diagnostic ───────────────────────────────────────────────────────────
    st.subheader("Diagnostic Assessment")
    st.caption("Pre-unit task to probe prior knowledge before teaching begins. Informs starting point and pace profile.")

    existing_diagnostic = st.text_area(
        "Existing diagnostic task (optional)",
        value=st.session_state.get("existing_diagnostic", ""),
        height=100,
        placeholder="Paste existing diagnostic to review, or leave blank to draft new..."
    )
    st.session_state["existing_diagnostic"] = existing_diagnostic

    if st.button("Generate Diagnostic Prompt", use_container_width=True):
        st.session_state["last_diagnostic_prompt"] = build_diagnostic_prompt(
            selected_codes, existing_diagnostic
        )

    if st.session_state.get("last_diagnostic_prompt"):
        st.code(st.session_state["last_diagnostic_prompt"], language=None)
        st.caption("Copy and paste into Claude.ai, ChatGPT, or Gemini.")

    diagnostic_task = st.text_area(
        "Diagnostic task (paste AI output)",
        value=st.session_state.get("diagnostic_task", ""),
        height=120,
        placeholder="Paste the diagnostic task here...",
        label_visibility="collapsed"
    )
    st.session_state["diagnostic_task"] = diagnostic_task

    st.divider()

    # ── Step 1: Generate combined prompt ─────────────────────────────────────
    st.subheader("Step 1 — Generate Assessment Prompt")
    st.caption("Optionally paste existing tasks/summary — the prompt will review them. Leave blank to draft from scratch.")

    # Optional existing inputs per assessment item
    existing_tasks = {}
    with st.expander("Paste existing tasks (optional)"):
        for a in assessments:
            val = st.text_area(
                f"{a['label']} ({a['type']}, {a['timing']})",
                value=st.session_state.get(f"existing_task_{a['id']}", ""),
                height=120,
                placeholder=f"Paste existing {a['label']} task to review, or leave blank...",
                key=f"existing_task_input_{a['id']}"
            )
            st.session_state[f"existing_task_{a['id']}"] = val
            existing_tasks[a["id"]] = val

    existing_summary = st.text_area(
        "Existing summary (optional)",
        value=st.session_state.get("existing_summary", ""),
        height=80,
        placeholder="Paste existing summary to review, or leave blank..."
    )
    st.session_state["existing_summary"] = existing_summary

    if st.button("Generate Assessment Prompt", type="primary", use_container_width=True):
        st.session_state["last_assessment_prompt"] = build_assessment_prompt(
            selected_codes, assessments, existing_tasks, existing_summary
        )

    if st.session_state.get("last_assessment_prompt"):
        st.code(st.session_state["last_assessment_prompt"], language=None)
        st.caption("Copy and paste into Claude.ai, ChatGPT, or Gemini.")

    # ── Step 2: Paste outputs ─────────────────────────────────────────────────
    st.divider()
    st.subheader("Step 2 — Paste AI Outputs")

    for a in assessments:
        task_val = st.text_area(
            f"Output {a['id']}: {a['label']} ({a['type']}, {a['timing']})",
            value=st.session_state.get(f"finalised_task_{a['id']}", ""),
            height=160,
            placeholder=f"Paste Output {a['id']} — {a['label']} task here...",
            key=f"finalised_task_input_{a['id']}"
        )
        st.session_state[f"finalised_task_{a['id']}"] = task_val

    assessment_summary = st.text_area(
        "Combined assessment summary",
        value=st.session_state.get("assessment_summary", ""),
        height=100,
        placeholder="Paste the combined summary here...",
    )
    st.session_state["assessment_summary"] = assessment_summary

    # ── Confirm and export ────────────────────────────────────────────────────
    st.divider()
    all_tasks_filled = all(
        st.session_state.get(f"finalised_task_{a['id']}", "").strip()
        for a in assessments
    )
    task_confirmed = st.checkbox(
        "All assessment tasks and summary are finalised — ready for class planning",
        disabled=not (all_tasks_filled and assessment_summary.strip())
    )

    if task_confirmed:
        st.divider()
        st.subheader("Download Unit Plan")
        st.caption("Class-agnostic PDF — teachers annotate with their friction level.")
        assessment_type = assessments[0]["type"] if assessments else "Test"
        pdf_buf = generate_pdf(
            selected_codes=selected_codes,
            num_lessons=st.session_state.num_lessons,
            assessment_type=assessment_type,
            assessment_summary=assessment_summary
        )
        st.download_button(
            label="⬇ Download Unit Plan PDF",
            data=pdf_buf,
            file_name=f"unit_plan_{'_'.join(selected_codes)}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )

    st.divider()
    if st.button("Continue to Class Planning →", type="primary",
                 disabled=not task_confirmed, use_container_width=True):
        st.session_state.page = "s4_planning"
        st.rerun()