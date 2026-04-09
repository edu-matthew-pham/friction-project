"""
Prompt builder for Learning Waypoints.
Templates live in prompts/templates/*.md — edit them directly to adjust prompt text.
This file handles data preparation and template filling only.
"""
import os
from utils import standards_map, get_prior_chain

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _load(name):
    with open(os.path.join(TEMPLATE_DIR, f"{name}.md")) as f:
        return f.read()


def _build_context(selected_codes):
    """Shared context fields used by assessment and diagnostic prompts."""
    hinge_nodes, y_goals, sc_lines, prior_lines = [], [], [], []
    for code in selected_codes:
        if code not in standards_map:
            continue
        std = standards_map[code]
        y_goals.append(f"{code}: {std['y_goal']}")
        for node in std["nodes"]:
            if node["hinge"]:
                hinge_nodes.append(f"- Waypoint {node['id']} ({code}): {node['label']} — {node.get('hinge_reason', '')}")
            sc = node.get("success_criteria", [])
            if sc:
                sc_lines.append(f"Waypoint {node['id']} ({code}) — {node['label']}:")
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


def build_diagnostic_prompt(selected_codes, existing_diagnostic=""):
    ctx = _build_context(selected_codes)

    xmin_lines = []
    for code in selected_codes:
        if code not in standards_map:
            continue
        std = standards_map[code]
        xmin_lines.append(f"{code} — {std['title']}:")
        for node in std["nodes"]:
            xmin_lines.append(f"  Waypoint {node['id']}: {node['xmin']}")

    if existing_diagnostic.strip():
        task_instruction = (
            f"EXISTING DIAGNOSTIC TASK TO REVIEW\n"
            f"──────────────────────────────────\n"
            f"{existing_diagnostic}\n\n"
            f"YOUR TASK\n"
            f"──────────────────────────────────\n"
            f"Review and improve the existing diagnostic task. Ensure it:\n"
            f"- Targets prior knowledge from the pathway above, not Y7 content\n"
            f"- Is completable in 10–15 minutes\n"
            f"- Surfaces common misconceptions and gaps\n"
            f"- Generates actionable information for the teacher"
        )
    else:
        task_instruction = (
            f"YOUR TASK\n"
            f"──────────────────────────────────\n"
            f"Design a short pre-unit diagnostic task (10–15 minutes) that:\n"
            f"- Targets prior knowledge from the pathway above, not Y7 content\n"
            f"- Surfaces what students already know and common misconceptions\n"
            f"- Is accessible to all students regardless of prior achievement\n"
            f"- Generates actionable information: teacher can identify students who need more consolidation at early waypoints\n"
            f"- Is not a test — frame it as a curiosity or thinking task"
        )

    return _load("diagnostic").format(
        standards=", ".join(selected_codes),
        prior_text=ctx["prior_text"],
        xmin_text="\n".join(xmin_lines) if xmin_lines else "None defined",
        y_goal_text=ctx["y_goal_text"],
        task_instruction=task_instruction,
    )


def build_assessment_prompt(selected_codes, assessments, existing_tasks, existing_summary):
    ctx = _build_context(selected_codes)

    items_text = "\n".join(f"- {a['label']}: {a['type']} · {a.get('reported', 'Summative')} · {a['timing']}" for a in assessments)

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
                "This is a MID-UNIT assessment — cover waypoints taught so far, not the full unit."
                if a["timing"] == "Mid-unit"
                else "This is an END-OF-UNIT assessment — cover all waypoints in the unit."
            )
            reported = a.get("reported", "Summative")
            if reported == "Formative":
                task_instructions.append(
                    f"OUTPUT {a['id']} — DRAFT: {a['label']} ({a['type']}, Formative, {a['timing']})\n"
                    f"{timing_note}\n"
                    f"Design a short formative checkpoint (10–15 minutes) that:\n"
                    f"- Tests Xmin success criteria for waypoints covered so far\n"
                    f"- Is not reported — framed as a learning check, not a grade\n"
                    f"- Gives the teacher a quick class-level picture of gaps\n"
                    f"- Uses low-stakes formats: exit ticket, quick sketch, short response, sorting task"
                )
            else:
                task_instructions.append(
                    f"OUTPUT {a['id']} — DRAFT: {a['label']} ({a['type']}, Summative, {a['timing']})\n"
                    f"{timing_note}\n"
                    f"Draft a complete assessment task with:\n"
                    f"  Section A — Xmin (~60%): compulsory, tests minimum construction\n"
                    f"  Section B — X+ (~30%): same concepts, broader integration\n"
                    f"  Section C — X++ (~10%): open-access transfer and synthesis\n"
                    f"Do not exceed Y-goals. Do not label any section as 'extension'."
                )

    summary_instruction = (
        f"FINAL OUTPUT — REVISED SUMMARY\nExisting summary to review:\n{existing_summary}\nRevise to cover all assessment items above."
        if existing_summary.strip()
        else "FINAL OUTPUT — COMBINED SUMMARY (150 words max)\nSummarise all assessment items for lesson planning. Include:\n- Each item's type, timing and format\n- Key concepts per section (A/B/C) for each item\n- Which hinge concepts are tested and in which item\n- Mark weighting per section"
    )

    return _load("assessment").format(
        standards=", ".join(selected_codes),
        items_text=items_text,
        y_goal_text=ctx["y_goal_text"],
        prior_text=ctx["prior_text"],
        hinge_text=ctx["hinge_text"],
        sc_text=ctx["sc_text"],
        task_instructions="\n\n".join(task_instructions),
        summary_instruction=summary_instruction,
    )


