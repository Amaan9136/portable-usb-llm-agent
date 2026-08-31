"""
Portable USB LLM Agent - command-line client.

Talks to the same running agent server (Start-Agent.bat / the UI launcher)
over HTTP, using the same /agent/stream, /projects, /tree, /file endpoints
as the browser UI. Nothing here bypasses the agent's security model - this
is just another client of the same API.

Examples:
    python cli.py --list-projects
    python cli.py --import "C:\\path\\to\\folder" --name my-app
    python cli.py --task "add input validation" --project my-app
    python cli.py --task "run the test suite" --project my-app --allow-commands
    python cli.py --tree --project my-app
    python cli.py --read myapp/src/main.py --project my-app
    python cli.py --list-models
    python cli.py --model "llama3.2:latest" --backend ollama
    python cli.py --task "add tests" --project my-app --backend ollama --model "gpt-oss:20b-cloud"
    python cli.py --download-zip --project my-app
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_AGENT_URL = "http://127.0.0.1:8787"

# ANSI colors - degrade gracefully if the terminal doesn't support them.
CYAN = "\033[96m"
MAGENTA = "\033[95m"
AMBER = "\033[93m"
DIM = "\033[90m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _use_color() -> bool:
    return sys.stdout.isatty()


def c(text: str, color: str) -> str:
    if not _use_color():
        return text
    return f"{color}{text}{RESET}"


def _request(method: str, url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except json.JSONDecodeError:
            detail = body
        print(c(f"[error] {exc.code}: {detail}", MAGENTA), file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(c(f"[error] could not reach agent server at {url}: {exc}", MAGENTA), file=sys.stderr)
        sys.exit(1)


def cmd_list_models(base_url: str) -> None:
    data = _request("GET", f"{base_url}/models")
    print(c("llama-cpp (portable, always available):", BOLD))
    for m in data.get("llama_cpp", []):
        print(f"  {c(m['name'], CYAN)}")
    ollama = data.get("ollama", {})
    print()
    if not ollama.get("available"):
        print(c(f"ollama: unreachable ({ollama.get('error', 'unknown error')})", DIM))
        return
    print(c(f"ollama (via {ollama.get('source', 'api')}):", BOLD))
    if not ollama.get("models"):
        print(c("  no models found - run `ollama pull <model>` first.", DIM))
        return
    for m in ollama["models"]:
        tag = c("cloud", MAGENTA) if m.get("cloud") else c("local", CYAN)
        size = f"  {m['size_bytes']}" if m.get("size_bytes") else ""
        print(f"  [{tag}] {m['name']}{size}")
    active = data.get("active", {})
    print()
    print(c(f"active: backend={active.get('backend')} model={active.get('model_name')}", DIM))


def cmd_select_model(base_url: str, backend: str, model_name: str | None) -> None:
    payload = {"backend": backend, "model_name": model_name}
    result = _request("POST", f"{base_url}/models/select", payload)
    active = result.get("active", {})
    print(c(f"Now using backend={active.get('backend')} model={active.get('model_name')}", CYAN))


def cmd_download_zip(base_url: str, relative_path: str, out_path: str | None) -> None:
    url = f"{base_url}/explorer/download?relative_path={urllib.parse.quote(relative_path)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
            cd = resp.headers.get("Content-Disposition", "")
            filename = out_path
            if not filename:
                filename = "workspace.zip"
                if "filename=" in cd:
                    filename = cd.split("filename=", 1)[1].strip('"; ')
            with open(filename, "wb") as f:
                f.write(data)
            print(c(f"Downloaded {filename} ({len(data)} bytes).", CYAN))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(c(f"[error] {exc.code}: {body}", MAGENTA), file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(c(f"[error] could not reach agent server: {exc}", MAGENTA), file=sys.stderr)
        sys.exit(1)


def cmd_list_projects(base_url: str) -> None:
    data = _request("GET", f"{base_url}/projects")
    projects = data.get("projects", [])
    if not projects:
        print(c("No projects yet. Import one with --import.", DIM))
        return
    for p in projects:
        status = c("ok", CYAN) if p.get("exists") else c("missing", MAGENTA)
        print(f"  {c(p['name'], BOLD)}  [{status}]  from {p.get('source_path')}")


def cmd_import(base_url: str, source_path: str, name: str | None) -> None:
    result = _request(
        "POST",
        f"{base_url}/projects/import",
        {"source_path": source_path, "project_name": name},
    )
    print(c(f"Imported '{result['project']}' ({result['files_imported']} files).", CYAN))


def cmd_tree(base_url: str, project: str) -> None:
    data = _request("GET", f"{base_url}/tree?relative_path={project}")
    _print_tree(data["tree"], 0)


def _print_tree(node: dict, depth: int) -> None:
    indent = "  " * depth
    if node["type"] == "dir":
        print(f"{indent}{c(node['name'] + '/', CYAN)}")
        for child in node.get("children", []):
            _print_tree(child, depth + 1)
    else:
        size = node.get("size", 0)
        print(f"{indent}{node['name']} {c(f'({size}b)', DIM)}")


def cmd_read(base_url: str, relative_path: str) -> None:
    data = _request("GET", f"{base_url}/file?relative_path={relative_path}")
    print(data["content"])


def cmd_task(
    base_url: str,
    task: str,
    project: str,
    allow_commands: bool,
    allow_overwrite: bool,
    create_zip: bool,
    backend: str | None,
    model_name: str | None,
    verbose_stream: bool | None,
    testing_phase: bool | None,
) -> None:
    full_task = f'Work inside the "{project}" project folder (workspace/{project}). {task}'
    payload = {
        "task": full_task,
        "project_name": project,
        "allow_commands": allow_commands,
        "allow_overwrite": allow_overwrite,
        "create_zip": create_zip,
        "backend": backend,
        "model_name": model_name,
        "verbose_stream": verbose_stream,
        "testing_phase": testing_phase,
    }
    url = f"{base_url}/agent/stream"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    role_labels = {
        "planner": "PLAN",
        "implementer": "IMPL",
        "reviewer": "REVW",
        "tester": "TEST",
        "packager": "PACK",
    }

    try:
        with urllib.request.urlopen(req, timeout=None) as resp:
            event = "message"
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                if line.startswith("event:"):
                    event = line[len("event:"):].strip()
                    continue
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if not data_str:
                    continue
                try:
                    payload_data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                _handle_event(event, payload_data, role_labels)
    except urllib.error.URLError as exc:
        print(c(f"\n[error] connection lost: {exc}", MAGENTA), file=sys.stderr)
        sys.exit(1)


def _handle_event(event: str, payload: dict, role_labels: dict) -> None:
    if event == "start":
        backend = payload.get("backend", "llama-cpp")
        model = payload.get("model", "")
        verbose = payload.get("verbose_stream", True)
        print(c(f"-- agent started (max {payload['turns_allowed']} turns) -- backend={backend} model={model} verbose={verbose}", DIM))
    elif event == "token":
        sys.stdout.write(payload["text"])
        sys.stdout.flush()
    elif event == "tool_call_start":
        label = role_labels.get(payload["role"], payload["role"].upper())
        tool = payload["tool"]
        args_summary = _summarize_args(tool, payload.get("arguments", {}))
        print(f"\n{c('[' + label + ']', AMBER)} {c(tool, CYAN)} {args_summary}")
    elif event == "tool_call_end":
        result = payload.get("result", {})
        ok = result.get("ok")
        mark = c("done", CYAN) if ok else c("failed: " + str(result.get("error", "")), MAGENTA)
        print(f"  -> {mark}")
    elif event == "perf":
        tps = payload.get("tokens_per_second", 0)
        tokens = payload.get("tokens", 0)
        print(c(f"\n  [perf] {tokens} tok in {payload.get('elapsed_seconds', 0)}s  ~{tps} tok/s", DIM))
    elif event == "warning":
        print(c(f"\n[warning] {payload['message']}", AMBER))
    elif event == "error":
        print(c(f"\n[error] {payload['message']}", MAGENTA), file=sys.stderr)
    elif event == "final_answer":
        print()
        print(c("-- final answer --", DIM))
        print(payload.get("text", ""))
        changed = payload.get("changed_files") or []
        if changed:
            print(c("\nchanged files:", DIM))
            for f in changed:
                print(f"  - {f}")
        if payload.get("artifact_filename"):
            print(c(f"\nartifact: {payload['artifact_filename']}", AMBER))


def _summarize_args(tool: str, args: dict) -> str:
    if tool == "write_file":
        return args.get("relative_path", "")
    if tool == "read_file":
        return args.get("relative_path", "")
    if tool == "list_files":
        return args.get("relative_path", ".")
    if tool == "run_command":
        return " ".join(args.get("command", []))
    if tool == "create_zip":
        return args.get("artifact_name", "")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Portable USB LLM Agent - command-line client.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--agent-url", default=DEFAULT_AGENT_URL, help="Agent server URL (default: %(default)s)")
    parser.add_argument("--project", help="Project name (must already be imported)")
    parser.add_argument("--task", help="Task description to run against --project")
    parser.add_argument("--list-projects", action="store_true", help="List imported projects")
    parser.add_argument("--import", dest="import_path", metavar="PATH", help="Import a local folder as a project")
    parser.add_argument("--name", help="Optional project name to use with --import")
    parser.add_argument("--tree", action="store_true", help="Print the file tree of --project")
    parser.add_argument("--read", metavar="RELATIVE_PATH", help="Print the contents of a file in the workspace")
    parser.add_argument("--allow-commands", action="store_true", help="Allow the agent to run python/pytest/npm/node/git")
    parser.add_argument("--allow-overwrite", action="store_true", default=True, help="Allow overwriting existing files (default: on)")
    parser.add_argument("--no-overwrite", dest="allow_overwrite", action="store_false", help="Disallow overwriting existing files")
    parser.add_argument("--zip", dest="create_zip", action="store_true", help="Package the result as a ZIP artifact")
    parser.add_argument("--list-models", action="store_true", help="List models available from llama-cpp and Ollama (local + cloud)")
    parser.add_argument("--model", metavar="NAME", help="Select the active model by name (use with --backend)")
    parser.add_argument("--backend", choices=["llama-cpp", "ollama"], help="Select the active backend, or scope a single --task to it")
    parser.add_argument("--no-verbose", dest="verbose_stream", action="store_false", default=None, help="Hide tool-call/reasoning chatter, stream only tokens and final answer")
    parser.add_argument("--no-testing-phase", dest="testing_phase", action="store_false", default=None, help="Disable the tester role for this task")
    parser.add_argument("--download-zip", action="store_true", help="Download the whole project (or --path within it) as a ZIP")
    parser.add_argument("--path", default=".", help="Relative path within the project to zip with --download-zip (default: whole project)")
    parser.add_argument("--out", help="Output filename for --download-zip (default: workspace.zip or <folder>.zip)")

    args = parser.parse_args()
    base_url = args.agent_url.rstrip("/")

    if args.list_projects:
        cmd_list_projects(base_url)
        return

    if args.list_models:
        cmd_list_models(base_url)
        return

    if args.import_path:
        cmd_import(base_url, args.import_path, args.name)
        return

    if args.read:
        cmd_read(base_url, args.read)
        return

    if args.tree:
        if not args.project:
            parser.error("--tree requires --project")
        cmd_tree(base_url, args.project)
        return

    if args.download_zip:
        if not args.project:
            parser.error("--download-zip requires --project")
        relative_path = args.project if args.path == "." else f"{args.project}/{args.path}"
        cmd_download_zip(base_url, relative_path, args.out)
        return

    if args.model or (args.backend and not args.task):
        if not args.backend:
            parser.error("--model requires --backend")
        cmd_select_model(base_url, args.backend, args.model)
        return

    if args.task:
        if not args.project:
            parser.error("--task requires --project")
        cmd_task(
            base_url, args.task, args.project, args.allow_commands, args.allow_overwrite, args.create_zip,
            args.backend, args.model, args.verbose_stream, args.testing_phase,
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()