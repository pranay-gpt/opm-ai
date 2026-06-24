"""opm_ai.chat.app — Streamlit entry point (placeholder).

This file is the Docker CMD target. It will grow into the full
conversational UI in Part 6. For now it confirms the container
starts cleanly and all imports resolve.
"""
import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(
    page_title="opm-ai",
    page_icon="🛢️",
    layout="wide",
)

st.title("🛢️ opm-ai")
st.subheader("AI-Assisted Reservoir Simulation Workbench")

st.info(
    "**Status:** Skeleton running. Full chat UI coming in Part 6.\n\n"
    "Modules being built:\n"
    "- Part 1 — OPM Runner\n"
    "- Part 2 — Deck Linter\n"
    "- Part 3 — Deck Builder\n"
    "- Part 4 — Pre-Processing\n"
    "- Part 5 — ResInsight Bridge\n"
    "- Part 6 — Chat UI (this file)\n"
    "- Part 7 — Educational Explainer"
)

# Environment check
st.divider()
st.markdown("### Environment Check")

checks = {
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    "TAVILY_API": os.getenv("TAVILY_API"),
    "NVIDIA_NIM_API": os.getenv("NVIDIA_NIM_API"),
    "OPM_FLOW_BINARY": os.getenv("OPM_FLOW_BINARY", "/usr/bin/flow"),
    "RESINSIGHT_EXECUTABLE": os.getenv("RESINSIGHT_EXECUTABLE", "/usr/bin/ResInsight"),
}

for key, val in checks.items():
    if val:
        st.success(f"✅ {key} — set")
    else:
        st.warning(f"⚠️ {key} — not set (add to .env)")
