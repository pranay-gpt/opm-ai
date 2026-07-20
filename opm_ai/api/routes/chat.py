"""Chat route: WebSocket /api/chat -> LLM client + tool router"""

import json
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Any

from opm_ai.api.paths import validate_deck_path, validate_output_path
from opm_ai.api.schemas import (
    ChatMessage, ChatRequest, TOOLS,
    EXPLAIN_CONCEPT_TOOL,
    GENERATE_QUIZ_TOOL,
)
from opm_ai.api.job_store import create_job, set_job_running, set_job_completed, set_job_failed, get_job
from opm_ai.api.session_store import get_or_create_session, get_session, update_session
from opm_ai.builder import build_deck
from opm_ai.linter import lint_deck
from opm_ai.runner import run_simulation
from opm_ai.runner.models import SimulationJob
from opm_ai.postprocess.summary import read_summary
from opm_ai.postprocess.kpi import extract_kpis
from opm_ai.postprocess.plots import plot_production, plot_pressure
from opm_ai.postprocess.resinsight_bridge import export_snapshots
from opm_ai.llm.client import LLMClient
from pathlib import Path
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
    deck, lint_result = build_deck(description, output_path)
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
    result = lint_deck(deck_path)
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

                from opm_ai.api.schemas import SimulationResultDTO
                result_dto = SimulationResultDTO(
                    success=result.success,
                    output_dir=str(result.output_dir),
                    crash_report=result.crash_report.model_dump() if result.crash_report else None,
                    returncode=result.returncode,
                    duration_s=result.duration_s,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    warnings=result.warnings,
                    summary_files={k: str(v) for k, v in result.summary_files.items()},
                    prt_path=str(result.prt_path) if result.prt_path else None,
                )
                set_job_completed(job_id, result_dto)
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

    output_dir = Path(job.result.output_dir)
    df = read_summary(output_dir)
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
    import asyncio

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
    import asyncio

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

    output_dir = Path(job.result.output_dir)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: export_snapshots(output_dir))

    return {
        "success": result["success"],
        "snapshots": [Path(p).name for p in result["snapshots"]],
        "error": result["error"],
        "duration_s": result["duration_s"],
    }


TOOL_FUNCTIONS = {
    "build_deck": tool_build_deck,
    "lint_deck": tool_lint_deck,
    "run_simulation": tool_run_simulation,
    "get_kpis": tool_get_kpis,
    "explain_concept": tool_explain_concept,
    "generate_quiz": tool_generate_quiz,
    "export_snapshots": tool_export_snapshots,
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


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for chat with LLM and tool calling."""
    await websocket.accept()

    try:
        # First message should be ChatRequest
        data = await websocket.receive_text()
        request = ChatRequest.model_validate_json(data)

        session_id = request.session_id
        system_prompt = load_system_prompt()

        # Get or create session history using bounded session store
        _, history = get_or_create_session(session_id)

        # Add user messages from request
        for msg in request.messages:
            history.append(msg)

        # Update session store with modified history
        update_session(session_id, history)

        client = LLMClient()

        if not client.available:
            await websocket.send_text(json.dumps({
                "type": "error",
                "content": "LLM provider offline. Configure GROQ_API_KEY, NVIDIA_NIM_API_KEY, or OPENAI_API_KEY.",
            }))
            return

        # Main chat loop
        while True:
            # Prepare messages for LLM: system + history
            messages = [ChatMessage(role="system", content=system_prompt)] + history

            # Call LLM with tools
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.chat_with_tools(
                    [m.model_dump() for m in messages],
                    TOOLS,
                )
            )

            if response.get("tool_calls"):
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

                    # Add tool result to history
                    history.append(ChatMessage(
                        role="tool",
                        content=json.dumps(tool_result),
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
                # LLM responded with text - stream it
                content = response["content"]
                await websocket.send_text(json.dumps({
                    "type": "token",
                    "content": content,
                }))

                # Add assistant response to history
                history.append(ChatMessage(role="assistant", content=content))

                # Update session store
                update_session(session_id, history)

            else:
                # Empty response
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "content": f"Chat error: {str(e)}",
            }))
        except Exception:
            pass
    finally:
        await websocket.close()


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