"""
Smoke test - checks that both the model server and the agent API are
reachable and healthy, WITHOUT running an actual generation task (no
project is created, no tokens are generated). Fast sanity check before
you hand the agent real work.

Run this after Start-Model.bat and Start-Agent.bat are both running.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"


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


_ENV = {**_load_env(ENV_EXAMPLE_PATH), **_load_env(ENV_PATH)}
MODEL_PORT = _ENV.get("MODEL_PORT", "8080")
AGENT_PORT = _ENV.get("AGENT_PORT", "8787")

MODEL_HEALTH_URLS = [
    f"http://127.0.0.1:{MODEL_PORT}/health",
    f"http://127.0.0.1:{MODEL_PORT}/v1/models",  # fallback: some builds lack /health
]
AGENT_HEALTH_URL = f"http://127.0.0.1:{AGENT_PORT}/health"


def _check(label: str, urls: list[str], timeout: float = 5.0) -> bool:
    last_error: Exception | None = None
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                body = response.read(500)
                print(f"[OK  ] {label}: {url} -> HTTP {response.status}")
                if body:
                    print(f"         {body[:200]!r}")
                return True
        except urllib.error.URLError as exc:
            last_error = exc
            continue
    print(f"[FAIL] {label}: could not reach any of {urls} ({last_error})")
    return False


def main() -> int:
    print("Portable USB LLM Agent - Smoke Test")
    print("=" * 40)

    model_ok = _check("Model server", MODEL_HEALTH_URLS)
    agent_ok = _check("Agent API", [AGENT_HEALTH_URL])

    print("=" * 40)
    if model_ok and agent_ok:
        print("Both servers are reachable. Ready for a real /agent request.")
        return 0

    print("One or both servers are not reachable.")
    if not model_ok:
        print("  - Is Start-Model.bat running? Check its console window for errors.")
    if not agent_ok:
        print("  - Is Start-Agent.bat running? Check its console window for errors.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
