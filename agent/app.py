"""
Portable USB LLM Agent agent API.
Runs a single sequential agent loop (planner -> implementer -> reviewer ->
tester -> packager, per system_prompt.txt) against a locally-hosted
OpenAI-compatible llama.cpp server. Never calls multiple model instances
concurrently - one shared local model, one request at a time.
Two tool-invocation modes are supported:
  - native: uses OpenAI-style `tools`/`tool_calls` (default; works with
    llama.cpp's --jinja templated function calling for supported models).
  - fallback: if native tool calling proves unreliable with a given
    model/template combo, set TOOL_MODE=fallback in .env to switch to a
    constrained single-JSON-object-per-turn protocol, validated with
    Pydantic (schemas.FallbackAction). This trades some flexibility for
    much higher reliability on smaller/quantized local models.
"""
from __future__ import annotations
import json
import logging
import os
import time
from pathlib import PurePosixPath as PathLib
from typing import Any, Iterator
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError, OpenAI
from pydantic import ValidationError
from config import ( AGENT_PORT, ARTIFACTS, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LOGS, MAX_AGENT_TURNS, MODEL_BACKEND, MODEL_PORT, OLLAMA_HOST, OLLAMA_MODEL_NAME, TESTING_PHASE_DEFAULT, TOOL_MODE, VERBOSE_STREAM_DEFAULT, WORKSPACE, )
from schemas import ( AgentRequest, AgentResponse, FallbackAction, FileWriteRequest, ImportProjectRequest, SelectModelRequest, ToolCallTrace, )
from tools import ( PathSecurityError, create_zip, file_tree, import_project, list_files, list_projects, read_file, run_command, safe_artifact_path, write_file, )
import ollama_client
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
logger = logging.getLogger("Portable USB LLM Agent")
app = FastAPI(title="Portable USB LLM Agent Agent", version="1.0.0")
# Loopback-only UI talks to this API from the same machine (a file:// or
# 127.0.0.1-served page). CORS is opened for local origins only - this
# process never binds anywhere but 127.0.0.1 (see SECURITY.md), so this
# does not expose anything to the network.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(127\.0\.0\.1|localhost)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)
_DEFAULT_CLIENT = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
_CLIENT_CACHE: dict[str, OpenAI] = {LLM_BASE_URL: _DEFAULT_CLIENT}
_ACTIVE_SELECTION = {"backend": MODEL_BACKEND, "model_name": OLLAMA_MODEL_NAME or LLM_MODEL}
with open(os.path.join(os.path.dirname(__file__), "system_prompt.txt"), encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


def _resolve_backend(request: AgentRequest) -> tuple[OpenAI, str, str]:
    """Pick the OpenAI-compatible client, base URL, and model name to use
    for this request. Precedence: explicit per-request backend/model_name
    > the server-wide active selection (set via /models/select, the UI
    switcher, or `cli.py --model`) > MODEL_BACKEND/.env at startup."""
    backend = request.backend or _ACTIVE_SELECTION["backend"] or MODEL_BACKEND
    if backend == "ollama":
        base_url = f"{OLLAMA_HOST.rstrip('/')}/v1"
        model = request.model_name or _ACTIVE_SELECTION["model_name"] or OLLAMA_MODEL_NAME or LLM_MODEL
    else:
        base_url = f"http://127.0.0.1:{MODEL_PORT}/v1"
        model = LLM_MODEL
    if base_url not in _CLIENT_CACHE:
        _CLIENT_CACHE[base_url] = OpenAI(base_url=base_url, api_key=LLM_API_KEY)
    return _CLIENT_CACHE[base_url], base_url, model
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
def _extract_fallback_action(raw: str) -> FallbackAction | None:
    """Best-effort recovery of a FallbackAction from raw model text that
    may be wrapped in a markdown code fence or have stray whitespace/prose
    around the JSON object, instead of being pure JSON as instructed."""
    text = raw.strip()
    if text.startswith("```"):
        text = text[3:]
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    candidate = text[start : end + 1]
    try:
        return FallbackAction.model_validate_json(candidate)
    except ValidationError:
        return None
def _dispatch_tool(name: str, arguments: dict, request: AgentRequest) -> dict:
    """Route a tool call to its implementation, injecting the per-request
    permission flags (allow_commands / allow_overwrite) rather than
    trusting the model to pass them - the model never controls these."""
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
    client, base_url, model_name = _resolve_backend(request)
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
                model=model_name,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
        except APIConnectionError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Could not reach the model server at "
                    f"{base_url}. Is the model/Ollama server running? ({exc})"
                ),
            ) from exc
        message = completion.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        logger.info("turn=%d tool_calls=%d", turn, len(message.tool_calls or []))
        if not message.tool_calls:
            rescued = _extract_fallback_action(message.content or "")
            if rescued is None:
                return AgentResponse(
                    ok=True,
                    changed_files=changed_files,
                    command_results=command_results,
                    warnings=warnings,
                    final_answer=message.content or "",
                    artifact_filename=artifact_filename,
                    trace=trace,
                )
            warnings.append(
                f"turn {turn}: model emitted a JSON action as plain text instead of a "
                "native tool call; recovered it automatically."
            )
            if rescued.action == "final_answer":
                return AgentResponse(
                    ok=True,
                    changed_files=changed_files,
                    command_results=command_results,
                    warnings=warnings,
                    final_answer=rescued.answer or "",
                    artifact_filename=artifact_filename,
                    trace=trace,
                )
            rescued_arguments = rescued.model_dump(exclude_none=True, exclude={"action"})
            try:
                result = _dispatch_tool(rescued.action, rescued_arguments, request)
            except PathSecurityError as exc:
                result = {"ok": False, "error": str(exc)}
            except Exception as exc:
                logger.exception("tool=%s failed", rescued.action)
                result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            if rescued.action == "write_file" and result.get("ok"):
                changed_files.append(result["written"])
            if rescued.action == "run_command":
                command_results.append(result)
            if rescued.action == "create_zip" and result.get("ok"):
                artifact_filename = result["artifact"]
            trace.append(ToolCallTrace(tool=rescued.action, arguments=rescued_arguments, result=result))
            messages.append({"role": "user", "content": f"Tool result: {json.dumps(result)}"})
            continue
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
_ROLE_SEQUENCE = ["planner", "implementer", "reviewer", "tester", "packager"]
_TOOL_TO_ROLE_HINT = {
    "list_files": "planner",
    "read_file": "planner",
    "write_file": "implementer",
    "run_command": "tester",
    "create_zip": "packager",
}
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
def _stream_native(request: AgentRequest) -> Iterator[str]:
    client, base_url, model_name = _resolve_backend(request)
    verbose = request.verbose_stream if request.verbose_stream is not None else VERBOSE_STREAM_DEFAULT
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request.task},
    ]
    changed_files: list[str] = []
    artifact_filename: str | None = None
    seen_role = "planner"
    run_started_at = time.monotonic()
    total_tokens = 0
    yield _sse(
        "start",
        {
            "turns_allowed": MAX_AGENT_TURNS,
            "roles": _ROLE_SEQUENCE,
            "backend": request.backend or MODEL_BACKEND,
            "model": model_name,
            "verbose_stream": verbose,
        },
    )
    for turn in range(MAX_AGENT_TURNS):
        if verbose:
            yield _sse("turn_start", {"turn": turn})
        turn_started_at = time.monotonic()
        turn_tokens = 0
        try:
            stream = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
                stream=True,
            )
        except APIConnectionError as exc:
            yield _sse(
                "error",
                {
                    "message": (
                        f"Could not reach the model server at {base_url}. "
                        f"Is the model/Ollama server running? ({exc})"
                    ),
                },
            )
            return
        content_parts: list[str] = []
        tool_call_chunks: dict[int, dict[str, Any]] = {}
        finish_reason = None
        suppress_tokens: bool | None = None
        try:
            for chunk in stream:
                choice = chunk.choices[0]
                delta = choice.delta
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                if delta and delta.content:
                    content_parts.append(delta.content)
                    turn_tokens += 1
                    total_tokens += 1
                    if suppress_tokens is None:
                        stripped = "".join(content_parts).lstrip()
                        if stripped:
                            suppress_tokens = stripped[0] in "{`"
                    if not suppress_tokens:
                        yield _sse("token", {"turn": turn, "text": delta.content})
                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        slot = tool_call_chunks.setdefault(
                            tc.index, {"id": None, "name": None, "arguments": ""}
                        )
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function and tc.function.name:
                            slot["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            slot["arguments"] += tc.function.arguments
        except APIConnectionError as exc:
            yield _sse("error", {"message": f"Lost connection to model server mid-stream: {exc}"})
            return
        turn_elapsed = max(time.monotonic() - turn_started_at, 1e-6)
        yield _sse(
            "perf",
            {
                "turn": turn,
                "tokens": turn_tokens,
                "elapsed_seconds": round(turn_elapsed, 3),
                "tokens_per_second": round(turn_tokens / turn_elapsed, 2),
                "total_tokens": total_tokens,
                "total_elapsed_seconds": round(time.monotonic() - run_started_at, 3),
            },
        )
        full_content = "".join(content_parts)
        assistant_message: dict[str, Any] = {"role": "assistant", "content": full_content or None}
        if tool_call_chunks:
            assistant_message["tool_calls"] = [
                {
                    "id": slot["id"] or f"call_{i}",
                    "type": "function",
                    "function": {"name": slot["name"], "arguments": slot["arguments"] or "{}"},
                }
                for i, slot in sorted(tool_call_chunks.items())
            ]
        messages.append(assistant_message)
        if not tool_call_chunks:
            rescued = _extract_fallback_action(full_content)
            if rescued is None:
                yield _sse(
                    "final_answer",
                    {
                        "ok": True,
                        "text": full_content,
                        "changed_files": changed_files,
                        "artifact_filename": artifact_filename,
                    },
                )
                return
            yield _sse(
                "warning",
                {
                    "message": (
                        f"turn {turn}: model emitted a JSON action as plain text instead of a "
                        "native tool call; recovered it automatically."
                    )
                },
            )
            if rescued.action == "final_answer":
                yield _sse(
                    "final_answer",
                    {
                        "ok": True,
                        "text": rescued.answer or "",
                        "changed_files": changed_files,
                        "artifact_filename": artifact_filename,
                    },
                )
                return
            name = rescued.action
            role = _TOOL_TO_ROLE_HINT.get(name, seen_role)
            seen_role = role
            rescued_arguments = rescued.model_dump(exclude_none=True, exclude={"action"})
            if verbose:
                yield _sse("tool_call_start", {"turn": turn, "role": role, "tool": name, "arguments": rescued_arguments})
            try:
                result = _dispatch_tool(name, rescued_arguments, request)
            except PathSecurityError as exc:
                result = {"ok": False, "error": str(exc)}
            except Exception as exc:
                logger.exception("tool=%s failed", name)
                result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            if name == "write_file" and result.get("ok"):
                changed_files.append(result["written"])
            if name == "create_zip" and result.get("ok"):
                artifact_filename = result["artifact"]
            yield _sse(
                "tool_call_end",
                {"turn": turn, "role": role, "tool": name, "arguments": rescued_arguments, "result": result},
            )
            messages.append({"role": "user", "content": f"Tool result: {json.dumps(result)}"})
            continue
        for i, slot in sorted(tool_call_chunks.items()):
            name = slot["name"] or "unknown"
            role = _TOOL_TO_ROLE_HINT.get(name, seen_role)
            seen_role = role
            try:
                arguments = json.loads(slot["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = {}
                result = {"ok": False, "error": "Model produced invalid JSON arguments."}
            else:
                if verbose:
                    yield _sse(
                        "tool_call_start",
                        {"turn": turn, "role": role, "tool": name, "arguments": arguments},
                    )
                try:
                    result = _dispatch_tool(name, arguments, request)
                except PathSecurityError as exc:
                    result = {"ok": False, "error": str(exc)}
                except Exception as exc:  # defensive: never let a tool crash the stream
                    logger.exception("tool=%s failed", name)
                    result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            if name == "write_file" and result.get("ok"):
                changed_files.append(result["written"])
            if name == "create_zip" and result.get("ok"):
                artifact_filename = result["artifact"]
            yield _sse(
                "tool_call_end",
                {"turn": turn, "role": role, "tool": name, "arguments": arguments, "result": result},
            )
            call_id = slot["id"] or f"call_{i}"
            messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result)})
        if finish_reason == "length":
            yield _sse("warning", {"message": "Model hit its output length limit mid-turn."})
    yield _sse(
        "final_answer",
        {
            "ok": False,
            "text": "Turn limit reached. Review the trace and narrow the task.",
            "changed_files": changed_files,
            "artifact_filename": artifact_filename,
        },
    )
