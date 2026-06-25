"""
Tool schema definitions and dispatch logic for the OPM-AI chat router.

Each tool maps to a module in opm_ai:
  build_deck      -> opm_ai.deckbuilder
  lint_deck       -> opm_ai.linter
  run_simulation  -> opm_ai.simulator
  analyze_results -> opm_ai.postprocess
  explain_concept -> KB (placeholder for Part 7)
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

# ─── Tool schema (OpenAI function-calling format) ────────────────────────────

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "build_deck",
            "description": (
                "Build an OPM Flow / Eclipse simulation deck from a natural language "
                "description. Starts with RUNSPEC and asks for all required parameters. "
                "Use the closest sample dataset as the template."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Plain English reservoir model description, including fluid type, drive mechanism, grid size hints, and any known PVT data.",
                    },
                    "template": {
                        "type": "string",
                        "description": "Optional template name, e.g. 'SPE1', 'SPE9', 'BRUGGE'. Leave blank to auto-select.",
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lint_deck",
            "description": (
                "Lint and validate an Eclipse/OPM deck text. Returns a list of "
                "errors and warnings, grouped by section."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "deck_text": {
                        "type": "string",
                        "description": "Full deck content as a string, or a file path ending in .DATA.",
                    },
                },
                "required": ["deck_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_simulation",
            "description": (
                "Run OPM Flow on the active or specified deck. "
                "Returns run status, timesteps, and path to output SMSPEC/UNSMRY files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "deck_path": {
                        "type": "string",
                        "description": "Absolute path to the .DATA file. Omit to use the active case.",
                    },
                    "parallel": {
                        "type": "integer",
                        "description": "Number of MPI threads. Default 4.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_results",
            "description": (
                "Post-process simulation results. Identifies drive mechanism, extracts KPIs, "
                "and generates interactive Plotly charts. Always identifies drive mechanism "
                "and confirms with user before plotting."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "result_path": {
                        "type": "string",
                        "description": "Path to the case directory containing UNSMRY. Omit to use active result.",
                    },
                    "drive_mechanism": {
                        "type": "string",
                        "enum": [
                            "solution_gas",
                            "gas_cap",
                            "water_drive",
                            "combination",
                            "gravity_drainage",
                            "waterflood",
                            "eor",
                        ],
                        "description": "Override drive mechanism detection. Leave blank to auto-detect.",
                    },
                    "well_level": {
                        "type": "boolean",
                        "description": "Include per-well plots in addition to field-level. Default false.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_concept",
            "description": (
                "Explain a reservoir engineering or simulation concept. "
                "If a knowledge base entry exists, uses it; otherwise uses LLM reasoning. "
                "[KB_PENDING] concepts are queued for Part 7 knowledge base build."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "concept": {
                        "type": "string",
                        "description": "The concept to explain, e.g. 'material balance equation', 'why is reservoir pressure declining'",
                    },
                    "level": {
                        "type": "string",
                        "enum": ["beginner", "intermediate", "advanced"],
                        "description": "Explanation depth. Default intermediate.",
                    },
                },
                "required": ["concept"],
            },
        },
    },
]


# ─── Tool dispatch ────────────────────────────────────────────────────────────

def dispatch(tool_name: str, args: dict, session: dict) -> str:
    """
    Route a tool call to the appropriate opm_ai module.
    Returns a JSON-serialisable string to feed back into the LLM context.
    """
    try:
        if tool_name == "build_deck":
            return _build_deck(args, session)
        elif tool_name == "lint_deck":
            return _lint_deck(args, session)
        elif tool_name == "run_simulation":
            return _run_simulation(args, session)
        elif tool_name == "analyze_results":
            return _analyze_results(args, session)
        elif tool_name == "explain_concept":
            return _explain_concept(args, session)
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": str(e), "tool": tool_name})


def _build_deck(args: dict, session: dict) -> str:
    try:
        from opm_ai.deckbuilder import build_deck  # type: ignore
        result = build_deck(
            description=args["description"],
            template=args.get("template"),
        )
        session["active_deck"] = result.get("deck_text", "")
        return json.dumps(result)
    except ImportError:
        return json.dumps({"status": "stub", "message": "DeckBuilder module not yet loaded.", "args": args})


def _lint_deck(args: dict, session: dict) -> str:
    try:
        from opm_ai.linter import lint_deck  # type: ignore
        return json.dumps(lint_deck(deck_text=args["deck_text"]))
    except ImportError:
        return json.dumps({"status": "stub", "message": "Linter module not yet loaded.", "args": args})


def _run_simulation(args: dict, session: dict) -> str:
    try:
        from opm_ai.simulator import run_simulation  # type: ignore
        deck_path = args.get("deck_path") or session.get("active_deck_path")
        result = run_simulation(deck_path=deck_path, parallel=args.get("parallel", 4))
        session["active_result_path"] = result.get("result_path")
        return json.dumps(result)
    except ImportError:
        return json.dumps({"status": "stub", "message": "Simulator module not yet loaded.", "args": args})


def _analyze_results(args: dict, session: dict) -> str:
    try:
        from opm_ai.postprocess.kpi_extractor import extract_kpis  # type: ignore
        from opm_ai.postprocess.plot_engine import generate_plots  # type: ignore
        from opm_ai.postprocess.reader import load_summary  # type: ignore  # noqa: F401
        result_path = args.get("result_path") or session.get("active_result_path")
        sf = load_summary(result_path)
        kpis = extract_kpis(sf)
        plots = generate_plots(sf, kpis, output_dir=None, drive=args.get("drive_mechanism"))
        session["last_kpis"] = kpis
        session["last_plots"] = plots
        return json.dumps({"kpis": kpis.to_dict() if hasattr(kpis, "to_dict") else str(kpis), "plot_count": len(plots)})
    except ImportError:
        return json.dumps({"status": "stub", "message": "PostProcess modules not yet fully wired.", "args": args})


def _explain_concept(args: dict, session: dict) -> str:
    concept = args["concept"]
    level = args.get("level", "intermediate")
    # KB lookup placeholder — Part 7 will inject real entries here
    kb_entry = _kb_lookup(concept)
    if kb_entry:
        return json.dumps({"source": "knowledge_base", "content": kb_entry})
    # Queue for Part 7 KB build
    session.setdefault("pending_kb_questions", []).append(concept)
    return json.dumps({
        "source": "llm_reasoning",
        "concept": concept,
        "level": level,
        "kb_pending": True,
        "message": f"[KB_PENDING] No KB entry for '{concept}'. Answered via LLM. Queued for KB build.",
    })


def _kb_lookup(concept: str) -> str | None:
    """Part 7 placeholder — returns None until KB is built."""
    return None
