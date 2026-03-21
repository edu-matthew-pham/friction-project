import streamlit as st
import pandas as pd
import json
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="X–Y Unit Planner", page_icon="✦", layout="wide")

# ── Load node data ─────────────────────────────────────────────────────────────
@st.cache_data
def load_nodes():
    with open("y7_science_nodes.json") as f:
        return json.load(f)

data = load_nodes()
standards_map = {s["code"]: s for s in data["standards"]}

# ── Helpers ───────────────────────────────────────────────────────────────────
def science_band(score):
    if score >= 85: return 5
    elif score >= 75: return 4
    elif score >= 60: return 3
    elif score >= 45: return 2
    else: return 1

def classify_friction(mean_rfi):
    if mean_rfi <= -0.5: return "Low"
    elif mean_rfi < 0.5: return "Typical"
    else: return "Medium–High"

def width_emphasis(friction, node):
    opts = node.get("width_enrich_options", [])
    if friction == "Low":
        return node["width_core"], opts
    elif friction == "Medium–High":
        return node["width_core"], []
    else:
        return node["width_core"], opts[:1] if opts else []

def width_level_label(friction, is_hinge):
    if friction == "Low":
        return "Core + Enrich" if is_hinge else "Core"
    elif friction == "Medium–High":
        return "Core" if is_hinge else "Xmin"
    else:
        return "Core + Enrich" if is_hinge else "Core"

def friction_label_short(f):
    return {"Low": "low", "Typical": "typical", "Medium–High": "medium-high"}[f]

def node_lesson_budget(base, is_hinge):
    return max(1, round(base * (1.3 if is_hinge else 1.0)))

def compression_warnings(selected_codes, num_lessons):
    warnings = []
    total_nodes = sum(len(standards_map[c]["nodes"]) for c in selected_codes if c in standards_map)
    base = num_lessons / total_nodes if total_nodes else 1
    if base < 1:
        warnings.append(f"⚠ Only {num_lessons} lessons for {total_nodes} nodes — some nodes will need to share a lesson.")
    for code in selected_codes:
        if code not in standards_map:
            continue
        for node in standards_map[code]["nodes"]:
            if node["hinge"] and node_lesson_budget(base, True) < 2:
                warnings.append(f"⚠ Hinge node '{node['label']}' ({code}) has less than 2 lessons — consider increasing lesson count.")
    return warnings