def _run_fallback(request: AgentRequest) -> AgentResponse:
    """Constrained single-JSON-action-per-turn loop for models/templates
    that don't reliably support native tool calling."""
    client, base_url, model_name = _resolve_backend(request)
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
                model=model_name,
                messages=messages,
                temperature=0.2,
            )
        except APIConnectionError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Could not reach the model server at {base_url}. ({exc})",
            ) from exc
        raw = completion.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": raw})
        try:
            action = FallbackAction.model_validate_json(raw)
        except ValidationError as exc:
            action = _extract_fallback_action(raw)
            if action is None:
                warnings.append(f"turn {turn}: model emitted invalid action JSON, retrying.")
                messages.append(
                    {
                        "role": "user",
                        "content": f"Invalid action JSON ({exc}). Emit exactly one valid action JSON "
                        "object, with no markdown code fence and no other text.",
                    }
                )
                continue
            warnings.append(
                f"turn {turn}: model wrapped its action JSON in extra text/fencing; recovered it automatically."
            )
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
        "backend": _ACTIVE_SELECTION["backend"],
        "active_model": _ACTIVE_SELECTION["model_name"],
        "ollama_host": OLLAMA_HOST,
        "testing_phase_default": TESTING_PHASE_DEFAULT,
        "verbose_stream_default": VERBOSE_STREAM_DEFAULT,
    }
