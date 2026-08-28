"""
Model download helper for Portable USB LLM Agent.

This script deliberately does NOT silently fetch a model from a hardcoded
URL — GGUF repository layouts and filenames on Hugging Face (and similar
hosts) change over time, and a stale hardcoded URL either breaks or,
worse, silently pulls a different file than you expect. Instead this
script:

  1. Prints general guidance for finding and choosing a GGUF model that
     fits your hardware, and shows the destination path this project
     expects (read from MODEL_PATH in .env / .env.example).
  2. If you pass --url explicitly, downloads that one URL yourself (you
     are asserting you've verified it), with a progress indicator and a
     SHA256 print at the end so you can cross-check it against the
     repository's listed checksum if one is published.

This project is not tied to any specific model — pick whatever GGUF
model (any size/quantization your hardware can run) works for you, set
MODEL_PATH and LLM_MODEL_NAME in .env to match, and use this script only
as an optional download convenience.

Usage:
    python scripts/download_model.py                 # prints instructions only
    python scripts/download_model.py --url <direct-file-url>
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
DEFAULT_ENV_PATH = ROOT / ".env"
DEFAULT_ENV_EXAMPLE_PATH = ROOT / ".env.example"


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


def _configured_model_path() -> Path:
    """MODEL_PATH from .env, falling back to .env.example, then a
    generic default — same precedence as agent/config.py."""
    values = {
        **_load_env(DEFAULT_ENV_EXAMPLE_PATH),
        **_load_env(DEFAULT_ENV_PATH),
    }
    raw = values.get("MODEL_PATH", "models\\your-model.gguf")
    return ROOT / raw.replace("\\", "/")


def _instructions(destination: Path) -> str:
    return f"""
Portable USB LLM Agent — Model Download Guide
=====================================

This project is model-agnostic: any GGUF-format model works, as long as
llama-server.exe can load it and your hardware can run it. Pick a model
that fits your GPU/VRAM (or CPU/RAM if running CPU-only) and your use
case (e.g. a coding-focused instruct model for this agent's workflow).

WHERE TO GET ONE
------------------
1. Search Hugging Face (or another trusted host) for GGUF builds of the
   model you want, e.g. "<model-name>-GGUF". Prefer the official
   publisher's org account, or a well-known quantizer, over an unverified
   re-upload — unless you've checked the re-upload's checksum yourself.

2. Pick a quantization level (e.g. Q4_K_M, Q5_K_M, Q8_0) that fits your
   available VRAM/RAM. Smaller quant = less memory, lower quality;
   larger quant = more memory, higher quality. Q4_K_M is a common
   starting point for constrained hardware.

3. If the model is split into multiple parts (filenames ending in
   "-00001-of-00002.gguf" etc.), download ALL parts, then merge with:
       llama-gguf-split --merge <part1> <merged-output.gguf>
   (ships alongside llama-server.exe in most llama.cpp release archives —
   check runtime\\windows\\ after you've placed your build there.)

4. Place the final single .gguf file at the path configured by
   MODEL_PATH in your .env (currently resolves to):
       {destination}
   If you use a different path/filename, update MODEL_PATH in .env to
   match — Start-Model.bat, verify_environment.py, and this script all
   read that same setting.

5. Also set LLM_MODEL_NAME in .env to the model name string
   llama-server.exe reports for the file you loaded — check
   `/v1/models` on the running server, or its startup log, if unsure.

6. Sanity-check the downloaded file size against what the repository
   lists for that quantization. A drastically smaller file usually means
   an interrupted download — re-download it.

DO NOT AUTOMATICALLY TRUST OTHER MODELS
------------------------------------------
This script will not download an arbitrary URL without --url, and even
then, only fetches exactly the one URL you provide — verify it yourself
before passing it. Never point this at an untrusted or unofficial mirror
without checking published checksums first.
"""


def _download(url: str, destination: Path) -> None:
    print(f"Downloading:\n  {url}\n-> {destination}\n")
    destination.parent.mkdir(parents=True, exist_ok=True)

    def _report(block_num: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        downloaded = block_num * block_size
        pct = min(100, downloaded * 100 // total_size)
        sys.stdout.write(f"\r  {pct:3d}%  ({downloaded / 1e9:.2f} GB / {total_size / 1e9:.2f} GB)")
        sys.stdout.flush()

    urllib.request.urlretrieve(url, destination, reporthook=_report)
    print("\nDownload complete. Computing SHA256 (this may take a minute)...")

    sha256 = hashlib.sha256()
    with open(destination, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(chunk)

    print(f"SHA256: {sha256.hexdigest()}")
    print("Cross-check this against the checksum published in the model")
    print("repository, if one is listed, before trusting this file.")


def main() -> int:
    default_destination = _configured_model_path()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        help="Direct download URL for the GGUF file. Only used if you provide it explicitly.",
    )
    parser.add_argument(
        "--filename",
        default=default_destination.name,
        help=f"Destination filename inside models/ (default: from MODEL_PATH in .env, currently {default_destination.name})",
    )
    args = parser.parse_args()

    print(_instructions(default_destination))

    if not args.url:
        print("No --url provided. Instructions only — nothing downloaded.")
        return 0

    destination = MODELS_DIR / args.filename
    if destination.exists():
        print(f"[ERROR] {destination} already exists. Remove it first if you want to re-download.")
        return 1

    try:
        _download(args.url, destination)
    except Exception as exc:  # noqa: BLE001 - top-level CLI error reporting
        print(f"[ERROR] Download failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