def build_lesson_prompt(code, node, friction, assessment_type, override_lessons,
                        enrich_opts, assessments, assessment_summary, diagnostic_ratings, diagnostic_notes):

    # Prior knowledge chain with ratings
    prior_chain = get_prior_chain(code)
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

    # Y7 waypoint progress
    y7_waypoint_lines = []
    for n in standards_map[code]["nodes"]:
        nkey = f"diag_y7_{code}_node_{n['id']}"
        nrating = diagnostic_ratings.get(nkey, "🔴 Gap")
        marker = " → THIS WAYPOINT" if n["id"] == node["id"] else ""
        y7_waypoint_lines.append(f"Waypoint {n['id']}: {n['label']} [{nrating}]{marker}")
    y7_waypoints_text = "\n".join(y7_waypoint_lines)

    # Friction-aware success criteria
    sc_xmin = node.get("success_criteria", [])
    sc_lines = ["Xmin (target for all students):"]
    sc_lines += ["- " + sc for sc in sc_xmin]
    if friction in ["Steady", "Advancing"] and node.get("width_core"):
        sc_lines += ["", "X+ (target for this class — core width):"]
        sc_lines += ["- Demonstrate: " + node["width_core"]]
    if friction == "Advancing" and enrich_opts:
        sc_lines += ["", "X++ (target for this class — enrichment):"]
        sc_lines += ["- Demonstrate: " + enrich_opts[0]]
    sc_text = "\n".join(sc_lines)

    core_task = node.get("width_core", "") if friction != "Consolidating" else node.get("xmin", "")
    enrich_text = "\n".join("- " + o for o in enrich_opts) if enrich_opts else "Not applicable at this friction level."
    hinge_note = f"\nIMPORTANT — This is a hinge concept: {node['hinge_reason']}" if node.get("hinge") and node.get("hinge_reason") else ""

    friction_guidance = {
        "Advancing": "Students are likely to move quickly. Prioritise enrichment options to deepen construction. Avoid racing ahead to the next waypoint.",
        "Steady": "Maintain minimum width at this waypoint. Use the core width task. Add enrichment only if time allows.",
        "Consolidating": "Stay near Xmin. Use targeted supports — worked examples, misconception repair, structured sentence starters. Do not widen prematurely."
    }.get(friction, "Use the core width task.")

    assessment_items_text = "\n".join(
        f"- {a['label']}: {a['type']} · {a.get('reported', 'Summative')} · {a['timing']}" for a in assessments
    ) if assessments else f"- {assessment_type}"

    task_context = (
        f"\nASSESSMENT SUMMARY\n" + "─" * 34 + f"\n{assessment_summary}"
        if assessment_summary.strip() else ""
    )

    return _load("lesson").format(
        code=code,
        waypoint_id=node["id"],
        waypoint_label=node["label"],
        friction=friction,
        assessment_type=assessment_type,
        override_lessons=override_lessons,
        y_description=node["y_description"],
        prior_chain_text=prior_chain_text,
        y7_waypoints_text=y7_waypoints_text,
        sc_text=sc_text,
        xmin=node["xmin"],
        core_task=core_task,
        enrich_text=enrich_text,
        hinge_note=hinge_note,
        friction_guidance=friction_guidance,
        assessment_items_text=assessment_items_text,
        task_context=task_context,
    )