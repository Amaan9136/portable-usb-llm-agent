"""
PortableCoder agent API.

Runs a single sequential agent loop (planner -> implementer -> reviewer ->
tester -> packager, per system_prompt.txt) against a locally-hosted
OpenAI-compatible llama.cpp server. Never calls multiple model instances
concurrently — one shared local model, one request at a time.

Two tool-invocation modes are supported:
  - native: uses OpenAI-style `tools`/`tool_calls` (default; works with
    llama.cpp's --jinja templated function calling for supported models).
  - fallback: if native tool calling proves unreliable with a given
    model/template combo, set TOOL_MODE=fallback in .env.example to switch
    to a constrained single-JSON-object-per-turn protocol, validated with
    Pydantic (schemas.FallbackAction). This trades some flexibility for
    much higher reliability on smaller/quantized local models.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from openai import APIConnectionError, OpenAI
from pydantic import ValidationError

from config import (
    AGENT_PORT,
    ARTIFACTS,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LOGS,
    MAX_AGENT_TURNS,
)
from schemas import AgentRequest, AgentResponse, FallbackAction, ToolCallTrace
from tools import PathSecurityError, create_zip, list_files, read_file, run_command, safe_artifact_path, write_file

# --- Logging -----------------------------------------------------------
# Structured, but deliberately excludes task text, file content, command
# output, and anything that could contain secrets. Only metadata: which
# tool ran, whether it succeeded, and timing/size counters.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOGS / "agent.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("portablecoder")

TOOL_MODE = os.environ.get("TOOL_MODE", "native")  # "native" or "fallback"

app = FastAPI(title="PortableCoder Agent", version="1.0.0")
client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

with open(os.path.join(os.path.dirname(__file__), "system_prompt.txt"), encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"relative_path": {"type": "string", "default": "."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": ["relative_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create (or, if explicitly allowed, overwrite) a UTF-8 file inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["relative_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run an approved command in the workspace. Allowed commands: "
                "python, pytest, npm, node, git. Only executes if commands "
                "were explicitly allowed for this request."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "array", "items": {"type": "string"}},
                    "relative_cwd": {"type": "string", "default": "."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_zip",
            "description": "Create a ZIP file in artifacts/ from a workspace file or folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_relative_path": {"type": "string"},
                    "artifact_name": {"type": "string"},
                },
                "required": ["source_relative_path", "artifact_name"],
            },
        },
    },
]


def _dispatch_tool(name: str, arguments: dict, request: AgentRequest) -> dict:
    """Route a tool call to its implementation, injecting the per-request
    permission flags (allow_commands / allow_overwrite) rather than
    trusting the model to pass them — the model never controls these."""
    if name == "list_files":
        return list_files(arguments.get("relative_path", "."))
    if name == "read_file":
        return read_file(arguments["relative_path"])
    if name == "write_file":
        return write_file(
            arguments["relative_path"],
            arguments.get("content", ""),
            allow_overwrite=request.allow_overwrite,
        )
    if name == "run_command":
        return run_command(
            arguments.get("command", []),
            arguments.get("relative_cwd", "."),
            allow_commands=request.allow_commands,
        )
    if name == "create_zip":
        return create_zip(
            arguments["source_relative_path"],
            arguments["artifact_name"],
        )
    return {"ok": False, "error": f"Unknown tool: {name}"}


def _run_native(request: AgentRequest) -> AgentResponse:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request.task},
    ]
    trace: list[ToolCallTrace] = []
    changed_files: list[str] = []
    command_results: list[dict] = []
    artifact_filename: str | None = None
    warnings: list[str] = []

    for turn in range(MAX_AGENT_TURNS):
        try:
            completion = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
        except APIConnectionError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Could not reach the local model server at "
                    f"{LLM_BASE_URL}. Is Start-Model.bat running? ({exc})"
                ),
            ) from exc

        message = completion.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        logger.info("turn=%d tool_calls=%d", turn, len(message.tool_calls or []))

        if not message.tool_calls:
            return AgentResponse(
                ok=True,
                changed_files=changed_files,
                command_results=command_results,
                warnings=warnings,
                final_answer=message.content or "",
                artifact_filename=artifact_filename,
                trace=trace,
            )

        for call in message.tool_calls:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                result = {"ok": False, "error": "Model produced invalid JSON arguments."}
                arguments = {}
            else:
                try:
                    result = _dispatch_tool(call.function.name, arguments, request)
                except PathSecurityError as exc:
                    result = {"ok": False, "error": str(exc)}
                except Exception as exc:  # defensive: never let a tool crash the loop
                    logger.exception("tool=%s failed", call.function.name)
                    result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

            if call.function.name == "write_file" and result.get("ok"):
                changed_files.append(result["written"])
            if call.function.name == "run_command":
                command_results.append(result)
            if call.function.name == "create_zip" and result.get("ok"):
                artifact_filename = result["artifact"]

            trace.append(ToolCallTrace(tool=call.function.name, arguments=arguments, result=result))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                }
            )

    warnings.append(f"Agent turn limit ({MAX_AGENT_TURNS}) reached before a final answer.")
    return AgentResponse(
        ok=False,
        changed_files=changed_files,
        command_results=command_results,
        warnings=warnings,
        final_answer="Turn limit reached. Review the trace and narrow the task.",
        artifact_filename=artifact_filename,
        trace=trace,
    )


def _run_fallback(request: AgentRequest) -> AgentResponse:
    """Constrained single-JSON-action-per-turn loop for models/templates
    that don't reliably support native tool calling."""
    fallback_prompt = (
        SYSTEM_PROMPT
        + "\n\nNOTE: Native tool calling is NOT available in this session. "
        "Use the FALLBACK JSON MODE described above for every turn."
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": fallback_prompt},
        {"role": "user", "content": request.task},
    ]
    trace: list[ToolCallTrace] = []
    changed_files: list[str] = []
    command_results: list[dict] = []
    artifact_filename: str | None = None
    warnings: list[str] = []

    for turn in range(MAX_AGENT_TURNS):
        try:
            completion = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=0.2,
            )
        except APIConnectionError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Could not reach the local model server at {LLM_BASE_URL}. ({exc})",
            ) from exc

        raw = completion.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": raw})

        try:
            action = FallbackAction.model_validate_json(raw)
        except ValidationError as exc:
            warnings.append(f"turn {turn}: model emitted invalid action JSON, retrying.")
            messages.append(
                {
                    "role": "user",
                    "content": f"Invalid action JSON ({exc}). Emit exactly one valid action JSON object.",
                }
            )
            continue

        if action.action == "final_answer":
            return AgentResponse(
                ok=True,
                changed_files=changed_files,
                command_results=command_results,
                warnings=warnings,
                final_answer=action.answer or "",
                artifact_filename=artifact_filename,
                trace=trace,
            )

        arguments = action.model_dump(exclude_none=True, exclude={"action"})
        try:
            result = _dispatch_tool(action.action, arguments, request)
        except PathSecurityError as exc:
            result = {"ok": False, "error": str(exc)}
        except Exception as exc:
            logger.exception("tool=%s failed", action.action)
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

        if action.action == "write_file" and result.get("ok"):
            changed_files.append(result["written"])
        if action.action == "run_command":
            command_results.append(result)
        if action.action == "create_zip" and result.get("ok"):
            artifact_filename = result["artifact"]

        trace.append(ToolCallTrace(tool=action.action, arguments=arguments, result=result))
        messages.append({"role": "user", "content": f"Tool result: {json.dumps(result)}"})

    warnings.append(f"Agent turn limit ({MAX_AGENT_TURNS}) reached before a final answer.")
    return AgentResponse(
        ok=False,
        changed_files=changed_files,
        command_results=command_results,
        warnings=warnings,
        final_answer="Turn limit reached. Review the trace and narrow the task.",
        artifact_filename=artifact_filename,
        trace=trace,
    )


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "model_endpoint": LLM_BASE_URL,
        "model": LLM_MODEL,
        "tool_mode": TOOL_MODE,
    }


@app.post("/agent", response_model=AgentResponse)
def run_agent(request: AgentRequest) -> AgentResponse:
    logger.info(
        "agent request received: create_zip=%s allow_commands=%s allow_overwrite=%s",
        request.create_zip,
        request.allow_commands,
        request.allow_overwrite,
    )
    if TOOL_MODE == "fallback":
        return _run_fallback(request)
    return _run_native(request)


@app.get("/artifacts")
def list_artifacts() -> dict:
    files = sorted(p.name for p in ARTIFACTS.glob("*.zip") if p.is_file())
    return {"ok": True, "artifacts": files}


@app.get("/artifacts/{filename}")
def download_artifact(filename: str) -> FileResponse:
    try:
        path = safe_artifact_path(filename)
    except PathSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(path, media_type="application/zip", filename=path.name)
