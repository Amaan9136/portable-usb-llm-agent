"""
Model download helper for PortableCoder.

This script deliberately does NOT silently fetch a model from a hardcoded
URL — GGUF repository layouts and filenames on Hugging Face change over
time, and a stale hardcoded URL either breaks or, worse, silently pulls a
different file than you expect. Instead this script:

  1. Prints the exact official repository to visit and the file to look
     for.
  2. If you pass --url explicitly, downloads that one URL yourself (you
     are asserting you've verified it), with a progress indicator and a
     SHA256 print at the end so you can cross-check it against the
     repository's listed checksum if one is published.

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
EXPECTED_FILENAME = "qwen2.5-coder-7b-instruct-q4_k_m.gguf"

INSTRUCTIONS = f"""
PortableCoder — Model Download Guide
=====================================

This project targets: Qwen2.5-Coder-7B-Instruct, GGUF format, Q4_K_M
quantization only. Do NOT substitute the 14B or 32B variants — they will
not fit this project's VRAM/turn-budget assumptions (see README.md).

WHERE TO GET IT
------------------
1. Go to the official Qwen model repository on Hugging Face. Search for:
       "Qwen2.5-Coder-7B-Instruct-GGUF"
   and verify the repository is published under the official Qwen /
   Alibaba organization account, not a third-party re-upload, unless you
   have independently verified a re-upload's checksum against the
   original.

2. In that repository's file list, find the file named (or matching):
       {EXPECTED_FILENAME}
   Some repositories quantize multiple sizes into one repo — make sure
   you select Q4_K_M specifically, not Q4_0, Q5_K_M, Q8_0, etc.

3. If the model is split into multiple parts (e.g. filenames ending in
   "-00001-of-00002.gguf"), download ALL parts, then merge them with:
       llama-gguf-split --merge <part1> {EXPECTED_FILENAME}
   (llama-gguf-split ships alongside llama-server.exe in most llama.cpp
   release archives — check runtime\\windows\\ after you've placed your
   llama.cpp build there.)

4. Place the final single .gguf file at:
       {MODELS_DIR / EXPECTED_FILENAME}

5. Verify the file size looks right: Q4_K_M for this model is
   approximately 4.4–4.7 GB. If your downloaded file is drastically
   smaller, the download likely failed partway — re-download.

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        help="Direct download URL for the GGUF file. Only used if you provide it explicitly.",
    )
    parser.add_argument(
        "--filename",
        default=EXPECTED_FILENAME,
        help=f"Destination filename inside models/ (default: {EXPECTED_FILENAME})",
    )
    args = parser.parse_args()

    print(INSTRUCTIONS)

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
