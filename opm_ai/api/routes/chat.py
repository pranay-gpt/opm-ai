"""Chat route: WebSocket /api/chat -> LLM client + tool router"""

import json
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import ValidationError
from typing import Any

# Max bytes for a single ChatRequest frame. Anything larger is rejected
# before pydantic parses it; the LLM has no use for a multi-MB history
# and an oversized frame usually means a runaway client loop.
WS_MAX_FRAME_BYTES = 64 * 1024

from opm_ai.api.job_helpers import job_output_dir
from opm_ai.api.paths import validate_deck_path, validate_output_path
from opm_ai.api.schemas import (
    ChatMessage, ChatRequest, TOOLS,
    EXPLAIN_CONCEPT_TOOL,
    GENERATE_QUIZ_TOOL,
)
from opm_ai.api.job_store import create_job, set_job_running, set_job_completed, set_job_failed, get_job
from opm_ai.api.session_store import (
    get_or_create_session,
    get_session,
    get_session_lock,
    update_session,
)
from opm_ai.builder import build_deck
from opm_ai.linter import lint_deck
from opm_ai.runner import run_simulation
from opm_ai.runner.models import SimulationJob
from opm_ai.postprocess.summary import read_summary
from opm_ai.postprocess.kpi import extract_kpis
from opm_ai.postprocess.plots import plot_production, plot_pressure
from opm_ai.postprocess.resinsight_bridge import export_snapshots
from opm_ai.postprocess.categorizer import categorize
from opm_ai.postprocess.plot_groups import plot_group as build_plot_group
from opm_ai.llm.client import LLMClient
import asyncio

router = APIRouter()

# Load system prompt from file
SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "system_prompt.md"

# Cache system prompt at module import time
try:
    SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text() if SYSTEM_PROMPT_PATH.exists() else (
        "You are an expert reservoir engineering assistant for OPM Flow.\n"
        "Help users build, lint, run, and analyze reservoir simulation models.\n"
        "Use the available tools to execute tasks."
    )
except Exception:
    SYSTEM_PROMPT = (
        "You are an expert reservoir engineering assistant for OPM Flow.\n"
        "Help users build, lint, run, and analyze reservoir simulation models.\n"
        "Use the available tools to execute tasks."
    )


def load_system_prompt() -> str:
    """Load system prompt from cached module-level constant."""
    return SYSTEM_PROMPT


# Tool implementations
async def tool_build_deck(args: dict) -> dict:
    """Build a deck from natural language."""
    description = args.get("description", "")
    output_path = args.get("output_path")
    if output_path:
        output_path = validate_output_path(output_path)
    # Chat is only reachable with a live provider; LLM extraction is the
    # right default here (build_deck falls back to offline on any failure).
    # Executor: build_deck blocks (LLM network call + render + lint) and
    # must not stall the websocket event loop or keepalives die.
    loop = asyncio.get_event_loop()
    deck, lint_result = await loop.run_in_executor(
        None, lambda: build_deck(description, output_path, use_llm=True)
    )
    return {
        "deck": deck,
        "lint": {
            "deck_path": lint_result.deck_path,
            "errors": [i.message for i in lint_result.issues if i.severity == "ERROR"],
            "passed": lint_result.passed,
        }
    }


async def tool_lint_deck(args: dict) -> dict:
    """Lint a deck file."""
    deck_path = args.get("deck_path", "")
    deck_path = validate_deck_path(deck_path)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: lint_deck(deck_path))
    return {
        "deck_path": result.deck_path,
        "errors": [i.message for i in result.issues if i.severity == "ERROR"],
        "passed": result.passed,
    }


async def tool_run_simulation(args: dict) -> dict:
    """Run a simulation as a background job."""
    try:
        deck_path = args.get("deck_path", "")
        deck_path = validate_deck_path(deck_path)
        timeout = args.get("timeout", 120)
        job_id = create_job()
        output_dir = deck_path.parent / f"output_{job_id[:8]}"

        async def run_bg():
            set_job_running(job_id)
            try:
                job = SimulationJob(
                    deck_path=Path(deck_path),
                    output_dir=output_dir,
                    timeout=timeout,
                )
                result = await asyncio.get_event_loop().run_in_executor(None, run_simulation, job)

                # F4.2 audit fix: from_runner classmethod on the DTO
                # replaces the inline 12-line copy. Pydantic model_dump
                # is no longer used for crash_report because the DTO
                # field is now a CrashReportDTO, not a dict.
                from opm_ai.api.schemas import SimulationResultDTO
                set_job_completed(job_id, SimulationResultDTO.from_runner(result))
            except Exception as e:
                set_job_failed(job_id, str(e))

        asyncio.create_task(run_bg())
        return {"job_id": job_id, "status": "pending"}
    except ValueError as e:
        # Path validation errors
        return {"error": str(e)}
    except HTTPException as e:
        # Job store capacity errors (429)
        return {"error": e.detail}


