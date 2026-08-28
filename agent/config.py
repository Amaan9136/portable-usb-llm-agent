"""
Central configuration for the PortableCoder agent.

Values here are defaults. The actual runtime values used by Start-Model.bat
come from .env.example (see .env.example at the project root) — this
module independently reads the SAME .env.example so the Python agent and the
batch-launched model server agree on ports without duplicating numbers by
hand in two places.

Deliberately no external config library (python-dotenv, etc.) to keep
dependencies minimal — .env.example has a trivial KEY=VALUE format.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = (ROOT / "workspace").resolve()
ARTIFACTS = (ROOT / "artifacts").resolve()
LOGS = (ROOT / "logs").resolve()
CONFIG_ENV_PATH = ROOT / ".env.example"


def _load_config_env(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE file. Ignores blank lines and lines
    starting with '#'. Does not support quoting, escaping, or multi-line
    values — intentionally minimal."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()

    return values


_FILE_VALUES = _load_config_env(CONFIG_ENV_PATH)


def _get(key: str, default: str) -> str:
    """Precedence: real environment variable > .env.example file > default.
    Environment variable wins so a user can override at launch time
    without editing files, e.g. `set AGENT_PORT=9000 && Start-Agent.bat`."""
    return os.environ.get(key, _FILE_VALUES.get(key, default))


MODEL_PORT = int(_get("MODEL_PORT", "8080"))
AGENT_PORT = int(_get("AGENT_PORT", "8787"))
LLM_BASE_URL = f"http://127.0.0.1:{MODEL_PORT}/v1"
LLM_MODEL = _get("LLM_MODEL_NAME", "qwen2.5-coder-7b-instruct")
LLM_API_KEY = "local-no-key"  # llama.cpp's server does not require a real key

# Agent control-loop budgets. Kept intentionally conservative because this
# targets a 7B model on a 4 GB VRAM laptop GPU with partial CPU offload —
# generation is not fast, and each of the 5 sequential roles (planner,
# implementer, reviewer, tester, packager) consumes turns and wall-clock
# time. If you increase context or expect longer sessions, raise these
# deliberately rather than assuming they scale for free.
MAX_AGENT_TURNS = int(_get("MAX_AGENT_TURNS", "12"))
COMMAND_TIMEOUT_SECONDS = int(_get("COMMAND_TIMEOUT_SECONDS", "90"))

MAX_TASK_LENGTH = 12_000
MAX_FILE_READ_BYTES = 500_000
MAX_FILE_WRITE_BYTES = 2_000_000
MAX_TOOL_OUTPUT_BYTES = 12_000

for _dir in (WORKSPACE, ARTIFACTS, LOGS):
    _dir.mkdir(parents=True, exist_ok=True)
