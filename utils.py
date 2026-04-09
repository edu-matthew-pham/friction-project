import json
import streamlit as st

# ── Load waypoint data from data/ folder ──────────────────────────────────────────
import os
import glob

@st.cache_data
def load_nodes():
    standards = []
    for fpath in sorted(glob.glob(os.path.join("data", "*.json"))):
        fname = os.path.basename(fpath)
        if fname in ("schema.json", "science_y_goals_map.json", "science_y_goals_map_schema.json"):
            continue
        with open(fpath) as f:
            d = json.load(f)
            standards.append(d["standard"])
    return {"standards": standards}

data = load_nodes()
standards_map = {s["code"]: s for s in data["standards"]}

# ── Helper functions ───────────────────────────────────────────────────────────
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
        warnings.append(f"⚠ Only {num_lessons} lessons for {total_nodes} waypoints — some waypoints will need to share a lesson.")
    for code in selected_codes:
        if code not in standards_map:
            continue
        for node in standards_map[code]["nodes"]:
            if node["hinge"] and node_lesson_budget(base, True) < 2:
                warnings.append(f"⚠ Hinge waypoint '{node['label']}' ({code}) has less than 2 lessons — consider increasing lesson count.")
    return warnings

# ── Session state defaults ─────────────────────────────────────────────────────
SESSION_DEFAULTS = {
    "page": "s0_welcome",
    "selected_codes": [],
    "num_lessons": 12,
    "assessment_type": "Test",
    "assessments": [],
    "friction_label": "Typical",
    "mean_rfi": None,
    "assessment_mode": "Draft new",
    "existing_task": "",
    "existing_summary": "",
    "existing_diagnostic": "",
    "last_diagnostic_prompt": "",
    "diagnostic_task": "",
    "diagnostic_ratings": {},
    "diagnostic_notes": "",
    "finalised_task": "",
    "last_assessment_prompt": "",
    "last_summary_prompt": "",
    "assessment_summary": "",
    "prior": "At",
}

def init_session_state():
    for key, val in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = val

# ── PDF Generation ─────────────────────────────────────────────────────────────
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

def generate_pdf(selected_codes, num_lessons, assessment_type, assessment_summary=""):
    """Generate a class-agnostic unit plan PDF showing all width levels."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    accent = colors.HexColor("#2d5a3d")
    s_title = ParagraphStyle("t", fontSize=16, fontName="Helvetica-Bold", spaceAfter=4)
    s_sub = ParagraphStyle("s", fontSize=9, textColor=colors.grey, spaceAfter=10)
    s_h2 = ParagraphStyle("h2", fontSize=12, fontName="Helvetica-Bold", spaceAfter=4, spaceBefore=12)
    s_h3 = ParagraphStyle("h3", fontSize=10, fontName="Helvetica-Bold", spaceAfter=3, spaceBefore=6)
    s_body = ParagraphStyle("b", fontSize=9, spaceAfter=3, leading=13)
    s_small = ParagraphStyle("sm", fontSize=8, textColor=colors.HexColor("#555"), leading=11, spaceAfter=2)
    s_hinge = ParagraphStyle("hi", fontSize=8, textColor=accent, leading=11, fontName="Helvetica-Oblique")

    story = []
    story.append(Paragraph("Learning Waypoints", s_title))
    story.append(Paragraph(
        f"Year 7 Science · {', '.join(selected_codes)} · {num_lessons} lessons · Assessment: {assessment_type}",
        s_sub))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph(
        "Width levels: Xmin = minimum before advancing · Core = standard construction · "
        "Enrich = richer construction of same concept. Circle the appropriate level for each class.",
        s_small))

    if assessment_summary.strip():
        story.append(Paragraph(f"Assessment summary: {assessment_summary}", s_small))

    story.append(Spacer(1, 0.4*cm))

    total_nodes = sum(len(standards_map[c]["nodes"]) for c in selected_codes if c in standards_map)
    base_lessons = num_lessons / total_nodes if total_nodes else 1

    # Summary table — all width levels shown
    story.append(Paragraph("Sequence Overview", s_h2))
    summary_header = [["Standard", "Waypoint", "Y Position", "Hinge", "Est. Lessons"]]
    summary_data = []
    for code in selected_codes:
        if code not in standards_map:
            continue
        for node in standards_map[code]["nodes"]:
            is_hinge = node["hinge"]
            n_lessons = node_lesson_budget(base_lessons, is_hinge)
            summary_data.append([
                code,
                str(node["id"]) + ". " + node["label"],
                node.get("y_description") or "",
                "⚑ Yes" if is_hinge else "",
                str(n_lessons)
            ])

    all_rows = summary_header + summary_data
    col_widths = [1.8*cm, 4.5*cm, 7*cm, 1.5*cm, 1.7*cm]
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

    # Waypoint detail — all three width levels per waypoint
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
            n_lessons = node_lesson_budget(base_lessons, is_hinge)
            enrich_opts = node.get("width_enrich_options", [])

            hinge_tag = " ⚑ HINGE" if is_hinge else ""
            header_row = [[
                Paragraph(f"Waypoint {node['id']}: {node['label']}{hinge_tag}",
                          ParagraphStyle("nh", fontSize=10, fontName="Helvetica-Bold",
                                         textColor=accent if is_hinge else colors.black)),
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
            if node.get("success_criteria"):
                story.append(Paragraph("✓ Success criteria:", s_small))
                for sc in node["success_criteria"]:
                    story.append(Paragraph("• " + sc, s_small))

            enrich_text = ("<br/>".join("• " + o for o in enrich_opts)
                          if enrich_opts else "<i>No enrichment options defined.</i>")
            content = [[
                Paragraph("±Xmin", s_h3),
                Paragraph("Core Width Task", s_h3),
                Paragraph("Enrichment Options", s_h3)
            ], [
                Paragraph(node["xmin"], s_body),
                Paragraph(node["width_core"], s_body),
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
    return buf

# ── Prior knowledge chain ──────────────────────────────────────────────────────
import glob as _glob

@st.cache_data
def load_y_goals_map():
    path = os.path.join("data", "science_y_goals_map.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def _search_tree(node, target, path):
    current = path + [node["code"]]
    if node["code"] == target:
        return current[:-1]
    for child in node.get("children", []):
        result = _search_tree(child, target, current)
        if result is not None:
            return result
    return None

def get_prior_chain(code):
    """Return ordered list of prior standards from Foundation up to (not including) this code."""
    y_goals_map = load_y_goals_map()
    threads = y_goals_map.get("progression_threads", {})
    ancestors = []
    for strand in threads.get("strands", {}).values():
        for root in strand["tree"]:
            result = _search_tree(root, code, [])
            if result is not None:
                ancestors = result
                break
        if ancestors:
            break

    chain = []
    for ancestor_code in ancestors:
        for yl, yl_data in y_goals_map.get("year_levels", {}).items():
            for std in yl_data.get("standards", []):
                if std["code"] == ancestor_code:
                    chain.append({
                        "code": ancestor_code,
                        "year_level": yl,
                        "title": std["title"],
                        "y_goal": std["y_goal"]
                    })
    return chain