# ── Session state ─────────────────────────────────────────────────────────────
defaults = {
    "page": "s1_curriculum",
    "selected_codes": [],
    "num_lessons": 12,
    "assessment_type": "Test",
    "friction_label": "Typical",
    "mean_rfi": None,
    "assessment_mode": "Draft new",
    "existing_task": "",
    "finalised_task": "",
    "last_assessment_prompt": "",
    "last_summary_prompt": "",
    "assessment_summary": "",
    "prior": "At",
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── Progress indicator ────────────────────────────────────────────────────────
PAGES = ["s1_curriculum", "s2_nodes", "s3_assessment", "s4_planning"]
LABELS = ["1. Curriculum Setup", "2. Node Review", "3. Assessment", "4. Class Planning"]

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

st.title("✦ X–Y Unit Planner")
st.caption("Year 7 Science · Friction Project POC")
show_progress()
st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 1 — CURRICULUM SETUP
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "s1_curriculum":
    st.subheader("Curriculum Setup")
    st.caption("Select the standards, lesson count and assessment type for this unit.")

    all_titles = [f"{s['code']} — {s['title']}" for s in data["standards"]]
    selected_display = st.multiselect(
        "Standards covered by this assessment",
        options=all_titles,
        default=[all_titles[4], all_titles[5]]
    )
    selected_codes = [t.split(" — ")[0] for t in selected_display]

    col1, col2 = st.columns(2)
    with col1:
        num_lessons = st.number_input(
            "Total lessons available",
            min_value=4, max_value=40, value=st.session_state.num_lessons, step=1
        )
    with col2:
        assessment_type = st.radio(
            "Assessment type",
            ["Test", "Investigation"],
            index=["Test", "Investigation"].index(st.session_state.assessment_type),
            captions=[
                "Closed response, time-limited, teacher-designed",
                "Practical or extended task, teacher-structured"
            ]
        )

    if selected_codes:
        total_nodes = sum(len(standards_map[c]["nodes"]) for c in selected_codes if c in standards_map)
        st.info(f"**{total_nodes} nodes** across {len(selected_codes)} standard(s) · ~**{num_lessons / total_nodes:.1f} lessons/node**")

        warns = compression_warnings(selected_codes, num_lessons)
        for w in warns:
            st.warning(w)
    else:
        st.warning("Select at least one standard to continue.")

    if st.button("Review Node Map →", type="primary", disabled=not selected_codes, use_container_width=True):
        st.session_state.selected_codes = selected_codes
        st.session_state.num_lessons = num_lessons
        st.session_state.assessment_type = assessment_type
        st.session_state.page = "s2_nodes"
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 2 — NODE REVIEW
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "s2_nodes":
    selected_codes = st.session_state.selected_codes
    num_lessons = st.session_state.num_lessons

    col_back, col_fwd = st.columns([1, 4])
    with col_back:
        if st.button("← Back"):
            st.session_state.page = "s1_curriculum"
            st.rerun()

    st.subheader("Node Review")
    st.caption("Review the pre-built node sequence for the selected standards. All nodes are mandatory and ACARA-compliant.")

    total_nodes = sum(len(standards_map[c]["nodes"]) for c in selected_codes if c in standards_map)
    base_lessons = num_lessons / total_nodes if total_nodes else 1

    warns = compression_warnings(selected_codes, num_lessons)
    for w in warns:
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
                "Node": str(node["id"]) + ". " + node["label"],
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
            "Node": st.column_config.TextColumn(width="medium"),
            "Y Position": st.column_config.TextColumn(width="large"),
            "Hinge": st.column_config.TextColumn(width="small"),
            "Hinge Reason": st.column_config.TextColumn(width="large"),
            "Est. Lessons": st.column_config.NumberColumn(width="small"),
        }
    )

    st.caption("Est. Lessons are indicative only. Hinge nodes are allocated slightly more time by default.")
    st.divider()

    # Node detail
    with st.expander("View full node detail"):
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
                st.markdown(f"**{hinge_prefix}Node {node['id']}: {node['label']}**")
                st.caption(f"Y: {node['y_description']}")
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

# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 3 — ASSESSMENT SETUP
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "s3_assessment":
    selected_codes = st.session_state.selected_codes
    assessment_type = st.session_state.assessment_type

    col_back, _ = st.columns([1, 4])
    with col_back:
        if st.button("← Back"):
            st.session_state.page = "s2_nodes"
            st.rerun()

    st.subheader("Assessment Setup")
    st.caption(f"Assessment type: **{assessment_type}** · Standards: {', '.join(selected_codes)}")

    mode = st.radio(
        "Assessment task",
        ["Draft new", "Review existing"],
        index=["Draft new", "Review existing"].index(st.session_state.assessment_mode),
        horizontal=True
    )
    st.session_state.assessment_mode = mode

    existing_task = ""
    if mode == "Review existing":
        existing_task = st.text_area(
            "Paste your existing assessment task here",
            value=st.session_state.existing_task,
            height=200,
            placeholder="Paste the full assessment task text..."
        )
        st.session_state.existing_task = existing_task

    if st.button("Generate Assessment Prompt", type="primary", use_container_width=True):

        # Build hinge summary
        hinge_nodes = []
        y_goals = []
        for code in selected_codes:
            if code not in standards_map:
                continue
            std = standards_map[code]
            y_goals.append(f"{code}: {std['y_goal']}")
            for node in std["nodes"]:
                if node["hinge"]:
                    hinge_nodes.append(f"- Node {node['id']} ({code}): {node['label']} — {node.get('hinge_reason', '')}")

        hinge_text = "\n".join(hinge_nodes) if hinge_nodes else "None identified"
        y_goal_text = "\n".join(y_goals)

        if mode == "Draft new":
            task_instruction = """YOUR TASK
──────────────────────────────────
Draft a complete assessment task with three sections:

Section A — Core Width (Xmin) (~60% of marks)
Compulsory items accessible to all students. Test minimum construction at key nodes.
Focus: clarity, correctness, structured response.
Typical items: identify, describe, explain, compare using scaffolded criteria.

Section B — Extended Width (X+) (~30% of marks)
Same concepts but requiring broader integration and coordination.
Typical items: complete and explain, justify using reasoning, analyse a scenario.

Section C — Synthetic Width (X++) (~10% of marks)
Open-access. Students choose one option demonstrating transfer, application or synthesis.
Typical items: evaluate a claim, explain a real-world application, defend a position.

IMPORTANT:
- No section introduces content beyond the Y-goals above
- All students may attempt all sections
- Do not label any section as "extension"
- Assessment mean should naturally sit around 60% if well-calibrated"""
        else:
            task_instruction = f"""EXISTING TASK TO REVIEW
──────────────────────────────────
{existing_task}

YOUR TASK
──────────────────────────────────
Evaluate the existing task above against the X–Y model requirements:

1. Does it certify minimum width (Xmin) for all students? (~60% of marks)
2. Does it reward extended width (X+) without requiring new content? (~30% of marks)
3. Does it provide open-access synthetic width (X++)? (~10% of marks)
4. Are hinge concepts adequately assessed?
5. Does any item exceed the Y-goals stated above?

Then suggest specific improvements to align it with the three-section structure.
Rewrite any items that do not meet the model's requirements."""

        assessment_prompt = f"""You are helping a Head of Department design a Year 7 Science assessment aligned to the X–Y Constructivist Model.

CONTEXT
──────────────────────────────────
Year Level: 7
Subject: Science
Assessment Type: {assessment_type}
Standards: {', '.join(selected_codes)}

Y-GOALS (fixed conceptual endpoints — do not exceed these)
──────────────────────────────────
{y_goal_text}

HINGE CONCEPTS (must be adequately assessed)
──────────────────────────────────
{hinge_text}

ASSESSMENT MODEL
──────────────────────────────────
This assessment uses the X–Y model where:
- Y-axis = conceptual depth (fixed, same for all students)
- X-axis = width of construction (differentiated horizontally)
- Xmin = minimum construction certifying the standard (~60% of marks)
- X+ = extended width, same concepts, broader integration (~30% of marks)
- X++ = synthetic width, open-access transfer and application (~10% of marks)

{task_instruction}"""

        st.session_state["last_assessment_prompt"] = assessment_prompt

    # Persist prompt display outside button block
    if st.session_state.get("last_assessment_prompt"):
        st.subheader("Assessment Prompt")
        st.code(st.session_state["last_assessment_prompt"], language=None)
        st.caption("Copy and paste into Claude.ai, ChatGPT, or Gemini.")

    st.divider()
    st.subheader("Step 2 — Paste Full Task")
    st.caption("Paste the full AI-generated task here for reference. Download a copy for your records.")

    finalised_task = st.text_area(
        "Full assessment task",
        value=st.session_state.get("finalised_task", ""),
        height=180,
        placeholder="Paste the full AI-generated task here...",
        label_visibility="collapsed"
    )
    st.session_state["finalised_task"] = finalised_task

    st.divider()
    st.subheader("Step 3 — Generate and Paste Assessment Summary")
    st.caption("Generate a concise summary to inform lesson planning. Paste the result in the box below — only the summary feeds into Screen 4.")

    if finalised_task.strip():
        if st.button("Generate Summary Prompt", use_container_width=True):
            summary_prompt = f"""You are helping summarise an assessment task for Year 7 Science lesson planning purposes.

ASSESSMENT TASK
──────────────────────────────────
{finalised_task}

YOUR TASK
──────────────────────────────────
Generate a concise assessment summary (maximum 150 words) suitable for informing lesson planning. Include:
- Assessment type and format
- Key concepts assessed in Section A (Xmin), Section B (X+), and Section C (X++)
- Which hinge concepts are directly tested
- Overall mark weighting per section

Do not reproduce the full task. The summary will be used as context in lesson planning prompts."""
            st.session_state["last_summary_prompt"] = summary_prompt

        if st.session_state.get("last_summary_prompt"):
            st.code(st.session_state["last_summary_prompt"], language=None)
            st.caption("Copy and paste into Claude.ai, ChatGPT, or Gemini.")
    else:
        st.info("Paste the full task in Step 2 first to generate a summary prompt.")

    assessment_summary = st.text_area(
        "Assessment summary (used in lesson planning prompts)",
        value=st.session_state.get("assessment_summary", ""),
        height=120,
        placeholder="Paste the AI-generated summary here...",
        label_visibility="collapsed"
    )
    st.session_state["assessment_summary"] = assessment_summary

    task_confirmed = st.checkbox(
        "Assessment task and summary are finalised — ready for class planning",
        disabled=not (finalised_task.strip() and st.session_state.get("assessment_summary", "").strip())
    )

    if st.button("Continue to Class Planning →", type="primary",
                 disabled=not task_confirmed, use_container_width=True):
        st.session_state.page = "s4_planning"
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 4 — CLASS PLANNING
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "s4_planning":
    selected_codes = st.session_state.selected_codes
    num_lessons = st.session_state.num_lessons
    assessment_type = st.session_state.assessment_type

    col_back, _ = st.columns([1, 4])
    with col_back:
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

                assessment_context = {
                    "Test": "Lessons should build toward a written test. Prioritise clarity of explanation, correct use of terminology, and structured responses.",
                    "Investigation": "Lessons should build toward a practical investigation. Prioritise procedural understanding, observation skills, and evidence-based reasoning."
                }.get(assessment_type, "")
                assessment_summary = st.session_state.get("assessment_summary", "")
                task_context = f"\nASSESSMENT SUMMARY\n{'─'*34}\n{assessment_summary}" if assessment_summary.strip() else ""

                lesson_prompt = f"""You are helping a Year 7 Science teacher plan lessons for a single conceptual node.

CONTEXT
──────────────────────────────────
Subject: Year 7 Science
Standard: {code}
Node: {node['id']}. {node['label']}
Class Friction: {friction}
Assessment Type: {assessment_type}
Lessons available: {override_lessons}

CONCEPTUAL POSITION (Y)
──────────────────────────────────
{node['y_description']}

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
{assessment_context}{task_context}

YOUR TASK
──────────────────────────────────
Generate a lesson sequence for {override_lessons} lesson(s) covering this node. For each lesson include:
- Learning intention aligned to the Y position above
- Starter activity (5–10 min)
- Main activity aligned to the appropriate width level for this friction class
- Formative check (exit ticket or cold call questions)
- Any misconceptions to watch for and how to address them

Keep all activities within the conceptual scope of this node. Do not introduce content from later nodes."""

                st.code(lesson_prompt, language=None)
                st.caption("Copy and paste into Claude.ai, ChatGPT, or Gemini.")

            st.divider()

    # ── PDF Export ────────────────────────────────────────────────────────────
    st.subheader("Export")
    if st.button("Generate PDF", type="primary", use_container_width=True):
        st.session_state.page = "pdf"
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "pdf":
    friction = st.session_state.friction_label
    selected_codes = st.session_state.selected_codes
    num_lessons = st.session_state.num_lessons
    prior = st.session_state.prior
    assessment_type = st.session_state.assessment_type
    prior_factor = {"Well below": 1.4, "Below": 1.2, "At": 1.0, "Above": 0.8}[prior]

    fc_pdf = {"Low": colors.HexColor("#2d5a3d"),
              "Typical": colors.HexColor("#7a5c00"),
              "Medium–High": colors.HexColor("#8b1a1a")}[friction]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    s_title = ParagraphStyle("t", fontSize=16, fontName="Helvetica-Bold", spaceAfter=4)
    s_sub = ParagraphStyle("s", fontSize=9, textColor=colors.grey, spaceAfter=10)
    s_h2 = ParagraphStyle("h2", fontSize=12, fontName="Helvetica-Bold", spaceAfter=4, spaceBefore=12)
    s_h3 = ParagraphStyle("h3", fontSize=10, fontName="Helvetica-Bold", spaceAfter=3, spaceBefore=6)
    s_body = ParagraphStyle("b", fontSize=9, spaceAfter=3, leading=13)
    s_small = ParagraphStyle("sm", fontSize=8, textColor=colors.HexColor("#555"), leading=11, spaceAfter=2)
    s_hinge = ParagraphStyle("hi", fontSize=8, textColor=fc_pdf, leading=11, fontName="Helvetica-Oblique")

    story = []
    story.append(Paragraph("X–Y Unit Planner", s_title))
    story.append(Paragraph(
        f"Year 7 Science · {', '.join(selected_codes)} · {num_lessons} lessons · "
        f"Assessment: {assessment_type} · Prior: {prior} · Friction: {friction}", s_sub))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.3*cm))

    friction_desc = {
        "Low": "Science exceeds GPA. Widen at hinge nodes. Offer all enrichment options.",
        "Typical": "Science aligned with GPA. Minimum width at most nodes. Selective enrichment at hinges.",
        "Medium–High": "Science below GPA. Stay near Xmin. Targeted supports. No enrichment until core is secure."
    }
    story.append(Paragraph(f"Friction strategy ({friction}): {friction_desc[friction]}", s_small))
    if st.session_state.mean_rfi is not None:
        story.append(Paragraph(f"Calculated Mean RFI: {st.session_state.mean_rfi:.2f}", s_small))
    story.append(Spacer(1, 0.4*cm))

    total_nodes = sum(len(standards_map[c]["nodes"]) for c in selected_codes if c in standards_map)
    base_lessons = num_lessons / total_nodes if total_nodes else 1

    # Summary table
    story.append(Paragraph("Sequence Overview", s_h2))
    summary_header = [["Standard", "Node", "Y Position", "Hinge", "Hinge Reason", "Width", "Lessons"]]
    summary_data = []
    for code in selected_codes:
        if code not in standards_map:
            continue
        for node in standards_map[code]["nodes"]:
            is_hinge = node["hinge"]
            n_lessons = node_lesson_budget(base_lessons * prior_factor, is_hinge)
            wl = width_level_label(friction, is_hinge)
            summary_data.append([
                code,
                str(node["id"]) + ". " + node["label"],
                node.get("y_description") or "",
                "Yes" if is_hinge else "",
                node.get("hinge_reason") or "",
                wl,
                str(n_lessons)
            ])

    all_rows = summary_header + summary_data
    col_widths = [1.8*cm, 4*cm, 4.5*cm, 1*cm, 4*cm, 2*cm, 1.2*cm]
    st_table = Table(all_rows, colWidths=col_widths)
    st_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(st_table)
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.3*cm))

    # Node detail
    for code in selected_codes:
        if code not in standards_map:
            continue
        std = standards_map[code]
        story.append(Paragraph(f"{std['code']} — {std['title']}", s_h2))
        story.append(Paragraph(f"Y-goal: {std['y_goal']}", s_small))
        story.append(Paragraph(f"Assumed prior: {std['prior_knowledge']}", s_small))
        story.append(Spacer(1, 0.2*cm))

        for node in std["nodes"]:
            is_hinge = node["hinge"]
            core_task, enrich_opts = width_emphasis(friction, node)
            n_lessons = node_lesson_budget(base_lessons * prior_factor, is_hinge)

            hinge_tag = " ⚑ HINGE" if is_hinge else ""
            header_row = [[
                Paragraph(f"Node {node['id']}: {node['label']}{hinge_tag}",
                          ParagraphStyle("nh", fontSize=10, fontName="Helvetica-Bold",
                                         textColor=fc_pdf if is_hinge else colors.black)),
                Paragraph(f"~{n_lessons} lesson{'s' if n_lessons != 1 else ''}",
                          ParagraphStyle("nl", fontSize=9, textColor=colors.grey))
            ]]
            ht = Table(header_row, colWidths=[14*cm, 3*cm])
            ht.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f5f1") if is_hinge else colors.HexColor("#f8f8f8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(ht)
            story.append(Paragraph(f"Y: {node.get('y_description', '')}", s_small))

            enrich_text = ("<br/>".join("• " + o for o in enrich_opts)
                           if enrich_opts else "<i>Not recommended at this friction level.</i>")
            content = [[
                Paragraph("±Xmin", s_h3), Paragraph("Core Width Task", s_h3), Paragraph("Enrichment Options", s_h3)
            ], [
                Paragraph(node["xmin"], s_body),
                Paragraph(core_task, s_body),
                Paragraph(enrich_text, s_small)
            ]]
            ct = Table(content, colWidths=[5.5*cm, 5.5*cm, 6*cm])
            ct.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
            ]))
            story.append(ct)

            if is_hinge and node.get("hinge_reason"):
                story.append(Paragraph(f"⚑ {node['hinge_reason']}", s_hinge))

            story.append(Spacer(1, 0.2*cm))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
        story.append(Spacer(1, 0.3*cm))

    doc.build(story)
    buf.seek(0)

    if st.button("← Back to Class Planning"):
        st.session_state.page = "s4_planning"
        st.rerun()

    st.download_button(
        label="⬇ Download PDF",
        data=buf,
        file_name=f"unit_plan_{'_'.join(selected_codes)}_{friction_label_short(friction)}.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )
    st.success("PDF ready — click above to download.")
    st.caption("This plan is a starting point. Teachers should adapt width options and lesson allocations to their class context.")