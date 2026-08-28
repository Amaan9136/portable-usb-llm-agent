"""
Verifies the local environment is ready to run PortableCoder:
  - Python version
  - llama-server.exe present in runtime/windows/
  - Model file present in models/
  - Free disk space on the drive this project lives on
  - nvidia-smi availability (optional — informational only)

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
EXPECTED_MODEL = MODELS_DIR / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"

MIN_PYTHON = (3, 10)
MIN_FREE_GB = 2.0  # headroom beyond the ~4.7 GB model + venv + generated projects


def check_python() -> tuple[bool, str]:
    version = sys.version_info
    ok = (version.major, version.minor) >= MIN_PYTHON
    label = f"Python {version.major}.{version.minor}.{version.micro}"
    if not ok:
        return False, f"{label} — need >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    return True, label


def check_llama_server() -> tuple[bool, str]:
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


def check_model_file() -> tuple[bool, str]:
    if not EXPECTED_MODEL.is_file():
        return False, f"Not found at {EXPECTED_MODEL}. See scripts/download_model.py."

    size_gb = EXPECTED_MODEL.stat().st_size / 1e9
    if size_gb < 3.5:
        return False, f"File exists but is only {size_gb:.2f} GB — looks incomplete. Re-download."
    return True, f"Found, {size_gb:.2f} GB."


def check_disk_space() -> tuple[bool, str]:
    usage = shutil.disk_usage(ROOT)
    free_gb = usage.free / 1e9
    ok = free_gb >= MIN_FREE_GB
    return ok, f"{free_gb:.2f} GB free on this drive."


def check_nvidia_smi() -> tuple[bool, str]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return True, "nvidia-smi not found on PATH (optional — only needed for GPU tuning)."

    try:
        result = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=10)
        return True, result.stdout.strip() or "nvidia-smi ran but returned no output."
    except Exception as exc:  # noqa: BLE001
        return True, f"nvidia-smi found but failed to run: {exc}"


def main() -> int:
    checks = [
        ("Python version", check_python),
        ("llama-server.exe", check_llama_server),
        ("Model file", check_model_file),
        ("Free disk space", check_disk_space),
        ("nvidia-smi (optional)", check_nvidia_smi),
    ]

    print("PortableCoder — Environment Verification")
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
        print("One or more required checks failed — see FAIL lines above.")

    return 0 if all_required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
