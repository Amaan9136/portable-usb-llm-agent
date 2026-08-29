"""
Verifies the local environment is ready to run Portable USB LLM Agent:
  - Python version
  - A usable backend: runtime/windows/llama-server.exe, or a llama.exe
    ("serve" subcommand) build, per BACKEND in .env
  - Model file present at MODEL_PATH (from .env / .env.example)
  - Free disk space on the drive this project lives on
  - nvidia-smi availability (optional - informational only)

Run this before your first Start-Model.bat / Start-Agent.bat.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
RUNTIME_EXE = ROOT / "runtime" / "windows" / "llama-server.exe"
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"

MIN_PYTHON = (3, 10)
MIN_FREE_GB = 2.0  # headroom beyond the model file + venv + generated projects


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _configured_values() -> dict[str, str]:
    return {**_load_env(ENV_EXAMPLE_PATH), **_load_env(ENV_PATH)}


def _configured_model_path() -> Path:
    raw = _configured_values().get("MODEL_PATH", "models\\your-model.gguf")
    return ROOT / raw.replace("\\", "/")


EXPECTED_MODEL = _configured_model_path()
_CONFIG = _configured_values()
BACKEND = _CONFIG.get("BACKEND", "auto").strip().lower()
LLAMA_EXE = _CONFIG.get("LLAMA_EXE", "llama.exe").strip()


def check_python() -> tuple[bool, str]:
    version = sys.version_info
    ok = (version.major, version.minor) >= MIN_PYTHON
    label = f"Python {version.major}.{version.minor}.{version.micro}"
    if not ok:
        return False, f"{label} - need >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    return True, label


def _check_llama_server_exe() -> tuple[bool, str]:
    if not RUNTIME_EXE.is_file():
        return False, f"Not found at {RUNTIME_EXE}. See runtime/windows/README.txt."

    try:
        result = subprocess.run(
            [str(RUNTIME_EXE), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        version_text = (result.stdout + result.stderr).strip().splitlines()
        summary = version_text[0] if version_text else "(no version output)"
        return True, f"Found. {summary}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Found but failed to run --version: {exc}"


def _check_llama_exe() -> tuple[bool, str]:
    resolved = shutil.which(LLAMA_EXE) or (LLAMA_EXE if Path(LLAMA_EXE).is_file() else None)
    if not resolved:
        return False, f'"{LLAMA_EXE}" not found on PATH or as a direct path. Set LLAMA_EXE in .env.'

    try:
        result = subprocess.run(
            [resolved, "serve", "--help"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        version_text = (result.stdout + result.stderr).strip().splitlines()
        summary = version_text[0] if version_text else "(no output)"
        return True, f"Found at {resolved}. {summary}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Found at {resolved} but failed to run 'serve --help': {exc}"


def check_backend() -> tuple[bool, str]:
    if BACKEND == "llama-server":
        return _check_llama_server_exe()
    if BACKEND == "llama-cli":
        return _check_llama_exe()
    if BACKEND != "auto":
        return False, f'Unknown BACKEND="{BACKEND}" in .env (expected auto, llama-server, or llama-cli).'

    ok, detail = _check_llama_server_exe()
    if ok:
        return True, f"[llama-server] {detail}"
    ok, detail = _check_llama_exe()
    if ok:
        return True, f"[llama-cli] {detail}"
    return False, (
        f"Neither runtime\\windows\\llama-server.exe nor \"{LLAMA_EXE}\" (llama-cli) "
        "was found. See runtime/windows/README.txt."
    )


def check_model_file() -> tuple[bool, str]:
    if not EXPECTED_MODEL.is_file():
        return False, f"Not found at {EXPECTED_MODEL} (MODEL_PATH in .env). See scripts/download_model.py."

    size_gb = EXPECTED_MODEL.stat().st_size / 1e9
    if size_gb < 0.05:
        return False, f"File exists but is only {size_gb:.3f} GB - looks incomplete or empty. Re-download."
    return True, f"Found, {size_gb:.2f} GB."


def check_disk_space() -> tuple[bool, str]:
    usage = shutil.disk_usage(ROOT)
    free_gb = usage.free / 1e9
    ok = free_gb >= MIN_FREE_GB
    return ok, f"{free_gb:.2f} GB free on this drive."


def check_nvidia_smi() -> tuple[bool, str]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return True, "nvidia-smi not found on PATH (optional - only relevant for NVIDIA GPU tuning)."

    try:
        result = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=10)
        return True, result.stdout.strip() or "nvidia-smi ran but returned no output."
    except Exception as exc:  # noqa: BLE001
        return True, f"nvidia-smi found but failed to run: {exc}"


def main() -> int:
    checks = [
        ("Python version", check_python),
        ("Model server backend", check_backend),
        ("Model file", check_model_file),
        ("Free disk space", check_disk_space),
        ("nvidia-smi (optional)", check_nvidia_smi),
    ]

    print("Portable USB LLM Agent - Environment Verification")
    print("=" * 45)

    all_required_ok = True
    for label, fn in checks:
        ok, detail = fn()
        marker = "OK  " if ok else "FAIL"
        print(f"[{marker}] {label}: {detail}")
        if not ok and label != "nvidia-smi (optional)":
            all_required_ok = False

    print("=" * 45)
    if all_required_ok:
        print("Environment looks ready. Run Start-Model.bat, then Start-Agent.bat.")
    else:
        print("One or more required checks failed - see FAIL lines above.")

    return 0 if all_required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())