"""
Streamlit CSS themes for OPM-AI.
Inspired by PewDiePie's Odyssey — minimal, dark-first, clean typography.
Each theme is injected via st.markdown(unsafe_allow_html=True).
"""

THEMES: dict[str, dict] = {
    "Dark Void": {
        "description": "Default — deep charcoal, cyan accent",
        "emoji": "🌑",
        "css": """
        :root {
            --bg: #0e0e10;
            --surface: #18181b;
            --surface2: #1f1f23;
            --border: #2a2a2e;
            --text: #efeff1;
            --muted: #adadb8;
            --accent: #00b5ad;
            --accent-hover: #00d4c8;
            --accent-dim: rgba(0,181,173,0.12);
            --sidebar-bg: #18181b;
            --code-bg: #111113;
            --danger: #eb5757;
            --success: #57eb8a;
            --warning: #ebc457;
            --font-body: 'Inter', 'Segoe UI', sans-serif;
            --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
        }
        """,
    },
    "Arctic Frost": {
        "description": "Clean white, blue accent",
        "emoji": "❄️",
        "css": """
        :root {
            --bg: #f5f7fa;
            --surface: #ffffff;
            --surface2: #eef1f6;
            --border: #d8dde6;
            --text: #1a1d23;
            --muted: #5a6072;
            --accent: #2563eb;
            --accent-hover: #1d4ed8;
            --accent-dim: rgba(37,99,235,0.10);
            --sidebar-bg: #eef1f6;
            --code-bg: #f0f2f5;
            --danger: #dc2626;
            --success: #16a34a;
            --warning: #d97706;
            --font-body: 'Inter', 'Segoe UI', sans-serif;
            --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
        }
        """,
    },
    "Sepia Crude": {
        "description": "Warm brown, gold accent — oil field vibes",
        "emoji": "🛢️",
        "css": """
        :root {
            --bg: #1a1208;
            --surface: #231a0d;
            --surface2: #2e2210;
            --border: #3d2e14;
            --text: #e8d5a3;
            --muted: #a08c5a;
            --accent: #d4a017;
            --accent-hover: #f0c040;
            --accent-dim: rgba(212,160,23,0.12);
            --sidebar-bg: #1e1509;
            --code-bg: #150f05;
            --danger: #c0392b;
            --success: #27ae60;
            --warning: #e67e22;
            --font-body: 'Inter', 'Segoe UI', sans-serif;
            --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
        }
        """,
    },
    "Matrix Green": {
        "description": "Terminal green on black — simulation mode",
        "emoji": "💻",
        "css": """
        :root {
            --bg: #020c02;
            --surface: #061006;
            --surface2: #0a160a;
            --border: #1a3a1a;
            --text: #00ff41;
            --muted: #00aa2b;
            --accent: #39ff14;
            --accent-hover: #7fff00;
            --accent-dim: rgba(57,255,20,0.10);
            --sidebar-bg: #040d04;
            --code-bg: #010801;
            --danger: #ff3131;
            --success: #39ff14;
            --warning: #ffd700;
            --font-body: 'JetBrains Mono', 'Fira Code', monospace;
            --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
        }
        """,
    },
    "Midnight Blue": {
        "description": "Navy surface, electric blue accent",
        "emoji": "🌊",
        "css": """
        :root {
            --bg: #060b18;
            --surface: #0d1526;
            --surface2: #121c30;
            --border: #1e2d4a;
            --text: #cdd9f0;
            --muted: #7a90b5;
            --accent: #3b82f6;
            --accent-hover: #60a5fa;
            --accent-dim: rgba(59,130,246,0.12);
            --sidebar-bg: #0a1120;
            --code-bg: #060a14;
            --danger: #f87171;
            --success: #4ade80;
            --warning: #fbbf24;
            --font-body: 'Inter', 'Segoe UI', sans-serif;
            --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
        }
        """,
    },
}


BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Reset & base ── */
* { box-sizing: border-box; }

body, .main, .block-container, [data-testid="stApp"],
[data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: var(--font-body) !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: var(--sidebar-bg) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }

/* ── Sidebar nav buttons ── */
.nav-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 10px 14px;
    margin-bottom: 4px;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: var(--muted);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
    text-align: left;
    font-family: var(--font-body);
}
.nav-btn:hover { background: var(--accent-dim); color: var(--text); }
.nav-btn.active { background: var(--accent-dim); color: var(--accent); border-left: 2px solid var(--accent); }
.nav-btn .icon { font-size: 16px; width: 20px; text-align: center; }

/* ── Cards & surfaces ── */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.card-sm {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
    font-size: 13px;
}

/* ── Chat messages ── */
.msg-user {
    display: flex;
    justify-content: flex-end;
    margin: 8px 0;
}
.msg-user .bubble {
    background: var(--accent);
    color: #fff;
    padding: 10px 16px;
    border-radius: 18px 18px 4px 18px;
    max-width: 75%;
    font-size: 14px;
    line-height: 1.5;
}
.msg-ai {
    display: flex;
    justify-content: flex-start;
    margin: 8px 0;
    gap: 10px;
}
.msg-ai .avatar {
    width: 32px; height: 32px;
    border-radius: 50%;
    background: var(--accent-dim);
    border: 1px solid var(--accent);
    display: flex; align-items: center; justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
}
.msg-ai .bubble {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 10px 16px;
    border-radius: 4px 18px 18px 18px;
    max-width: 80%;
    font-size: 14px;
    line-height: 1.6;
}

/* ── Code blocks ── */
pre, code {
    font-family: var(--font-mono) !important;
    background: var(--code-bg) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px;
    font-size: 12px !important;
    color: var(--accent) !important;
}

/* ── Tool call indicator ── */
.tool-call-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--accent-dim);
    border: 1px solid var(--accent);
    color: var(--accent);
    font-size: 11px;
    font-family: var(--font-mono);
    padding: 3px 10px;
    border-radius: 20px;
    margin: 4px 0;
}

/* ── KPI grid ── */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
    margin: 16px 0;
}
.kpi-card {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
}
.kpi-card .kpi-value {
    font-size: 22px;
    font-weight: 700;
    color: var(--accent);
    font-variant-numeric: tabular-nums;
}
.kpi-card .kpi-label {
    font-size: 11px;
    color: var(--muted);
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Provider badge ── */
.provider-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 3px 10px;
    font-size: 11px;
    color: var(--muted);
}

/* ── Streamlit overrides ── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
.stTextInput input, .stTextArea textarea {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
    font-family: var(--font-body) !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px var(--accent-dim) !important;
}
.stButton button {
    background: var(--accent) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
}
.stButton button:hover {
    background: var(--accent-hover) !important;
    transform: translateY(-1px);
}
.stSelectbox div[data-baseweb="select"] {
    background: var(--surface2) !important;
    border-color: var(--border) !important;
}
[data-testid="stMarkdownContainer"] {
    color: var(--text) !important;
}
div[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}
/* Hide Streamlit branding */
#MainMenu, footer, [data-testid="stDeployButton"] { visibility: hidden; }
.stDeployButton { display: none; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted); }

/* ── Divider ── */
.divider {
    height: 1px;
    background: var(--border);
    margin: 16px 0;
}

/* ── Section header ── */
.section-header {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin: 20px 0 8px 0;
    padding: 0 4px;
}
</style>
"""


def get_theme_css(theme_name: str) -> str:
    """Return full CSS string for the given theme name."""
    theme = THEMES.get(theme_name, THEMES["Dark Void"])
    return f"<style>\n{theme['css']}\n</style>\n{BASE_CSS}"
