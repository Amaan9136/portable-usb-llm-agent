"""Typed request/response schemas for the agent API and for the
fallback JSON action protocol used when the local model does not
support native tool calling."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from config import MAX_TASK_LENGTH


class AgentRequest(BaseModel):
    task: str = Field(min_length=3, max_length=MAX_TASK_LENGTH)
    project_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional short name used for logging/artifact naming hints only.",
    )
    create_zip: bool = Field(
        default=False,
        description="If true, the Packager role will create a ZIP artifact after a successful run.",
    )
    allow_commands: bool = Field(
        default=False,
        description=(
            "Must be explicitly true for run_command to execute. Defaults to false "
            "so the agent cannot run tests/commands without the caller opting in."
        ),
    )
    allow_overwrite: bool = Field(
        default=False,
        description="Must be explicitly true to let write_file overwrite an existing file.",
    )


class ToolCallTrace(BaseModel):
    tool: str
    arguments: dict
    result: dict


class AgentResponse(BaseModel):
    ok: bool
    changed_files: list[str] = Field(default_factory=list)
    command_results: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    final_answer: str = ""
    artifact_filename: Optional[str] = None
    trace: list[ToolCallTrace] = Field(default_factory=list)


# --- Fallback JSON action protocol -----------------------------------
# Used only if the local model does not reliably emit native OpenAI-style
# tool_calls (some GGUF/server/template combinations vary in how well
# they support function calling). The system prompt instructs the model
# to emit exactly one JSON object matching this shape per turn instead.

class FallbackAction(BaseModel):
    action: Literal[
        "list_files",
        "read_file",
        "write_file",
        "run_command",
        "create_zip",
        "final_answer",
    ]
    relative_path: Optional[str] = None
    content: Optional[str] = None
    command: Optional[list[str]] = None
    relative_cwd: Optional[str] = "."
    source_relative_path: Optional[str] = None
    artifact_name: Optional[str] = None
    answer: Optional[str] = None