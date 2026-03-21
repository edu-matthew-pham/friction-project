import streamlit as st
import pandas as pd
import json
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_LEFT

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

def friction_label_short(f):
    return {"Low": "low", "Typical": "typical", "Medium–High": "medium-high"}[f]

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("page", "setup"),
    ("friction_label", "Typical"),
    ("mean_rfi", None),
    ("selected_codes", []),
    ("num_lessons", 12),
    ("prior", "At"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("✦ X–Y Unit Planner")
st.caption("Year 7 Science · Friction Project POC")
st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 1 — CLASS SETUP
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "setup":

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Class Friction")

        uploaded = st.file_uploader("Upload class CSV", type="csv",
                                     help="Required columns: student_id, science_score, gpa")

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

        st.divider()
        st.markdown("**Override friction estimate**")
        friction_options = ["Low", "Typical", "Medium–High"]
        st.session_state.friction_label = st.radio(
            "Friction level",
            friction_options,
            index=friction_options.index(st.session_state.friction_label),
            captions=[
                "Science outperforming GPA — needs pace control",
                "Science aligned with GPA — standard pace",
                "Science underperforming GPA — needs consolidation",
            ]
        )

    with col2:
        st.subheader("2. Assessment Setup")

        all_titles = [f"{s['code']} — {s['title']}" for s in data["standards"]]
        selected_display = st.multiselect(
            "Standards covered by this assessment",
            options=all_titles,
            default=[all_titles[4], all_titles[5]]
        )
        selected_codes = [t.split(" — ")[0] for t in selected_display]

        num_lessons = st.number_input(
            "Number of lessons available",
            min_value=4, max_value=40, value=12, step=1
        )

        st.session_state.prior = st.select_slider(
            "Student prior knowledge vs ACARA assumption",
            options=["Well below", "Below", "At", "Above"],
            value=st.session_state.prior
        )

        st.divider()

        if selected_codes:
            total_nodes = sum(len(standards_map[c]["nodes"]) for c in selected_codes if c in standards_map)
            st.info(f"**{total_nodes} nodes** across {len(selected_codes)} standard(s) · ~**{num_lessons / total_nodes:.1f} lessons/node**")
        else:
            st.warning("Select at least one standard to continue.")

        if st.button("Generate Node Map →", type="primary",
                     disabled=not selected_codes, use_container_width=True):
            st.session_state.selected_codes = selected_codes
            st.session_state.num_lessons = num_lessons
            st.session_state.page = "nodemap"
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 2 — NODE MAP
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "nodemap":

    friction = st.session_state.friction_label
    selected_codes = st.session_state.selected_codes
    num_lessons = st.session_state.num_lessons
    prior = st.session_state.prior

    # Nav + summary
    col_back, col_info = st.columns([1, 4])
    with col_back:
        if st.button("← Back"):
            st.session_state.page = "setup"
            st.rerun()
    with col_info:
        st.subheader(f"Node Map — {', '.join(selected_codes)}")
        st.caption(f"{num_lessons} lessons · Prior knowledge: {prior} · Friction: **{friction}**")

    # Friction guidance
    guidance = {
        "Low": "**Low friction:** Keep early nodes near ±Xmin. Widen at hinge nodes. All enrichment options available.",
        "Typical": "**Typical friction:** Minimum width at most nodes. Selective enrichment at hinge nodes only.",
        "Medium–High": "**Medium–High friction:** Stay near ±Xmin throughout. Targeted supports. No enrichment until core is secure."
    }
    st.info(guidance[friction])

    if st.session_state.mean_rfi is not None:
        st.caption(f"Calculated Mean RFI: {st.session_state.mean_rfi:.2f} (GPA-adjusted method)")

    st.divider()

    # Lesson budget
    total_nodes = sum(len(standards_map[c]["nodes"]) for c in selected_codes if c in standards_map)
    base_lessons = num_lessons / total_nodes if total_nodes else 1
    prior_factor = {"Well below": 1.4, "Below": 1.2, "At": 1.0, "Above": 0.8}[prior]

    # Summary overview table
    st.subheader("Sequence Overview")
    summary_rows = []
    for code in selected_codes:
        if code not in standards_map:
            continue
        for node in standards_map[code]["nodes"]:
            is_hinge = node["hinge"]
            node_lessons = max(1, round(base_lessons * prior_factor * (1.3 if is_hinge else 1.0)))
            if friction == "Low":
                width_level = "Enrich" if is_hinge else "Core"
            elif friction == "Medium–High":
                width_level = "Core" if is_hinge else "Xmin"
            else:
                width_level = "Core + Enrich" if is_hinge else "Core"
            summary_rows.append({
                "Standard": code,
                "Node": str(node["id"]) + ". " + node["label"],
                "Y Position": node.get("y_description") or "",
                "Hinge": "Yes" if is_hinge else "",
                "Hinge Reason": node.get("hinge_reason") or "",
                "Width Level": width_level,
                "Lessons": node_lessons,
            })
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True,
        column_config={
            "Node": st.column_config.TextColumn(width="medium"),
            "Y Position": st.column_config.TextColumn(width="large"),
            "Hinge": st.column_config.TextColumn(width="small"),
            "Hinge Reason": st.column_config.TextColumn(width="large"),
            "Width Level": st.column_config.TextColumn(width="medium"),
            "Lessons": st.column_config.NumberColumn(width="small"),
        }
    )
    st.divider()

    # Render nodes
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
            node_lessons = max(1, round(base_lessons * prior_factor * (1.3 if is_hinge else 1.0)))

            # Node header
            label = f"{'⚑ HINGE — ' if is_hinge else ''}Node {node['id']}: {node['label']}  ·  ~{node_lessons} lesson{'s' if node_lessons != 1 else ''}"
            if is_hinge:
                st.warning(label)
            else:
                st.markdown(f"**{label}**")

            # Node content in columns
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
                    value=node_lessons,
                    key=f"lessons_{node_key}"
                )
                enrich_text = (
                    "\n".join("- " + o for o in enrich_opts)
                    if enrich_opts else "Not applicable at this friction level."
                )
                hinge_text = (
                    f"\nIMPORTANT — This is a hinge concept: {node['hinge_reason']}"
                    if is_hinge else ""
                )
                friction_guidance_map = {
                    "Low": "Students are likely to move quickly. Prioritise enrichment options to deepen construction. Avoid racing ahead to the next node.",
                    "Typical": "Maintain minimum width at this node. Use the core width task. Add enrichment only if time allows.",
                    "Medium-High": "Stay near Xmin. Use targeted supports — worked examples, misconception repair, structured sentence starters. Do not widen prematurely.",
                    "Medium–High": "Stay near Xmin. Use targeted supports — worked examples, misconception repair, structured sentence starters. Do not widen prematurely."
                }
                friction_guidance = friction_guidance_map.get(friction, "Use the core width task.")
                lesson_prompt = f"""You are helping a Year 7 Science teacher plan lessons for a single conceptual node.

CONTEXT
──────────────────────────────────
Subject: Year 7 Science
Standard: {code}
Node: {node['id']}. {node['label']}
Class Friction: {friction}
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
{enrich_text}{hinge_text}

FRICTION GUIDANCE
──────────────────────────────────
{friction_guidance}

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
                st.caption("Copy the prompt above and paste into Claude.ai, ChatGPT, or Gemini.")

            st.divider()

    if st.button("Generate PDF →", type="primary", use_container_width=True):
        st.session_state.page = "pdf"
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 3 — PDF EXPORT
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "pdf":

    friction = st.session_state.friction_label
    selected_codes = st.session_state.selected_codes
    num_lessons = st.session_state.num_lessons
    prior = st.session_state.prior
    prior_factor = {"Well below": 1.4, "Below": 1.2, "At": 1.0, "Above": 0.8}[prior]

    fc_pdf = {"Low": colors.HexColor("#2d5a3d"),
              "Typical": colors.HexColor("#7a5c00"),
              "Medium–High": colors.HexColor("#8b1a1a")}[friction]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
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
        f"Prior: {prior} · Friction: {friction}", s_sub))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.3*cm))

    friction_desc = {
        "Low": "Science exceeds GPA. Widen at hinge nodes. Offer all enrichment options.",
        "Typical": "Science aligned with GPA. Minimum width at most nodes. Selective enrichment at hinges.",
        "Medium–High": "Science below GPA. Stay near ±Xmin. Targeted supports. No enrichment until core is secure."
    }
    story.append(Paragraph(f"Friction strategy ({friction}): {friction_desc[friction]}", s_small))
    if st.session_state.mean_rfi is not None:
        story.append(Paragraph(f"Calculated Mean RFI: {st.session_state.mean_rfi:.2f}", s_small))
    story.append(Spacer(1, 0.4*cm))

    total_nodes = sum(len(standards_map[c]["nodes"]) for c in selected_codes if c in standards_map)
    base_lessons = num_lessons / total_nodes if total_nodes else 1

    # Summary table in PDF
    story.append(Paragraph("Sequence Overview", s_h2))
    summary_header = [["Standard", "Node", "Y Position", "Hinge", "Hinge Reason", "Width Level", "Lessons"]]
    summary_data = []
    for code in selected_codes:
        if code not in standards_map:
            continue
        for node in standards_map[code]["nodes"]:
            is_hinge = node["hinge"]
            node_lessons = max(1, round(base_lessons * prior_factor * (1.3 if is_hinge else 1.0)))
            if friction == "Low":
                wl = "Enrich" if is_hinge else "Core"
            elif friction == "Medium–High":
                wl = "Core" if is_hinge else "Xmin"
            else:
                wl = "Core+Enrich" if is_hinge else "Core"
            summary_data.append([code, str(node["id"]) + ". " + node["label"],
                                 node.get("y_description") or "",
                                 "Yes" if is_hinge else "",
                                 node.get("hinge_reason") or "",
                                 wl, str(node_lessons)])
    all_rows = summary_header + summary_data
    col_widths = [1.8*cm, 4*cm, 4.5*cm, 1*cm, 4*cm, 2*cm, 1.2*cm]
    st_table = Table(all_rows, colWidths=col_widths)
    st_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eeeeee")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cccccc")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(st_table)
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.3*cm))

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
            node_lessons = max(1, round(base_lessons * prior_factor * (1.3 if is_hinge else 1.0)))

            hinge_tag = " ⚑ HINGE" if is_hinge else ""
            header_row = [[
                Paragraph(f"Node {node['id']}: {node['label']}{hinge_tag}",
                          ParagraphStyle("nh", fontSize=10, fontName="Helvetica-Bold",
                                         textColor=fc_pdf if is_hinge else colors.black)),
                Paragraph(f"~{node_lessons} lesson{'s' if node_lessons != 1 else ''}",
                          ParagraphStyle("nl", fontSize=9, textColor=colors.grey))
            ]]
            ht = Table(header_row, colWidths=[14*cm, 3*cm])
            ht.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f0f5f1") if is_hinge else colors.HexColor("#f8f8f8")),
                ("LEFTPADDING", (0,0), (-1,-1), 8),
                ("RIGHTPADDING", (0,0), (-1,-1), 8),
                ("TOPPADDING", (0,0), (-1,-1), 5),
                ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ]))
            story.append(ht)

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
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eeeeee")),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,0), 8),
                ("LEFTPADDING", (0,0), (-1,-1), 6),
                ("RIGHTPADDING", (0,0), (-1,-1), 6),
                ("TOPPADDING", (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#dddddd")),
            ]))
            story.append(ct)

            if is_hinge and node.get("hinge_reason"):
                story.append(Paragraph(f"⚑ {node['hinge_reason']}", s_hinge))

            story.append(Spacer(1, 0.2*cm))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
        story.append(Spacer(1, 0.3*cm))

    doc.build(story)
    buf.seek(0)

    if st.button("← Back to Node Map"):
        st.session_state.page = "nodemap"
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