async def tool_get_kpis(args: dict) -> dict:
    """Get KPIs and plots for a completed job."""
    job_id = args.get("job_id", "")
    job = get_job(job_id)
    if not job or job.status != "completed" or not job.result:
        return {"error": "Job not found or not completed"}

    output_dir = job_output_dir(job)
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, lambda: read_summary(output_dir))
    if df.empty:
        return {"error": "No summary data found"}

    kpis = extract_kpis(df)

    plots = {}
    try:
        fig_prod = plot_production(df)
        plots["production"] = fig_prod.to_json()
    except Exception as e:
        plots["production"] = f'{{"error": "{str(e)}"}}'

    try:
        fig_press = plot_pressure(df)
        plots["pressure"] = fig_press.to_json()
    except Exception as e:
        plots["pressure"] = f'{{"error": "{str(e)}"}}'

    return {"kpis": kpis, "plots": plots}


async def tool_explain_concept(args: dict) -> dict:
    """Explain a reservoir engineering concept."""
    from opm_ai.explainer import explain

    topic = args.get("topic", "")
    level = args.get("level", "intermediate")

    loop = asyncio.get_event_loop()
    explanation = await loop.run_in_executor(
        None,
        lambda: explain(topic, level=level)
    )

    # Return compact result for tool: text + citation titles (truncated to ~1500 chars)
    text = explanation.text
    if len(text) > 1500:
        text = text[:1500] + "..."

    citation_titles = [c.title for c in explanation.citations[:3]]

    return {
        "topic": explanation.topic,
        "level": explanation.level,
        "text": text,
        "citations": citation_titles,
        "follow_up_questions": list(explanation.follow_up_questions),
    }


async def tool_generate_quiz(args: dict) -> dict:
    """Generate a multiple-choice quiz from a scenario."""
    from opm_ai.explainer import generate_quiz

    scenario = args.get("scenario_summary", "")
    n_questions = args.get("n_questions", 3)

    loop = asyncio.get_event_loop()
    quiz = await loop.run_in_executor(
        None,
        lambda: generate_quiz(scenario, n_questions=n_questions)
    )

    # Return compact text format: Q / options A-D / answer letter
    lines = [f"Quiz: {quiz.scenario_summary}\n"]
    for i, q in enumerate(quiz.questions, 1):
        lines.append(f"Q{i}: {q.question}")
        for j, opt in enumerate(q.options):
            letter = chr(ord('A') + j)
            lines.append(f"  {letter}) {opt}")
        correct_letter = chr(ord('A') + q.correct_index)
        lines.append(f"  Answer: {correct_letter}")
        lines.append(f"  Explanation: {q.explanation}")
        lines.append("")

    return {
        "scenario_summary": quiz.scenario_summary,
        "questions_text": "\n".join(lines),
        "n_questions": len(quiz.questions),
    }


async def tool_export_snapshots(args: dict) -> dict:
    """Export ResInsight 3D snapshots for a completed job."""
    job_id = args.get("job_id", "")
    job = get_job(job_id)
    if not job or job.status != "completed" or not job.result:
        return {"error": "Job not found or not completed"}

    output_dir = job_output_dir(job)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: export_snapshots(output_dir))

    return {
        "success": result["success"],
        "snapshots": [Path(p).name for p in result["snapshots"]],
        "error": result["error"],
        "duration_s": result["duration_s"],
    }


def _resolve_active_job(args: dict) -> str | None:
    """Return the active job_id, preferring the one passed in args."""
    return args.get("job_id")


async def tool_list_available_vectors(args: dict) -> dict:
    """List which vector families are present in the active run's summary."""
    job_id = _resolve_active_job(args)
    if not job_id:
        return {"error": "no active job"}
    job = get_job(job_id)
    if not job or job.status != "completed" or not job.result:
        return {"error": "job not completed"}

    output_dir = job_output_dir(job)
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, lambda: read_summary(output_dir))
    if df.empty:
        return {"error": "no summary data"}

    return dict(categorize(df))


