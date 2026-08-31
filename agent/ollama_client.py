"""
Ollama discovery helpers.

Optional, opt-in integration - never used unless MODEL_BACKEND=ollama is
set (or the UI/CLI explicitly asks to list/select an Ollama model). Two
paths are supported for listing installed models:

  1. HTTP API (preferred): GET {OLLAMA_HOST}/api/tags against a locally
     running `ollama serve`. Fast, structured, no subprocess needed.
  2. CLI fallback: shells out to `ollama list` and parses the tabular
     output, for hosts where the API is unreachable but the `ollama`
     binary is on PATH and the background service still works via CLI.

Both a model's local size and its "-cloud" suffix (Ollama's naming
convention for cloud-hosted models proxied through the same local
daemon) are surfaced so the caller can label cloud vs local models in
the UI without guessing.
"""
from __future__ import annotations

import re
import subprocess
from typing import Any

import httpx

from config import OLLAMA_EXE, OLLAMA_HOST


class OllamaUnavailableError(RuntimeError):
    """Raised when neither the API nor the CLI could reach Ollama."""


def _is_cloud(name: str) -> bool:
    return name.lower().endswith("-cloud") or ":cloud" in name.lower() or name.lower().endswith(":cloud")


def _via_api() -> list[dict[str, Any]]:
    url = f"{OLLAMA_HOST.rstrip('/')}/api/tags"
    with httpx.Client(timeout=5.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

    models = []
    for m in data.get("models", []):
        name = m.get("name") or m.get("model") or ""
        models.append(
            {
                "name": name,
                "id": (m.get("digest") or "")[:12],
                "size_bytes": m.get("size"),
                "modified_at": m.get("modified_at"),
                "cloud": _is_cloud(name),
            }
        )
    return models


_LIST_LINE_RE = re.compile(
    r"^(?P<name>\S+)\s+(?P<id>[0-9a-fA-F]{6,})\s+(?P<size>[\d.]+\s*[A-Za-z]+|-)\s+(?P<modified>.+)$"
)


def _via_cli() -> list[dict[str, Any]]:
    try:
        completed = subprocess.run(
            [OLLAMA_EXE, "list"],
            capture_output=True,
            text=True,
            timeout=15,
            shell=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise OllamaUnavailableError(f"Could not run '{OLLAMA_EXE} list': {exc}") from exc

    if completed.returncode != 0:
        raise OllamaUnavailableError(
            f"'{OLLAMA_EXE} list' exited with {completed.returncode}: {completed.stderr.strip()}"
        )

    lines = completed.stdout.strip().splitlines()
    if not lines:
        return []

    models = []
    for line in lines[1:]:
        line = line.rstrip()
        if not line:
            continue
        match = _LIST_LINE_RE.match(line)
        if not match:
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            models.append({"name": name, "id": "", "size_bytes": None, "modified_at": None, "cloud": _is_cloud(name)})
            continue
        name = match.group("name")
        size_text = match.group("size").strip()
        models.append(
            {
                "name": name,
                "id": match.group("id"),
                "size_bytes": None if size_text == "-" else size_text,
                "modified_at": match.group("modified").strip(),
                "cloud": _is_cloud(name),
            }
        )
    return models


def list_models() -> dict:
    """Return {"ok": True, "models": [...], "source": "api"|"cli"} or
    {"ok": False, "error": ...} - never raises."""
    try:
        models = _via_api()
        return {"ok": True, "models": models, "source": "api"}
    except (httpx.HTTPError, ValueError):
        pass

    try:
        models = _via_cli()
        return {"ok": True, "models": models, "source": "cli"}
    except OllamaUnavailableError as exc:
        return {"ok": False, "error": str(exc), "models": []}


def is_available() -> bool:
    result = list_models()
    return result.get("ok", False)
