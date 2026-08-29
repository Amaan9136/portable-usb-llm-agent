"""
Cross-platform launcher for Portable USB LLM Agent's UI.
Windows users normally use Start-All.bat, which also launches the model
server. This script is for when you already have the model server
running separately (any OS) and just want to bring up the agent API
(which also serves the UI) and open a browser.
Usage:
    python start_ui.py
    python start_ui.py --agent-port 8787 --no-browser
"""
from __future__ import annotations
import argparse
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
ROOT = Path(__file__).resolve().parent
def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent-port", type=int, default=8787)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open a browser tab")
    parser.add_argument("--wait-seconds", type=int, default=30, help="How long to wait for the agent to come up")
    args = parser.parse_args()
    agent_dir = ROOT / "agent"
    if not agent_dir.is_dir():
        print(f"[error] agent/ directory not found at {agent_dir}", file=sys.stderr)
        sys.exit(1)
    if _port_open(args.host, args.agent_port):
        print(f"Agent already running on {args.host}:{args.agent_port} - reusing it.")
    else:
        print(f"Starting agent API on {args.host}:{args.agent_port} ...")
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app", "--host", args.host, "--port", str(args.agent_port)],
            cwd=str(agent_dir),
        )
        for _ in range(args.wait_seconds):
            if _port_open(args.host, args.agent_port):
                break
            time.sleep(1)
        else:
            print(f"[error] agent did not come up within {args.wait_seconds}s. Check its console output.", file=sys.stderr)
            sys.exit(1)
    url = f"http://{args.host}:{args.agent_port}/"
    print(f"UI ready at {url}")
    if not args.no_browser:
        webbrowser.open(url)
if __name__ == "__main__":
    main()
