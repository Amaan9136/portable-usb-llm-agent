"""
Secure, containment-first tool implementations.

Every function here is defensive by default: it assumes the caller
(including the LLM) is untrusted input, not a cooperative partner.
Nothing here reads environment variables, credentials, SSH keys, or any
path outside WORKSPACE/ARTIFACTS. Deletion is permanently disabled.

Threat model assumptions (see SECURITY.md for the full writeup):
  - The model may hallucinate or be adversarially prompted (e.g. via
    content it reads from a file) to attempt path traversal, absolute
    paths, or disallowed commands.
  - All such attempts must fail closed with a clear error, not a
    partial/undefined action.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path, PureWindowsPath

from config import (
    ARTIFACTS,
    COMMAND_TIMEOUT_SECONDS,
    MAX_FILE_READ_BYTES,
    MAX_FILE_WRITE_BYTES,
    MAX_TOOL_OUTPUT_BYTES,
    WORKSPACE,
)

# Only these executables may ever be invoked. Checked against the raw
# first argument BEFORE any path resolution, so "python" cannot be
# smuggled in as "C:\Windows\System32\python.exe" to dodge the allowlist
# semantics - we still only accept the bare command name and let the OS
# resolve it from PATH, which keeps behavior predictable and auditable.
ALLOWED_COMMANDS = {"python", "pytest", "npm", "node", "git"}

# Explicitly called out in the spec as must-block, even though they're
# not in ALLOWED_COMMANDS anyway (defense in depth - this list exists so
# a future edit to ALLOWED_COMMANDS can't accidentally re-admit these,
# and so error messages are more specific for common LLM mistakes).
EXPLICITLY_BLOCKED = {
    "powershell", "powershell.exe", "pwsh",
    "cmd", "cmd.exe",
    "bash", "sh", "zsh",
    "curl", "wget",
    "ssh", "scp", "sftp",
    "rm", "del", "erase",
    "format",
    "shutdown", "restart-computer",
    "reg", "regedit",
    "choco", "winget", "scoop",
    "netsh", "netstat", "ping", "nslookup", "telnet",
}

# Windows reserved device names - creating a file with one of these
# stems (with or without an extension) has special OS meaning and must
# be rejected regardless of the requested extension.
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class PathSecurityError(ValueError):
    """Raised when a requested path fails containment checks."""


def _reject_reserved_names(relative_path: str) -> None:
    for part in PureWindowsPath(relative_path).parts:
        stem = part.split(".")[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise PathSecurityError(
                f"Blocked: '{part}' is a reserved Windows device name."
            )


def _reject_absolute_or_drive(relative_path: str) -> None:
    # Reject POSIX-absolute ("/etc/passwd"), Windows-absolute
    # ("C:\\Windows"), UNC paths ("\\\\server\\share"), and drive-relative
    # paths ("C:foo") - PureWindowsPath.is_absolute() alone does not
    # reliably catch every one of these on a POSIX host, so check
    # multiple signals explicitly.
    if os.path.isabs(relative_path):
        raise PathSecurityError("Blocked: absolute paths are not allowed.")

    win_path = PureWindowsPath(relative_path)
    if win_path.drive or win_path.root:
        raise PathSecurityError("Blocked: drive letters and rooted paths are not allowed.")

    if relative_path.startswith("\\\\") or relative_path.startswith("//"):
        raise PathSecurityError("Blocked: UNC-style paths are not allowed.")

    if re.match(r"^[a-zA-Z]:", relative_path):
        raise PathSecurityError("Blocked: drive-relative paths are not allowed.")


def safe_workspace_path(relative_path: str) -> Path:
    """Resolve relative_path against WORKSPACE and guarantee the result
    stays inside WORKSPACE, including after symlink resolution.

    Raises PathSecurityError on any traversal, absolute-path, drive,
    UNC, or reserved-name attempt.
    """
    if not relative_path or not relative_path.strip():
        raise PathSecurityError("Blocked: empty path.")

    _reject_absolute_or_drive(relative_path)
    _reject_reserved_names(relative_path)

    candidate = (WORKSPACE / relative_path).resolve()

    # resolve() follows symlinks. If a symlink inside workspace points
    # outside it, the resolved path will land outside WORKSPACE and this
    # check catches it - same mechanism handles plain ".." traversal.
    try:
        candidate.relative_to(WORKSPACE)
    except ValueError as exc:
        raise PathSecurityError(
            "Blocked: path escapes the workspace directory."
        ) from exc

    return candidate


def _truncate(text: str, limit: int = MAX_TOOL_OUTPUT_BYTES) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text
    return encoded[-limit:].decode("utf-8", errors="replace")


def list_files(relative_path: str = ".") -> dict:
    try:
        path = safe_workspace_path(relative_path)
    except PathSecurityError as exc:
        return {"ok": False, "error": str(exc)}

    if not path.exists():
        return {"ok": False, "error": "Path does not exist."}

    if path.is_file():
        return {"ok": True, "files": [str(path.relative_to(WORKSPACE))]}

    files = [
        str(item.relative_to(WORKSPACE))
        for item in sorted(path.rglob("*"))
        if item.is_file() and ".git" not in item.parts
    ]
    return {"ok": True, "files": files[:500], "truncated": len(files) > 500}


def read_file(relative_path: str) -> dict:
    try:
        path = safe_workspace_path(relative_path)
    except PathSecurityError as exc:
        return {"ok": False, "error": str(exc)}

    if not path.is_file():
        return {"ok": False, "error": "File does not exist."}

    if path.stat().st_size > MAX_FILE_READ_BYTES:
        return {
            "ok": False,
            "error": f"File exceeds {MAX_FILE_READ_BYTES} byte read limit.",
        }

    return {"ok": True, "content": path.read_text(encoding="utf-8", errors="replace")}


def write_file(relative_path: str, content: str, allow_overwrite: bool = False) -> dict:
    try:
        path = safe_workspace_path(relative_path)
    except PathSecurityError as exc:
        return {"ok": False, "error": str(exc)}

    if len(content.encode("utf-8", errors="replace")) > MAX_FILE_WRITE_BYTES:
        return {
            "ok": False,
            "error": f"Content exceeds {MAX_FILE_WRITE_BYTES} byte write limit.",
        }

    if path.exists() and not allow_overwrite:
        return {
            "ok": False,
            "error": (
                "File already exists. Overwriting requires the request's "
                "allow_overwrite flag to be true."
            ),
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"ok": True, "written": str(path.relative_to(WORKSPACE))}


def run_command(
    command: list[str],
    relative_cwd: str = ".",
    allow_commands: bool = False,
) -> dict:
    if not allow_commands:
        return {
            "ok": False,
            "error": "Blocked: run_command requires allow_commands: true on the request.",
        }

    if not command or not isinstance(command, list):
        return {"ok": False, "error": "Command must be a non-empty list."}

    executable = command[0].strip().lower()

    if executable in EXPLICITLY_BLOCKED:
        return {"ok": False, "error": f"Blocked command: '{executable}' is explicitly disallowed."}

    if executable not in ALLOWED_COMMANDS:
        return {
            "ok": False,
            "error": f"Blocked command: '{executable}'. Allowed: {sorted(ALLOWED_COMMANDS)}",
        }

    try:
        cwd = safe_workspace_path(relative_cwd)
    except PathSecurityError as exc:
        return {"ok": False, "error": str(exc)}

    if not cwd.is_dir():
        return {"ok": False, "error": "Working directory does not exist."}

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            shell=False,  # never shell=True - no shell metacharacter expansion
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": _truncate(completed.stdout),
            "stderr": _truncate(completed.stderr),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"Command exceeded the {COMMAND_TIMEOUT_SECONDS}-second timeout.",
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "error": f"Executable '{executable}' not found on PATH.",
        }


def create_zip(source_relative_path: str, artifact_name: str) -> dict:
    try:
        source = safe_workspace_path(source_relative_path)
    except PathSecurityError as exc:
        return {"ok": False, "error": str(exc)}

    if not source.exists():
        return {"ok": False, "error": "Source path does not exist."}

    # artifact_name is sanitized independently of workspace path rules:
    # it must resolve to a plain filename inside ARTIFACTS, never a
    # nested path. Use PureWindowsPath (not the platform-default Path)
    # so this is correct even when the agent runs on a non-Windows host
    # (e.g. this test suite on Linux) - PureWindowsPath understands
    # backslash separators and drive letters the way the actual deployed
    # Windows target will, whereas a POSIX PurePath would treat
    # "..\\..\\evil" as a single opaque filename and let it through.
    win_name = PureWindowsPath(artifact_name)
    if win_name.drive or win_name.root:
        return {"ok": False, "error": "Invalid artifact name: absolute or rooted names are not allowed."}

    safe_stem = win_name.name
    if not safe_stem or safe_stem in (".", "..") or len(win_name.parts) > 1:
        return {"ok": False, "error": "Invalid artifact name: must be a plain filename, no path separators."}

    if not safe_stem.lower().endswith(".zip"):
        safe_stem += ".zip"

    output = (ARTIFACTS / safe_stem).resolve()
    try:
        output.relative_to(ARTIFACTS)
    except ValueError:
        return {"ok": False, "error": "Invalid artifact name."}

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        if source.is_file():
            archive.write(source, source.name)
        else:
            for file in source.rglob("*"):
                if file.is_file() and ".git" not in file.parts:
                    archive.write(file, file.relative_to(source.parent))

    return {"ok": True, "artifact": output.name}


def delete_path(*_args, **_kwargs) -> dict:
    """Deletion is deliberately and permanently disabled. See SECURITY.md."""
    return {
        "ok": False,
        "error": "Deletion is deliberately disabled. Delete files manually after review.",
    }


def safe_artifact_path(filename: str) -> Path:
    """Used by the API's download endpoint. Only serves .zip files that
    live directly inside ARTIFACTS, never a subdirectory or traversal."""
    if not filename or "/" in filename or "\\" in filename:
        raise PathSecurityError("Blocked: filename must not contain path separators.")

    if not filename.lower().endswith(".zip"):
        raise PathSecurityError("Blocked: only .zip files may be downloaded.")

    candidate = (ARTIFACTS / filename).resolve()
    try:
        candidate.relative_to(ARTIFACTS)
    except ValueError as exc:
        raise PathSecurityError("Blocked: path escapes the artifacts directory.") from exc

    if not candidate.is_file():
        raise FileNotFoundError("Artifact does not exist.")

    return candidate