@app.get("/models")
def get_models() -> dict:
    """Lists selectable models from both backends: the fixed local GGUF
    model (llama.cpp), plus every model Ollama reports installed - local
    and cloud alike - if Ollama is reachable. The cloud/local flag lets
    the UI/CLI label each entry without any extra round trip."""
    llama_cpp_models = [{"name": LLM_MODEL, "backend": "llama-cpp", "cloud": False}]
    ollama_result = ollama_client.list_models()
    ollama_models = [
        {"name": m["name"], "backend": "ollama", "cloud": m["cloud"], "id": m.get("id"), "size_bytes": m.get("size_bytes")}
        for m in ollama_result.get("models", [])
    ]
    return {
        "ok": True,
        "llama_cpp": llama_cpp_models,
        "ollama": {
            "available": ollama_result.get("ok", False),
            "source": ollama_result.get("source"),
            "error": ollama_result.get("error"),
            "models": ollama_models,
        },
        "active": _ACTIVE_SELECTION,
    }
@app.post("/models/select")
def select_model(request: SelectModelRequest) -> dict:
    """Switches the server-wide default backend/model without a restart -
    what both the UI's model switcher and `cli.py --model` call. A
    per-request backend/model_name on /agent or /agent/stream still
    overrides this for that single call."""
    if request.backend == "ollama":
        if not request.model_name:
            raise HTTPException(status_code=400, detail="model_name is required when backend='ollama'.")
        available = ollama_client.list_models()
        if available.get("ok") and available.get("models"):
            names = {m["name"] for m in available["models"]}
            if request.model_name not in names:
                raise HTTPException(
                    status_code=400,
                    detail=f"'{request.model_name}' is not in `ollama list`. Available: {sorted(names)}",
                )
        _ACTIVE_SELECTION["backend"] = "ollama"
        _ACTIVE_SELECTION["model_name"] = request.model_name
    else:
        _ACTIVE_SELECTION["backend"] = "llama-cpp"
        _ACTIVE_SELECTION["model_name"] = LLM_MODEL
    logger.info("model selection changed: backend=%s model=%s", _ACTIVE_SELECTION["backend"], _ACTIVE_SELECTION["model_name"])
    return {"ok": True, "active": _ACTIVE_SELECTION}
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
@app.get("/explorer/download")
def download_explorer_zip(relative_path: str = ".") -> FileResponse:
    """Zips any workspace file or folder (defaults to the whole workspace
    root) on demand and serves it - what the UI's explorer-panel download
    button and the CLI's --download-zip flag both call. Reuses the same
    containment-checked create_zip tool as the agent itself."""
    import uuid
    artifact_name = f"explorer-{uuid.uuid4().hex[:8]}.zip"
    result = create_zip(relative_path, artifact_name)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Zip failed."))
    try:
        path = safe_artifact_path(result["artifact"])
    except (PathSecurityError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    download_name = "workspace.zip" if relative_path in (".", "") else f"{PathLib(relative_path).name}.zip"
    return FileResponse(path, media_type="application/zip", filename=download_name)
@app.get("/artifacts/{filename}")
def download_artifact(filename: str) -> FileResponse:
    try:
        path = safe_artifact_path(filename)
    except PathSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type="application/zip", filename=path.name)