async def tool_plot_well_vectors(args: dict) -> dict:
    """Build a Plotly figure for selected wells + vectors.

    Args:
      wells: list[str] — at least one
      vectors: list[str] — at least one
      log: bool, optional
      group: str — one of well_rates / well_cumulative / well_injection
    """
    wells = args.get("wells") or []
    vectors = args.get("vectors") or []
    if not wells:
        return {"error": "missing 'wells' (non-empty list required)"}
    if not vectors:
        return {"error": "missing 'vectors' (non-empty list required)"}
    group = args.get("group", "well_rates")
    log_scale = bool(args.get("log", False))

    job_id = _resolve_active_job(args)
    if not job_id:
        return {"error": "no active job"}
    job = get_job(job_id)
    if not job or job.status != "completed" or not job.result:
        return {"error": "job not completed"}

    output_dir = job_output_dir(job)
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, lambda: read_summary(output_dir))
    if df.empty:
        return {"error": "no summary data"}

    try:
        fig = build_plot_group(group, df, wells, vectors, log_scale=log_scale)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("plot_well_vectors failed")
        return {"error": f"plot generation failed: {e}"}

    return {
        "figure_json": fig.to_json(),
        "wells": wells,
        "vectors": vectors,
        "group": group,
    }


async def tool_compare_wells(args: dict) -> dict:
    """Single vector across multiple wells — the common comparison shape."""
    if "vector" not in args:
        return {"error": "missing 'vector' (single string required)"}
    wells = args.get("wells") or []
    if not wells:
        return {"error": "missing 'wells' (non-empty list required)"}

    # Delegate to plot_well_vectors with the single vector wrapped as a list
    return await tool_plot_well_vectors({
        **args,
        "group": args.get("group", "well_rates"),
        "vectors": [args["vector"]],
    })


TOOL_FUNCTIONS = {
    "build_deck": tool_build_deck,
    "lint_deck": tool_lint_deck,
    "run_simulation": tool_run_simulation,
    "get_kpis": tool_get_kpis,
    "explain_concept": tool_explain_concept,
    "generate_quiz": tool_generate_quiz,
    "export_snapshots": tool_export_snapshots,
    "list_available_vectors": tool_list_available_vectors,
    "plot_well_vectors": tool_plot_well_vectors,
    "compare_wells": tool_compare_wells,
}


async def execute_tool(tool_name: str, args: dict) -> dict:
    """Execute a tool by name with arguments."""
    func = TOOL_FUNCTIONS.get(tool_name)
    if not func:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return await func(args)
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}


