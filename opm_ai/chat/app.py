"""
OPM-AI Streamlit Application

PewDiePie Odyssey-inspired minimal UI:
- Left sidebar: function selector nav + provider settings + theme switcher
- Main area: context-aware panel for the selected function
- Chat panel: streaming LLM with tool call badges
- Plots panel: interactive Plotly charts
- Deck builder: syntax-highlighted editor
- Results: KPI grid + plot viewer

Run:
    streamlit run opm_ai/chat/app.py

Environment variables:
    GROQ_API_KEY    — Groq free tier
    NVIDIA_API_KEY  — NVIDIA NIM free tier (Nemotron-Ultra-253B)
"""

import os
import json
from pathlib import Path
from typing import Any

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="OPM-AI",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from opm_ai.chat.themes import THEMES, get_theme_css
from opm_ai.chat.providers import PROVIDERS

# ── Session state bootstrap ───────────────────────────────────────────────────
DEFAULTS = {
    "active_view": "chat",
    "messages": [],
    "llm_provider": "groq",
    "selected_model": PROVIDERS["groq"].default_model,
    "theme": "Dark Void",
    "drive_mechanism": None,
    "drive_confirmed": False,
    "active_case": None,
    "active_deck": None,
    "active_deck_path": None,
    "active_result_path": None,
    "last_tool_called": None,
    "last_kpis": None,
    "last_plots": [],
    "pending_kb_questions": [],
    "runspec_params": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Inject theme CSS ──────────────────────────────────────────────────────────
st.markdown(get_theme_css(st.session_state.theme), unsafe_allow_html=True)

# ── System prompt loader ──────────────────────────────────────────────────────
@st.cache_resource
def load_system_prompt() -> str:
    sp = Path(__file__).parent / "system_prompt.md"
    if sp.exists():
        return sp.read_text(encoding="utf-8")
    return "You are OPM-AI, an expert reservoir simulation assistant."

SYSTEM_PROMPT = load_system_prompt()

# ── Nav items ─────────────────────────────────────────────────────────────────
NAV_ITEMS = [
    {"id": "chat",       "icon": "💬", "label": "Chat",         "desc": "Talk to the AI"},
    {"id": "results",    "icon": "📊", "label": "Results",      "desc": "KPIs & plots"},
    {"id": "deck",       "icon": "📝", "label": "Deck Builder",  "desc": "Build .DATA files"},
    {"id": "run",        "icon": "▶️", "label": "Run Simulation","desc": "OPM Flow runner"},
    {"id": "explain",    "icon": "🎓", "label": "Explain",       "desc": "Concept explainer"},
    {"id": "settings",   "icon": "⚙️", "label": "Settings",      "desc": "API keys & config"},
]

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo
    st.markdown(
        """
        <div style='display:flex;align-items:center;gap:10px;padding:16px 4px 8px;'>
            <div style='font-size:28px;'>🛢️</div>
            <div>
                <div style='font-size:16px;font-weight:700;color:var(--text);letter-spacing:-0.3px;'>OPM-AI</div>
                <div style='font-size:11px;color:var(--muted);'>Reservoir Intelligence</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-header">Navigation</div>', unsafe_allow_html=True)

    # Nav buttons
    for item in NAV_ITEMS:
        is_active = st.session_state.active_view == item["id"]
        active_cls = "active" if is_active else ""
        if st.button(
            f"{item['icon']}  {item['label']}",
            key=f"nav_{item['id']}",
            use_container_width=True,
            help=item["desc"],
        ):
            st.session_state.active_view = item["id"]
            st.rerun()

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-header">LLM Provider</div>', unsafe_allow_html=True)

    # Provider selector
    provider_names = list(PROVIDERS.keys())
    provider_labels = [f"{PROVIDERS[p].badge} {PROVIDERS[p].label}" for p in provider_names]
    current_idx = provider_names.index(st.session_state.llm_provider)
    selected_provider_label = st.selectbox(
        "Provider",
        provider_labels,
        index=current_idx,
        label_visibility="collapsed",
        key="provider_select",
    )
    selected_provider_name = provider_names[provider_labels.index(selected_provider_label)]
    if selected_provider_name != st.session_state.llm_provider:
        st.session_state.llm_provider = selected_provider_name
        st.session_state.selected_model = PROVIDERS[selected_provider_name].default_model
        st.rerun()

    # Model selector
    provider_cfg = PROVIDERS[st.session_state.llm_provider]
    model_list = provider_cfg.models
    current_model = st.session_state.selected_model
    if current_model not in model_list:
        current_model = model_list[0]
    model_idx = model_list.index(current_model)
    selected_model = st.selectbox(
        "Model",
        model_list,
        index=model_idx,
        label_visibility="collapsed",
        key="model_select",
    )
    st.session_state.selected_model = selected_model

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-header">Theme</div>', unsafe_allow_html=True)

    theme_names = list(THEMES.keys())
    theme_labels = [f"{THEMES[t]['emoji']}  {t}" for t in theme_names]
    current_theme_label = f"{THEMES[st.session_state.theme]['emoji']}  {st.session_state.theme}"
    selected_theme_label = st.selectbox(
        "Theme",
        theme_labels,
        index=theme_labels.index(current_theme_label),
        label_visibility="collapsed",
        key="theme_select",
    )
    selected_theme = theme_names[theme_labels.index(selected_theme_label)]
    if selected_theme != st.session_state.theme:
        st.session_state.theme = selected_theme
        st.rerun()

    # Active case indicator
    if st.session_state.active_case:
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown(
            f"<div class='card-sm'>📂 <b>Case:</b> {Path(st.session_state.active_case).name}</div>",
            unsafe_allow_html=True,
        )

    # Drive mechanism indicator
    if st.session_state.drive_mechanism:
        dm = st.session_state.drive_mechanism.replace("_", " ").title()
        confirmed = "✅" if st.session_state.drive_confirmed else "❓"
        st.markdown(
            f"<div class='card-sm'>{confirmed} <b>Drive:</b> {dm}</div>",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: get LLM router (cached per session to avoid re-init)
# ─────────────────────────────────────────────────────────────────────────────
def get_router():
    """Build the LLM router. Returns None with an error message if API key missing."""
    try:
        from opm_ai.chat.llm_router import LLMRouter
        return LLMRouter(
            provider_name=st.session_state.llm_provider,
            model=st.session_state.selected_model,
        ), None
    except ValueError as e:
        return None, str(e)
    except Exception as e:  # noqa: BLE001
        return None, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: CHAT
# ─────────────────────────────────────────────────────────────────────────────
def view_chat():
    st.markdown(
        "<h2 style='font-size:20px;font-weight:700;margin-bottom:16px;color:var(--text);'>💬 Chat with OPM-AI</h2>",
        unsafe_allow_html=True,
    )

    # Provider badge
    p = PROVIDERS[st.session_state.llm_provider]
    st.markdown(
        f"<div class='provider-badge'>{p.badge} {p.label} &nbsp;·&nbsp; {st.session_state.selected_model}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Chat history
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                st.markdown(
                    f"<div class='msg-user'><div class='bubble'>{content}</div></div>",
                    unsafe_allow_html=True,
                )
            elif role == "assistant" and content:
                st.markdown(
                    f"<div class='msg-ai'><div class='avatar'>🛢️</div><div class='bubble'>{content}</div></div>",
                    unsafe_allow_html=True,
                )
            elif role == "tool_call_indicator":
                st.markdown(
                    f"<div class='tool-call-badge'>⚙️ called: {content}</div>",
                    unsafe_allow_html=True,
                )

    # Input row
    col_input, col_send = st.columns([6, 1])
    with col_input:
        user_input = st.text_input(
            "Message",
            placeholder="Ask about your simulation, request a deck, analyze results…",
            label_visibility="collapsed",
            key="chat_input",
        )
    with col_send:
        send = st.button("Send", use_container_width=True, key="chat_send")

    col_clear, _ = st.columns([2, 8])
    with col_clear:
        if st.button("Clear chat", key="chat_clear"):
            st.session_state.messages = []
            st.rerun()

    if send and user_input.strip():
        # Append user message
        st.session_state.messages.append({"role": "user", "content": user_input.strip()})

        router, err = get_router()
        if err:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"⚠️ **API key error:** {err}\n\nSet `{PROVIDERS[st.session_state.llm_provider].api_key_env}` in your environment.",
            })
            st.rerun()
            return

        # Build message list for LLM
        llm_msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in st.session_state.messages:
            if m["role"] in ("user", "assistant") and m.get("content"):
                llm_msgs.append({"role": m["role"], "content": m["content"]})

        # Stream response
        with st.spinner("Thinking…"):
            full_response = ""
            placeholder = st.empty()
            for chunk in router.chat(llm_msgs, st.session_state):
                full_response += chunk
                placeholder.markdown(
                    f"<div class='msg-ai'><div class='avatar'>🛢️</div><div class='bubble'>{full_response}▌</div></div>",
                    unsafe_allow_html=True,
                )

        placeholder.empty()
        st.session_state.messages.append({"role": "assistant", "content": full_response})

        # Add tool call badge if tool was invoked
        if st.session_state.last_tool_called:
            st.session_state.messages.append({
                "role": "tool_call_indicator",
                "content": st.session_state.last_tool_called,
            })
            st.session_state.last_tool_called = None

        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: RESULTS
# ─────────────────────────────────────────────────────────────────────────────
def view_results():
    st.markdown(
        "<h2 style='font-size:20px;font-weight:700;margin-bottom:16px;color:var(--text);'>📊 Simulation Results</h2>",
        unsafe_allow_html=True,
    )

    # Drive mechanism identification card
    if not st.session_state.drive_confirmed:
        st.markdown(
            """
            <div class='card'>
                <div style='font-size:15px;font-weight:600;color:var(--text);margin-bottom:8px;'>🔍 Drive Mechanism Identification</div>
                <div style='font-size:13px;color:var(--muted);'>Before plotting, OPM-AI needs to confirm the reservoir drive mechanism.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        drive_options = [
            ("solution_gas", "💨 Solution Gas Drive (Depletion)"),
            ("gas_cap", "⛽ Gas Cap Drive"),
            ("water_drive", "💧 Water Drive"),
            ("combination", "🔄 Combination Drive"),
            ("gravity_drainage", "⬇️ Gravity Drainage"),
            ("waterflood", "🌊 Waterflood (IOR)"),
            ("eor", "🧪 EOR (Chemical/Thermal)"),
        ]
        selected_drive = st.selectbox(
            "Select drive mechanism",
            [d[0] for d in drive_options],
            format_func=lambda x: next(d[1] for d in drive_options if d[0] == x),
            key="drive_select",
        )
        if st.button("✅ Confirm Drive Mechanism", key="confirm_drive"):
            st.session_state.drive_mechanism = selected_drive
            st.session_state.drive_confirmed = True
            st.rerun()
        return

    dm = st.session_state.drive_mechanism.replace("_", " ").title()
    st.markdown(
        f"<div class='card-sm'>✅ Drive Mechanism: <b>{dm}</b></div>",
        unsafe_allow_html=True,
    )

    # KPI grid
    if st.session_state.last_kpis:
        st.markdown(
            "<div style='font-size:13px;font-weight:600;color:var(--muted);margin:16px 0 8px;text-transform:uppercase;letter-spacing:0.05em;'>Key Performance Indicators</div>",
            unsafe_allow_html=True,
        )
        kpis = st.session_state.last_kpis
        kpi_dict = kpis.to_dict() if hasattr(kpis, "to_dict") else {}
        if kpi_dict:
            cols = st.columns(min(4, len(kpi_dict)))
            for i, (k, v) in enumerate(kpi_dict.items()):
                with cols[i % len(cols)]:
                    st.metric(k.replace("_", " ").title(), f"{v:.3g}" if isinstance(v, float) else v)

    # Plot viewer
    if st.session_state.last_plots:
        st.markdown(
            "<div style='font-size:13px;font-weight:600;color:var(--muted);margin:16px 0 8px;text-transform:uppercase;letter-spacing:0.05em;'>Interactive Plots</div>",
            unsafe_allow_html=True,
        )
        plot_tabs = st.tabs([p.get("title", f"Plot {i+1}") for i, p in enumerate(st.session_state.last_plots)])
        for tab, plot_data in zip(plot_tabs, st.session_state.last_plots):
            with tab:
                if "fig" in plot_data:
                    st.plotly_chart(plot_data["fig"], use_container_width=True)
                elif "html" in plot_data:
                    st.components.v1.html(plot_data["html"], height=450, scrolling=False)
    else:
        st.markdown(
            """
            <div class='card' style='text-align:center;padding:40px;'>
                <div style='font-size:36px;'>📈</div>
                <div style='font-size:14px;color:var(--muted);margin-top:8px;'>No results yet. Run a simulation or load a case.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Load result directory
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    result_path = st.text_input(
        "Load result directory",
        placeholder="/path/to/case/",
        key="result_path_input",
    )
    col_load, col_well = st.columns([2, 2])
    with col_load:
        if st.button("📂 Load & Analyze", key="load_result") and result_path:
            st.session_state.active_result_path = result_path
            st.session_state.drive_confirmed = False
            st.rerun()
    with col_well:
        well_level = st.checkbox("Include well plots", key="well_level")


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: DECK BUILDER
# ─────────────────────────────────────────────────────────────────────────────
def view_deck():
    st.markdown(
        "<h2 style='font-size:20px;font-weight:700;margin-bottom:16px;color:var(--text);'>📝 Deck Builder</h2>",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class='card'>
            <div style='font-size:13px;color:var(--muted);line-height:1.6;'>
                Describe your reservoir in plain English. OPM-AI will build a deck starting with
                <code>RUNSPEC</code> and ask for any missing parameters.
                Deck order: <code>RUNSPEC → GRID → PROPS → REGIONS → SOLUTION → SUMMARY → SCHEDULE</code>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    description = st.text_area(
        "Reservoir description",
        placeholder="E.g. Black oil model, 10×10×3 grid, solution gas drive, 3 production wells, 1 injector…",
        height=100,
        key="deck_description",
    )
    template = st.selectbox(
        "Starting template",
        ["Auto-detect", "SPE1", "SPE9", "SPE10", "BRUGGE", "NORNE"],
        key="deck_template",
    )

    if st.button("🔨 Build Deck", key="build_deck_btn") and description:
        router, err = get_router()
        if err:
            st.error(f"API key error: {err}")
        else:
            with st.spinner("Building deck…"):
                build_msg = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Build a simulation deck: {description}. Template: {template}.\nUse the build_deck tool."},
                ]
                full_response = ""
                for chunk in router.chat(build_msg, st.session_state):
                    full_response += chunk
                if st.session_state.get("active_deck"):
                    st.session_state.deck_editor_content = st.session_state.active_deck
                else:
                    st.session_state.deck_editor_content = full_response

    # Deck editor
    deck_content = st.session_state.get("deck_editor_content", "")
    edited_deck = st.text_area(
        "Deck editor",
        value=deck_content,
        height=400,
        key="deck_editor",
        help="Edit the deck directly. Click Lint to check for errors.",
    )
    st.session_state.active_deck = edited_deck

    col_lint, col_save, col_run = st.columns(3)
    with col_lint:
        if st.button("🔍 Lint Deck", key="lint_btn") and edited_deck:
            router, err = get_router()
            if err:
                st.error(f"API key error: {err}")
            else:
                with st.spinner("Linting…"):
                    lint_msgs = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Lint this deck and report all errors:\n\n{edited_deck[:3000]}"},
                    ]
                    result = ""
                    for chunk in router.chat(lint_msgs, st.session_state):
                        result += chunk
                    st.markdown(f"<div class='card'>{result}</div>", unsafe_allow_html=True)

    with col_save:
        save_path = st.text_input("Save path", placeholder="/cases/my_case/MY_CASE.DATA", label_visibility="collapsed", key="deck_save_path")
        if st.button("💾 Save Deck", key="save_btn") and save_path and edited_deck:
            try:
                p = Path(save_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(edited_deck, encoding="utf-8")
                st.session_state.active_deck_path = save_path
                st.success(f"Saved to {save_path}")
            except Exception as e:  # noqa: BLE001
                st.error(str(e))

    with col_run:
        if st.button("▶️ Run Simulation", key="deck_run_btn") and (edited_deck or st.session_state.active_deck_path):
            st.session_state.active_view = "run"
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: RUN SIMULATION
# ─────────────────────────────────────────────────────────────────────────────
def view_run():
    st.markdown(
        "<h2 style='font-size:20px;font-weight:700;margin-bottom:16px;color:var(--text);'>▶️ Run Simulation</h2>",
        unsafe_allow_html=True,
    )

    deck_path = st.text_input(
        "Deck path (.DATA)",
        value=st.session_state.get("active_deck_path", ""),
        placeholder="/cases/my_case/MY_CASE.DATA",
        key="run_deck_path",
    )
    col_threads, col_opm = st.columns(2)
    with col_threads:
        n_threads = st.number_input("MPI threads", min_value=1, max_value=64, value=4, key="run_threads")
    with col_opm:
        opm_bin = st.text_input(
            "flow binary",
            value=os.getenv("OPM_FLOW_BIN", "flow"),
            key="run_opm_bin",
        )

    if st.button("▶️ Launch Simulation", key="run_launch") and deck_path:
        st.session_state.active_deck_path = deck_path
        log_placeholder = st.empty()
        log_lines = []
        try:
            import subprocess
            cmd = [opm_bin, "--output-dir", str(Path(deck_path).parent), deck_path]
            if n_threads > 1:
                cmd = ["mpirun", "-np", str(n_threads)] + cmd
            with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            ) as proc:
                for line in proc.stdout:
                    log_lines.append(line.rstrip())
                    log_placeholder.code("\n".join(log_lines[-40:]), language="bash")
                rc = proc.returncode
            if rc == 0:
                st.success("✅ Simulation completed successfully!")
                result_dir = str(Path(deck_path).parent)
                st.session_state.active_result_path = result_dir
                st.session_state.drive_confirmed = False
            else:
                st.error(f"❌ Simulation failed with exit code {rc}")
        except FileNotFoundError:
            st.error(f"OPM Flow binary '{opm_bin}' not found. Install OPM Flow or set OPM_FLOW_BIN env var.")
        except Exception as e:  # noqa: BLE001
            st.error(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: EXPLAIN
# ─────────────────────────────────────────────────────────────────────────────
def view_explain():
    st.markdown(
        "<h2 style='font-size:20px;font-weight:700;margin-bottom:16px;color:var(--text);'>🎓 Concept Explainer</h2>",
        unsafe_allow_html=True,
    )

    if st.session_state.pending_kb_questions:
        st.markdown(
            "<div class='section-header'>📌 Queued for KB Build (Part 7)</div>",
            unsafe_allow_html=True,
        )
        for q in st.session_state.pending_kb_questions:
            st.markdown(f"<div class='card-sm'>⏳ {q}</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    concept = st.text_input(
        "Concept or question",
        placeholder="E.g. Why is reservoir pressure declining after waterflood?",
        key="explain_concept",
    )
    level = st.radio(
        "Explanation level",
        ["beginner", "intermediate", "advanced"],
        index=1,
        horizontal=True,
        key="explain_level",
    )

    if st.button("🎓 Explain", key="explain_btn") and concept:
        router, err = get_router()
        if err:
            st.error(f"API key error: {err}")
        else:
            with st.spinner("Thinking…"):
                msgs = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Explain this concept at {level} level, use the explain_concept tool: {concept}"},
                ]
                result = ""
                placeholder = st.empty()
                for chunk in router.chat(msgs, st.session_state):
                    result += chunk
                    placeholder.markdown(
                        f"<div class='card'>{result}</div>",
                        unsafe_allow_html=True,
                    )


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: SETTINGS
# ─────────────────────────────────────────────────────────────────────────────
def view_settings():
    st.markdown(
        "<h2 style='font-size:20px;font-weight:700;margin-bottom:16px;color:var(--text);'>⚙️ Settings</h2>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-header'>API Keys</div>", unsafe_allow_html=True)

    for pname, pcfg in PROVIDERS.items():
        current_key = os.getenv(pcfg.api_key_env, "")
        masked = ("*" * 8 + current_key[-4:]) if len(current_key) > 4 else ("Not set" if not current_key else current_key)
        new_key = st.text_input(
            f"{pcfg.badge} {pcfg.label} — {pcfg.api_key_env}",
            value="",
            placeholder=masked,
            type="password",
            key=f"settings_key_{pname}",
        )
        if new_key:
            os.environ[pcfg.api_key_env] = new_key
            st.success(f"{pcfg.api_key_env} updated for this session.")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>OPM Flow</div>", unsafe_allow_html=True)
    opm_path = st.text_input(
        "OPM Flow binary path",
        value=os.getenv("OPM_FLOW_BIN", "flow"),
        key="settings_opm_bin",
    )
    if st.button("Save OPM path", key="save_opm_path"):
        os.environ["OPM_FLOW_BIN"] = opm_path
        st.success("Saved.")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header">ResInsight (Local)</div>", unsafe_allow_html=True)
    resinsight_path = st.text_input(
        "ResInsight binary path",
        value=os.getenv("RESINSIGHT_BIN", "ResInsight"),
        key="settings_resinsight_bin",
    )
    if st.button("Save ResInsight path", key="save_resinsight_path"):
        os.environ["RESINSIGHT_BIN"] = resinsight_path
        st.success("Saved.")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header">Session</div>", unsafe_allow_html=True)
    if st.button("🗑️ Reset session state", key="reset_session"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    with st.expander("📋 Raw session state (debug)"):
        safe_state = {k: v for k, v in st.session_state.items() if k != "messages"}
        st.json(safe_state)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────────────────────
VIEW_MAP = {
    "chat": view_chat,
    "results": view_results,
    "deck": view_deck,
    "run": view_run,
    "explain": view_explain,
    "settings": view_settings,
}

VIEW_MAP.get(st.session_state.active_view, view_chat)()
