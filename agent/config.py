"""
Central configuration for the Portable USB LLM Agent agent.

All tunable values live in .env (copied from .env.example at the project
root). This module and the batch launchers both read that same file, so
the Python agent and the batch-launched model server always agree -
nothing model- or backend-specific is hardcoded here.

Deliberately no external config library (python-dotenv, etc.) to keep
dependencies minimal - .env has a trivial KEY=VALUE format.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = (ROOT / "workspace").resolve()
ARTIFACTS = (ROOT / "artifacts").resolve()
LOGS = (ROOT / "logs").resolve()
CONFIG_ENV_PATH = ROOT / ".env"
CONFIG_ENV_EXAMPLE_PATH = ROOT / ".env.example"


def _load_config_env(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE file. Ignores blank lines and lines
    starting with '#'. Does not support quoting, escaping, or multi-line
    values - intentionally minimal."""
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


# Precedence: .env.example (base defaults) < .env (user overrides).
# If the user never copied .env.example to .env, .env.example alone still
# provides working defaults.
_FILE_VALUES = {
    **_load_config_env(CONFIG_ENV_EXAMPLE_PATH),
    **_load_config_env(CONFIG_ENV_PATH),
}


def _get(key: str, default: str) -> str:
    """Precedence: real environment variable > .env > .env.example > default.
    Environment variable wins so a user can override at launch time
    without editing files, e.g. `set AGENT_PORT=9000 && Start-Agent.bat`."""
    return os.environ.get(key, _FILE_VALUES.get(key, default))


MODEL_PORT = int(_get("MODEL_PORT", "8080"))
AGENT_PORT = int(_get("AGENT_PORT", "8787"))
LLM_BASE_URL = f"http://127.0.0.1:{MODEL_PORT}/v1"
LLM_MODEL = _get("LLM_MODEL_NAME", "local-model")
LLM_API_KEY = "local-no-key"  # llama.cpp's server does not require a real key
TOOL_MODE = _get("TOOL_MODE", "native")  # "native" or "fallback"

# Agent control-loop budgets. Defaults are conservative since they must
# work for small, quantized local models on modest hardware, and each of
# the 5 sequential roles (planner, implementer, reviewer, tester,
# packager) consumes turns and wall-clock time. Raise deliberately in
# .env if your model/hardware can handle more.
MAX_AGENT_TURNS = int(_get("MAX_AGENT_TURNS", "12"))
COMMAND_TIMEOUT_SECONDS = int(_get("COMMAND_TIMEOUT_SECONDS", "90"))

MAX_TASK_LENGTH = 12_000
MAX_FILE_READ_BYTES = 500_000
MAX_FILE_WRITE_BYTES = 2_000_000
MAX_TOOL_OUTPUT_BYTES = 12_000

for _dir in (WORKSPACE, ARTIFACTS, LOGS):
    _dir.mkdir(parents=True, exist_ok=True)