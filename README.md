# Portable USB LLM Agent

A portable, offline, local coding agent for a Windows USB drive. Runs
any GGUF model of your choice through llama.cpp's local
OpenAI-compatible server, driven by a small FastAPI agent that writes
files, runs a narrow allowlist of commands, and packages finished
projects into ZIP artifacts - all contained inside a `workspace/`
sandbox on your machine. An **optional, opt-in** backend also lets the
agent use a locally running [Ollama](https://ollama.com) install
instead - any model `ollama list` shows, local or one of Ollama's
"-cloud" models - selectable from the UI's Settings modal or the CLI,
without touching the default portable flow.

**Honest scope statement:** this is a Windows-portable project only,
unless you separately add Linux/macOS `llama-server` binaries to a
corresponding `runtime/<platform>/` folder and adjust the batch scripts
accordingly (not provided here). Performance depends entirely on your
host CPU, RAM, USB drive read speed, GPU/VRAM, and which model/quant
you choose - this will not run "fast on any system." Expect this to be
useful for small, well-scoped tasks, not large codebases or long
unattended sessions.

Every model, backend, and tuning value (model path, ports, context
size, GPU layers, thread count, backend flags) is configured through a
single `.env` file - nothing is hardcoded to a specific model. See
`.env.example` for the full list of keys.

## What it can do

- **Sequential-role agent pipeline** - every task is worked through five
  labeled roles shown live in the UI header (Planner → Implementer →
  Reviewer → Tester → Packager), so you can see which phase the model is
  in rather than staring at a single opaque "thinking" spinner.
- **Sandboxed file operations** - list, read, and write files inside the
  imported project's `workspace/` sandbox only; the tool layer rejects
  absolute paths, drive letters, and reserved names so the agent can't
  reach outside the sandbox.
- **Project import** - paste any local folder path in "Open a project"
  and it's copied into the sandboxed workspace under its own project
  name; the original folder on disk is never modified.
- **Optional command execution** - with "Allow commands" checked, the
  agent can run a narrow allowlisted set of shell commands (e.g. `python
  file.py`) inside the sandbox to actually test the code it writes,
  surfacing exit codes and stdout/stderr in the timeline.
- **Overwrite protection** - "Allow overwrite" gates whether the agent
  can replace existing files; off by default so re-running a task on the
  same project won't clobber your work without asking.
- **ZIP artifact packaging** - "Package ZIP" bundles the finished
  project into a downloadable artifact via the Packager role, landing in
  `artifacts/`.
- **Live streamed action timeline** - every run shows each tool call as
  it happens (`Listed`, `Wrote`, `Ran`, ...) with expandable file
  contents/diffs, a token/speed/duration footer, and a "changed files"
  strip you can open directly in the right-hand Viewer pane.
- **Two interchangeable model backends** - the default **Portable
  (llama.cpp)** backend runs a local GGUF model with no install and no
  network calls, or you can opt into a locally running **Ollama**
  install instead, picking any locally-pulled model or one of Ollama's
  `-cloud` models from the same Settings dropdown, without touching the
  portable flow.
- **File explorer + viewer** - the left Explorer pane mirrors the live
  project tree as the agent creates/edits files; the right Viewer pane
  shows the currently selected file's contents, auto-updating as the
  agent works.
- **CLI client** - `cli.py` talks to the same agent API as the web UI,
  for scripting or terminal-only use.
- **Cross-platform launcher** - `start_ui.py` runs the agent + UI (not
  the portable llama.cpp server) on any OS, useful if you're driving the
  agent against an Ollama backend on macOS/Linux.
- **Truthfulness guardrails** - responses are checked against what tool
  calls actually happened; the agent won't claim a file was written or a
  test passed if the corresponding tool call didn't actually run or
  succeed (see the "No tests were run..." / "No artifact created..."
  messaging pattern in the screenshots below).

## Screenshots

<table>
<tr>
<td width="50%">

**Chat-driven task execution**
Describe a task in plain English; the agent runs it as a sequence of
tool calls (list → write → write) and reports exactly which files were
actually changed, refusing to claim more than the tool results support.
<br><br>
<img src="screenshots/01-chat-run-task.png" alt="Running a task from the chat box, showing the live action timeline and changed-files summary">

</td>
<td width="50%">

**Importing a project**
"Open a project" copies a local folder path into the sandboxed
workspace under a project name of your choice - the source folder on
disk is never touched.
<br><br>
<img src="screenshots/02-open-project.png" alt="Open a project modal for importing a local folder path into the sandbox">

</td>
</tr>
<tr>
<td width="50%">

**Model selection**
The Settings modal lists the built-in Portable (llama.cpp) backend
alongside every Ollama model the local install reports - local and
`-cloud` models side by side, switchable without leaving the app.
<br><br>
<img src="screenshots/03-model-settings.png" alt="Settings modal showing Portable llama.cpp and Ollama local/cloud model options">

</td>
<td width="50%">

**Runs entirely on your hardware**
Since inference happens through a local llama.cpp/Ollama server, GPU
and memory usage stay on your machine - no data leaves your device
unless you deliberately pick an Ollama `-cloud` model.
<br><br>
<img src="screenshots/04-gpu-task-manager.png" alt="Windows Task Manager showing local GPU and memory usage while the agent runs">

</td>
</tr>
<tr>
<td width="50%">

**Multi-file, multi-step generation**
A single instruction ("Build a calculator, remove the sum.py") can
fan out into several tool calls in one run - here writing
`calculator.py`, `__init__.py`, and a `README.md` together, each shown
with its full generated content.
<br><br>
<img src="screenshots/05-multi-file-pipeline.png" alt="A single task producing calculator.py, __init__.py, and README.md in one run">

</td>
<td width="50%">

**Command execution and honest failure reporting**
With "Allow commands" on, the agent can run allowlisted shell commands
inside the sandbox to act on its own output - and when a command fails
(here, a script referencing a file that doesn't exist), the agent
reports the real exit code and error instead of pretending it worked.
<br><br>
<img src="screenshots/06-command-execution.png" alt="A failed command execution with exit code 2, correctly reported instead of hidden">

</td>
</tr>
</table>

## What's in the box vs. what you provide

| Provided in this ZIP | You download separately |
|---|---|
| Agent source code, docs | A GGUF model of your choice |
| Batch launch scripts | Either a `llama-server.exe` build matching your backend (CPU/CUDA/Vulkan/etc.), or an already-installed `llama.exe` (with a `serve` subcommand) - either works |
| Cosmic-neon web UI + CLI client | - |
| Empty `workspace/`, `artifacts/`, `logs/`, `models/` folders | - |

The model and the llama.cpp binary are excluded deliberately - see
`runtime/windows/README.txt` and `RUN.md`.

## Quick start

1. Copy `.env.example` to `.env` and set `MODEL_PATH` / `LLM_MODEL_NAME` (and any GPU/backend settings) for your setup.
2. Get a server backend: place a `llama-server.exe` build in `runtime\windows\`, **or** point `LLAMA_EXE` in `.env` at an already-installed `llama.exe` (defaults to resolving `llama.exe` on PATH). `BACKEND=auto` in `.env` picks whichever is available. Also place your `.gguf` model at the path from `MODEL_PATH`.
3. Run **`Start-All.bat`**. That's it - it starts the model server, starts the agent, waits for both to be ready, and opens the web UI in your browser automatically.

`Start-All.bat` is the only script you need for normal use; it does not
call or depend on any other script. `Start-Model.bat` / `Start-Agent.bat`
still exist for advanced manual use (e.g. running the agent without the
UI, or starting each piece in its own separately-timed window) but
running them is optional, not a prerequisite - see "Advanced: manual
start" in `RUN.md` if you want that instead.

Full setup, configuration reference, GPU tuning, API examples, UI/CLI
usage, and troubleshooting live in **[RUN.md](RUN.md)** - read that
before your first run.

## Project structure

```
Portable USB LLM Agent/
├── screenshots/              # UI screenshots referenced in this README
├── models/                  # place your .gguf model here (not included)
├── runtime/windows/         # place llama-server.exe here (not needed if using an installed llama.exe)
├── agent/
│   ├── app.py               # FastAPI app: /health, /agent, /agent/stream, /models, /models/select, /projects, /tree, /file, /explorer/download, /artifacts
│   ├── config.py            # .env loader, shared by agent + docs
│   ├── tools.py             # sandboxed file/command/zip/project-import tools
│   ├── schemas.py           # Pydantic request/response models
│   ├── ollama_client.py     # optional Ollama model discovery (HTTP API, CLI fallback)
│   └── system_prompt.txt    # sequential-role agent instructions
│   └── requirements.txt
├── ui/                       # cosmic-neon web UI, served by the agent itself
│   ├── index.html
│   ├── js/                    # ES modules: state, api, streaming, chat, explorer, models, settings...
│   ├── styles/app.css           # component styles (action timeline, modals, toggles)
│   ├── fontawesome/              # Font Awesome Free, local - no CDN
│   ├── tailwind.css             # compiled Tailwind CSS v4 (no CDN, no build step needed to run)
│   └── fonts/                 # self-hosted Space Grotesk / Inter / JetBrains Mono
├── cli.py                     # terminal client for the same agent API the UI uses
├── start_ui.py                 # cross-platform launcher (agent + UI only, any OS)
├── workspace/                # agent's sandboxed working directory (imported projects land here)
├── artifacts/                 # generated ZIP outputs land here
├── logs/                      # structured logs (no prompts/content logged)
├── scripts/
│   ├── download_model.py     # guided model download (no blind auto-fetch)
│   └── verify_environment.py # pre-flight checks
├── .env.example         # copy to .env and edit
├── Start-All.bat                # the only script you need - starts model + agent + opens the UI
├── Start-Model.bat              # advanced/manual: starts only the model server
├── Start-Agent.bat              # advanced/manual: starts only the agent (requires Start-Model.bat already running)
├── Stop-All.bat
├── SECURITY.md
├── RUN.md                      # detailed setup, tuning, API, UI/CLI usage, troubleshooting
├── LICENSE
└── README.md                  # this file
```

See `SECURITY.md` before setting `allow_commands: true` routinely.