@app.post("/agent/stream")
def run_agent_stream(request: AgentRequest) -> StreamingResponse:
    logger.info(
        "agent stream request received: create_zip=%s allow_commands=%s allow_overwrite=%s",
        request.create_zip,
        request.allow_commands,
        request.allow_overwrite,
    )
    if TOOL_MODE == "fallback":
        def _fallback_wrapper() -> Iterator[str]:
            _, _, model_name = _resolve_backend(request)
            yield _sse(
                "start",
                {
                    "turns_allowed": MAX_AGENT_TURNS,
                    "roles": _ROLE_SEQUENCE,
                    "backend": request.backend or _ACTIVE_SELECTION["backend"],
                    "model": model_name,
                    "verbose_stream": request.verbose_stream if request.verbose_stream is not None else VERBOSE_STREAM_DEFAULT,
                },
            )
            response = _run_fallback(request)
            for trace in response.trace:
                role = _TOOL_TO_ROLE_HINT.get(trace.tool, "planner")
                yield _sse(
                    "tool_call_end",
                    {"turn": 0, "role": role, "tool": trace.tool, "arguments": trace.arguments, "result": trace.result},
                )
            yield _sse(
                "final_answer",
                {
                    "ok": response.ok,
                    "text": response.final_answer,
                    "changed_files": response.changed_files,
                    "artifact_filename": response.artifact_filename,
                },
            )
        return StreamingResponse(_fallback_wrapper(), media_type="text/event-stream")
    return StreamingResponse(_stream_native(request), media_type="text/event-stream")
@app.get("/projects")
def get_projects() -> dict:
    return list_projects()
@app.post("/projects/import")
def post_import_project(request: ImportProjectRequest) -> dict:
    result = import_project(request.source_path, request.project_name)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Import failed."))
    return result
@app.get("/tree")
def get_tree(relative_path: str = ".") -> dict:
    result = file_tree(relative_path)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Not found."))
    return result
@app.get("/file")
def get_file(relative_path: str) -> dict:
    result = read_file(relative_path)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Not found."))
    return result
@app.put("/file")
def put_file(relative_path: str, body: FileWriteRequest) -> dict:
    result = write_file(relative_path, body.content, allow_overwrite=body.allow_overwrite)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Write failed."))
    return result
_UI_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")
if os.path.isdir(_UI_DIR):
    app.mount("/", StaticFiles(directory=_UI_DIR, html=True), name="ui")