def compact_tool_result(tool_name: str, result: dict) -> dict:
    """Shrink a tool result for LLM history.

    The frontend receives the full result; the LLM only needs enough to
    continue the conversation. Full decks and Plotly figure JSON blow the
    provider token-per-minute limits when re-sent with every turn.
    """
    if tool_name == "build_deck":
        deck = result.get("deck", "")
        return {
            "deck_preview": deck[:400],
            "deck_chars": len(deck),
            "lint": result.get("lint"),
            "note": "Full deck shown to the user; use the lint verdict and deck_path.",
        }
    if tool_name == "get_kpis":
        return {
            "kpis": result.get("kpis"),
            "plots": "rendered for the user" if result.get("plots") else None,
            "error": result.get("error"),
        }
    if tool_name == "list_available_vectors":
        return result  # tiny, send it all
    if tool_name in ("plot_well_vectors", "compare_wells"):
        fig_data = result.get("figure_json") or ""
        try:
            import json as _json
            parsed = _json.loads(fig_data)
            trace_names = [t.get("name", "?") for t in parsed.get("data", [])]
        except Exception:
            trace_names = []
        return {
            "trace_count": len(trace_names),
            "trace_names": trace_names[:10],
            "wells": result.get("wells"),
            "vectors": result.get("vectors"),
            "note": "Full Plotly figure rendered for the user; not re-sent to the LLM.",
        }
    return result


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for chat with LLM and tool calling.

    Accepts one or more ChatRequest frames on the same connection (the
    frontend may also reconnect per turn; server-side session history is
    authoritative either way). Each turn ends with a {"type": "done"} event.
    """
    await websocket.accept()

    try:
      while True:
        data = await websocket.receive_text()
        if len(data.encode("utf-8")) > WS_MAX_FRAME_BYTES:
            # Send a structured error frame and keep the connection open:
            # the next turn may be a legitimate, small request.
            await websocket.send_text(json.dumps({
                "type": "error",
                "code": "payload_too_large",
                "message": f"Frame exceeds {WS_MAX_FRAME_BYTES} bytes",
            }))
            continue
        try:
            request = ChatRequest.model_validate_json(data)
        except (ValidationError, json.JSONDecodeError) as e:
            # Malformed frame must not kill the connection. The frontend
            # is the only legit client and it never sends garbage, so this
            # is a defensive path.
            await websocket.send_text(json.dumps({
                "type": "error",
                "code": "invalid_payload",
                "message": str(e)[:500],
            }))
            continue

        session_id = request.session_id
        system_prompt = load_system_prompt()

        # Per-session lock: concurrent connections on the same session id
        # share one history list; every read-modify-write must hold this
        # lock so interleaved handlers cannot lose updates.
        session_lock = get_session_lock(session_id)

        async with session_lock:
            # Get or create session history using bounded session store
            _, history = get_or_create_session(session_id)

            # Merge request messages. The client sends its full message list
            # each turn; server history already holds prior turns, so:
            # empty history -> take everything (fresh session or server
            # restart replay); otherwise only the trailing user message is
            # new input. A replayed list ending in an assistant message
            # carries nothing new.
            appended = 0
            if not history:
                for msg in request.messages:
                    history.append(msg)
                    appended += 1
            elif request.messages and request.messages[-1].role == "user":
                history.append(request.messages[-1])
                appended += 1

            update_session(session_id, history)

        if appended == 0:
            # Nothing new to respond to (e.g. reconnect replay); wait for
            # the next request on this connection.
            continue

        client = LLMClient()

        if not client.available:
            msg = "LLM provider offline. Configure GROQ_API_KEY, NVIDIA_NIM_API_KEY, or OPENAI_API_KEY."
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": msg,
                "content": msg,
            }))
            continue

        # Main chat loop for this turn
        while True:
            # Prepare messages for LLM: system + snapshot of history taken
            # under the lock (the LLM call itself runs unlocked).
            async with session_lock:
                messages = [ChatMessage(role="system", content=system_prompt)] + list(history)

            # Call LLM with tools
            # exclude_none: providers reject explicit null tool_calls /
            # tool_call_id fields on messages that do not use them.
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.chat_with_tools(
                    [m.model_dump(exclude_none=True) for m in messages],
                    TOOLS,
                )
            )

            if response.get("tool_calls"):
                # Record the assistant turn that requested the tools; the
                # provider requires tool-role messages to follow it.
                async with session_lock:
                    history.append(ChatMessage(
                        role="assistant",
                        content=response.get("content") or "",
                        tool_calls=response["tool_calls"],
                    ))
                    update_session(session_id, history)

                # LLM wants to call tools
                for tool_call in response["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    tool_args = json.loads(tool_call["function"]["arguments"])
                    tool_call_id = tool_call["id"]

                    # Send tool call to frontend
                    await websocket.send_text(json.dumps({
                        "type": "tool_call",
                        "tool_name": tool_name,
                        "arguments": tool_args,
                        "tool_call_id": tool_call_id,
                    }))

                    # Execute tool
                    tool_result = await execute_tool(tool_name, tool_args)

                    # Add tool result to history (compacted: the LLM never
                    # needs full deck text or Plotly JSON re-sent each turn)
                    async with session_lock:
                        history.append(ChatMessage(
                            role="tool",
                            content=json.dumps(compact_tool_result(tool_name, tool_result)),
                            tool_call_id=tool_call_id,
                        ))

                        # Update session store
                        update_session(session_id, history)

                    # Send tool result to frontend
                    await websocket.send_text(json.dumps({
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "result": tool_result,
                        "tool_call_id": tool_call_id,
                    }))

                # Continue loop to get next LLM response after tool execution
                continue

            elif response.get("content"):
                # LLM responded with text - stream it and end the turn
                content = response["content"]
                await websocket.send_text(json.dumps({
                    "type": "token",
                    "content": content,
                }))

                # Add assistant response to history
                async with session_lock:
                    history.append(ChatMessage(role="assistant", content=content))

                    # Update session store
                    update_session(session_id, history)

                await websocket.send_text(json.dumps({"type": "done"}))
                break

            else:
                # Empty response (provider error or nothing to say)
                await websocket.send_text(json.dumps({"type": "done"}))
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            # "message" is what the frontend reads; keep "content" for
            # older consumers.
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Chat error: {str(e)}",
                "content": f"Chat error: {str(e)}",
            }))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            # Already closed (client disconnect); nothing to do.
            pass


@router.post("/chat", response_model=ChatMessage)
async def chat_http(request: ChatRequest) -> ChatMessage:
    """HTTP fallback for chat (non-streaming)."""
    try:
        system_prompt = load_system_prompt()
        client = LLMClient()

        if not client.available:
            raise HTTPException(
                status_code=503,
                detail="LLM provider offline. Configure GROQ_API_KEY, NVIDIA_NIM_API_KEY, or OPENAI_API_KEY."
            )

        messages = [ChatMessage(role="system", content=system_prompt)] + request.messages
        response = client.chat_with_tools(
            [m.model_dump() for m in messages],
            TOOLS,
        )

        if response.get("tool_calls"):
            return ChatMessage(
                role="assistant",
                content=f"Tool calls requested: {[tc['function']['name'] for tc in response['tool_calls']]}",
            )

        return ChatMessage(role="assistant", content=response.get("content", ""))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))