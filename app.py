import streamlit as st

st.set_page_config(page_title="X–Y Unit Planner", page_icon="✦", layout="wide")

st.title("✦ X–Y Unit Planner")
st.caption("Friction Project · POC")

st.divider()

col1, col2 = st.columns([1, 1.6])

with col1:
    st.subheader("Unit Details")

    subject = st.selectbox("Subject", ["Science", "Mathematics", "Humanities (HASS)", "Digital Technologies", "English", "Other"])
    year = st.selectbox("Year Level", [7, 8, 9, 10], index=2)
    acara = st.text_input("ACARA Standard Code", placeholder="e.g. AC9S9U01")
    acara_desc = st.text_area("Standard Description (optional)", placeholder="Paste the achievement standard text…", height=100)

    st.divider()
    st.subheader("Class Friction Estimate")

    friction = st.radio(
        "Select friction level",
        ["Low", "Typical", "Medium–High"],
        index=1,
        captions=[
            "Fast movers, needs pace control",
            "Standard pace, selective enrichment",
            "Needs consolidation support"
        ]
    )

    generate = st.button("Generate Prompt", type="primary", use_container_width=True)

with col2:
    st.subheader("Your Prompt")

    if generate:
        friction_map = {
            "Low": "LOW FRICTION — Keep early widths near minimum. Significantly widen at hinge concepts to absorb momentum. Push integration, transfer, and synthesis in enrichment tasks.",
            "Typical": "TYPICAL FRICTION — Maintain minimum width at most nodes. Add selective enrichment at hinge concepts. Balance consolidation with forward momentum.",
            "Medium–High": "MEDIUM–HIGH FRICTION — Stay near ±Xmin at each node. Use targeted supports (worked examples, misconception repair, structured prompts). Keep vertical pace steady; do not widen prematurely."
        }

        prompt = f"""You are helping a teacher plan a unit using the X–Y Constructivist Model.

CONTEXT
──────────────────────────────────
Subject: {subject}
Year Level: {year}
ACARA Standard: {acara or '[ACARA CODE]'}{chr(10) + 'Standard Description: ' + acara_desc if acara_desc else ''}
Class Friction: {friction}

ABOUT THE X–Y MODEL
──────────────────────────────────
- Y-axis = conceptual progression. Nodes are distinct concepts in sequence from assumed prior knowledge to the shared curriculum endpoint.
- X-axis = conceptual construction at a node. Every node has a MINIMUM WIDTH (±Xmin) — the floor of understanding required before advancing — plus optional extended and synthetic width.
- Friction = how readily this class will move through nodes. It determines how width is distributed, not how far concepts go.
- The conceptual endpoint (Y-goal) is FIXED for all students. Differentiation happens only through width, never by changing which concepts are reached.
- Hinge concepts: nodes where misconceptions cluster, later nodes depend on them, and extra width investment here pays off disproportionately downstream.

CLASS FRICTION STRATEGY
──────────────────────────────────
{friction_map[friction]}

YOUR TASK
──────────────────────────────────
Generate a complete unit plan. Structure your response as follows:

## 1. ASSUMED PRIOR KNOWLEDGE (Start Node)
Briefly describe what students are expected to know before this unit begins.

## 2. SHARED CONCEPTUAL ENDPOINT (Y-Goal)
State the fixed curriculum endpoint all students will be assessed against.

## 3. NODE MAP
List 6–8 nodes in sequence. For each node:

Node [N]: [Label]
- ±Xmin: [Minimum construction — what a student must do before advancing]
- Core width task: [Same concept, standard construction]
- Enrich width task: [Same concept, richer construction — NOT new content]
- Hinge concept: [Yes/No — if Yes, explain why briefly]

## 4. ASSESSMENT STRUCTURE
Section A — Core Width (~60% of marks)
Section B — Extended Width (~30% of marks)
Section C — Synthetic Width (~10% of marks)

IMPORTANT RULES
──────────────────────────────────
- Mark exactly 1–2 nodes as hinge concepts
- Enrich tasks must deepen the SAME concept, not introduce adjacent content
- Width strategy must reflect the friction level: {friction}
- The Y-goal is non-negotiable — do not extend beyond the ACARA standard"""

        st.code(prompt, language=None)

        st.success("Prompt ready — copy and paste into Claude.ai, ChatGPT, or Gemini (free tier)")

    else:
        st.info("Fill in unit details and click **Generate Prompt**")