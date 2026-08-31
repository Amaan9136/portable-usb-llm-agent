# Running Portable USB LLM Agent

This is the detailed setup and operation guide. See `README.md` for a
short overview and project structure.

## USB space budget

| Item | Approx. size |
|---|---|
| This project's source, docs, scripts | < 5 MB |
| `.venv` (created on first Start-Agent.bat run) | ~150–300 MB |
| llama-server.exe + supporting DLLs (skip if using an already-installed llama.exe) | ~50–300 MB depending on backend |
| Your chosen GGUF model | varies - a few hundred MB to tens of GB depending on model size/quantization |
| Working headroom for generated projects/artifacts | plan for 1–2 GB+ |

Budget your drive size around the model you actually pick - check its
file size on the model's Hugging Face (or other host) page before
downloading. Clear old `workspace/` and `artifacts/` content
periodically on smaller drives.

## Setup - first time

1. **Verify your environment** (after cloning/extracting this project):
   ```
   python scripts\verify_environment.py
   ```
   This checks Python version, disk space, and reports what's missing.
   It will report the model and model server backend as missing on a
   fresh checkout - that's expected until you complete steps 2–4.

2. **Copy the config template** and edit it for your setup:
   ```
   copy .env.example .env
   ```
   Open `.env` and set at minimum `MODEL_PATH` and `LLM_MODEL_NAME` to
   match the model you plan to use. See "Configuration reference" below
   for every key.

3. **Get a model server backend.** Two options - pick whichever applies:
   - **Already have a `llama.exe` build installed** (e.g. one that
     supports `llama.exe serve -m ... -ngl ... -t ...`)? Nothing to
     install. `Start-Model.bat` auto-detects and uses it via
     `LLAMA_EXE` in `.env` (default `llama.exe`, resolved on PATH; set
     a full path if it isn't on PATH). Set `BACKEND=llama-cli` in
     `.env` to force this even if `runtime\windows\llama-server.exe`
     also exists.
   - **Otherwise, get a `llama-server.exe` build matching your
     hardware** (CPU-only, CUDA, Vulkan, or another backend llama.cpp
     publishes Windows builds for). See `runtime\windows\README.txt`
     for exact download instructions and the official release URL to
     use. Place `llama-server.exe` (and any supporting DLLs from the
     same release archive) into `runtime\windows\`.
   `BACKEND=auto` (the default) prefers `llama-server.exe` when present
   and falls back to `LLAMA_EXE` otherwise.

4. **Download a model.** See "Downloading a model" below. Place the
   resulting file at the path you set for `MODEL_PATH` in `.env`.

5. **Re-run verification:**
   ```
   python scripts\verify_environment.py
   ```
   All checks should pass (nvidia-smi is optional/informational, and
   only relevant if you're targeting an NVIDIA GPU).

## First-run commands

From the project root, run:

```
Start-All.bat
```

This single script starts the model server, starts the agent API,
waits for both to be ready, and opens the cosmic neon web UI in your
browser at `http://127.0.0.1:8787/`. It does not call or depend on
`Start-Model.bat` or `Start-Agent.bat` - all of that logic is built
directly into `Start-All.bat` itself.

First run creates a Python virtual environment and installs
dependencies (`agent/requirements.txt`) - this is the one step in
normal operation that needs internet access, and only on first setup.
Subsequent runs reuse the existing `.venv`.

Two console windows will open and stay open ("LLM Model Server" and
"LLM Agent API") - leave them running. Closing the window `Start-All.bat`
itself ran in does **not** stop them; use `Stop-All.bat`, or Ctrl+C in
each of those two windows, to stop everything.

If you'd rather use the raw API directly instead of the UI, once
`Start-All.bat` is running you can still open:
```
http://127.0.0.1:8787/docs
```
OR
```
http://127.0.0.1:8787/redoc
```
(or whatever `AGENT_PORT` you set) for interactive API docs - the UI
and the raw API are the same running server, so nothing extra needs to
be started for this.

### Advanced: starting each piece manually

`Start-Model.bat` and `Start-Agent.bat` still exist if you want to
start the model server and agent separately - for example, to watch
each one's startup output in its own window without the combined
wait/retry logic in `Start-All.bat`, or to run the agent without ever
touching the UI. This is optional; most people never need it.

**Window 1 - model server:**
```
Start-Model.bat
```
Wait for it to print that the server is listening before continuing.
Leave this window open.

**Window 2 - agent API:**
```
Start-Agent.bat
```
This requires `Start-Model.bat` to already be running - `Start-Agent.bat`
does not start the model server itself.

Note that starting things this way still gives you the full UI too
(the agent serves it at `http://127.0.0.1:8787/`) - the only thing
`Start-All.bat` adds on top is the automatic sequencing, readiness
checks, and auto-opening the browser for you.

Do not run `Start-All.bat` at the same time as `Start-Model.bat`/
`Start-Agent.bat` - they would try to bind the same ports twice and
one set will fail to start.

## Using the UI

Once `Start-All.bat` has opened your browser (or you've started things
manually and opened `http://127.0.0.1:8787/` yourself), you can:

- **Open Project** - paste the path to any local folder. It's copied
  into `workspace/<name>/` (the original folder is never modified),
  keeping the agent's sandboxing guarantee intact while still letting
  you work with any project on your machine.
- Browse that project's files in the left-hand explorer. Hover a file
  to reveal a download icon that zips and downloads just that file; the
  zip icon next to the project dropdown downloads the whole project.
- Chat with the agent in the center panel. A short conversational
  message just gets a normal streamed reply - the agent only enters its
  planner/implementer/reviewer/tester/packager pipeline when the task
  actually needs to touch files or run commands. When it does, every
  action streams into the chat live as a collapsible step (file
  written, command run with its output, files listed, zip packaged) -
  click a step to expand its full detail. The right-hand viewer also
  updates in real time whenever a file is written.
- Toggle "Allow commands", "Allow overwrite", and "Package ZIP" the
  same way you would with the `allow_commands` / `allow_overwrite` /
  `create_zip` fields in a raw `/agent` request.
- Open **Settings** (gear icon) to:
  - Point the UI at a different agent server URL.
  - Pick which model backend/model is active - the built-in portable
    GGUF model, or (if you've opted into Ollama - see below) any model
    `ollama list` shows, local or cloud, refreshed live from the
    server.
  - Toggle **verbose event streaming** (show every tool call, command,
    and reasoning step live, vs. just the final answer) and **testing
    phase** (whether the tester role's `run_command` calls happen by
    default) - each toggle has a caption explaining what it does.

### Optional: using Ollama instead of the bundled llama.cpp model

The portable llama.cpp flow above is always the default and needs
nothing extra. If you'd rather use a model already installed via
[Ollama](https://ollama.com) - including Ollama's cloud-hosted
`*-cloud` models - it's an opt-in switch, not a replacement:

1. Install Ollama normally and make sure `ollama list` works in a
   terminal.
2. Either set `MODEL_BACKEND=ollama` and `OLLAMA_MODEL_NAME=<name>` in
   `.env` before launching, **or** leave `.env` alone and pick the
   model later from the Settings modal's model dropdown (or
   `cli.py --model <name> --backend ollama`) - no restart needed.
3. `Start-Model.bat` / `Start-All.bat` detect `BACKEND=ollama` and,
   instead of launching a new model-server process, just confirm the
   Ollama service is reachable (`ollama list`) and print the installed
   models, since Ollama runs its own persistent background service.

Switching backend/model through the UI or CLI takes effect immediately
for new runs - it calls `/models/select` on the running agent, no
restart required. `Stop-All.bat` never stops Ollama itself, since it's
shared background infrastructure this launcher didn't start.

### Command-line client

Everything the UI does is also available from a terminal via `cli.py`,
which talks to the same running agent server - open a separate
terminal (in addition to, not instead of, `Start-All.bat`) and run:

```
python cli.py --list-projects
python cli.py --import "C:\path\to\folder" --name my-app
python cli.py --task "add input validation" --project my-app
python cli.py --task "run the test suite" --project my-app --allow-commands
python cli.py --tree --project my-app
python cli.py --read my-app/src/main.py
python cli.py --list-models
python cli.py --model "llama3.2:latest" --backend ollama
python cli.py --task "add tests" --project my-app --backend ollama --model "gpt-oss:20b-cloud"
python cli.py --download-zip --project my-app
python cli.py --task "quick fix" --project my-app --no-verbose
python cli.py --task "quick fix" --project my-app --no-testing-phase
```

`--list-models` shows both the portable llama.cpp model and, if
reachable, every Ollama model (labeled `local` or `cloud`). `--model`
with `--backend` switches the active server-wide selection the same
way the UI's Settings modal does. `--download-zip` (with `--path` to
scope it to a subfolder, and `--out` for the output filename) zips and
downloads via the same endpoint the UI's download buttons use.
`--no-verbose` hides the live tool-call/command chatter and streams
only tokens plus the final answer; `--no-testing-phase` skips the
tester role for that one run.

On macOS/Linux, or if you already have the model server running and
just want the agent + UI, `start_ui.py` is a cross-platform equivalent
of `Start-All.bat` for that half of the process:

```
python start_ui.py
```

## Downloading a model

This project is not tied to any specific model - any GGUF-format model
works, as long as your chosen backend (`llama-server.exe` or
`llama.exe`) can load it and your hardware can run it. A coding-focused
instruct model is a natural fit for this agent's workflow, but the
choice is yours.

See the full walkthrough printed by:
```
python scripts\download_model.py
```
It prints general guidance for finding and choosing a GGUF model,
resolves the destination path from `MODEL_PATH` in your `.env`, and
reminds you to set `LLM_MODEL_NAME` to match. If the model is split
into multiple parts (filenames ending in `-00001-of-00002.gguf` etc.),
merge them with `llama-gguf-split --merge` (ships alongside most
llama.cpp release builds) before placing the single resulting file at
your configured `MODEL_PATH`.

## Configuration reference

All configuration lives in `.env` (copied from `.env.example`).
`Start-All.bat` (and, if you use them, `Start-Model.bat` /
`Start-Agent.bat`) plus `agent/config.py` all read the same file, so
every process agrees on ports, paths, and model without duplicating
values.

| Key | Read by | Meaning |
|---|---|---|
| `MODEL_PATH` | Start-All.bat, scripts | Path to your `.gguf` file, relative to project root. |
| `CONTEXT_SIZE` | Start-All.bat | Context window size passed to llama-server (`-c`). Only applies to the `llama-server` backend - `llama-cli` doesn't take it in the same form (add via `EXTRA_ARGS` if your build supports it). |
| `GPU_LAYERS` | Start-All.bat | Layers offloaded to GPU (`-ngl`). `0` = CPU-only. Passed to both backends. |
| `CPU_THREADS` | Start-All.bat | CPU threads (`-t`). Passed to both backends. |
| `MODEL_PORT` | Start-All.bat, agent, scripts | Port the model server binds to on `127.0.0.1`. Passed as `--port` to `llama-server`; not passed to `llama-cli` (some `llama.exe serve` builds don't accept it the same way - set it via `EXTRA_ARGS` if yours does and you need a non-default port). |
| `BACKEND` | Start-All.bat, scripts\verify_environment.py | Which server to launch: `auto` (default, prefers `llama-server.exe` if present, else falls back to `LLAMA_EXE`), `llama-server`, or `llama-cli`. |
| `LLAMA_EXE` | Start-All.bat, scripts\verify_environment.py | Path or bare name of the `llama.exe`-style CLI build, used for the `llama-cli` backend. Defaults to `llama.exe` resolved via PATH. |
| `EXTRA_ARGS` | Start-All.bat | Extra flags appended verbatim to whichever backend's command line (backend-specific, e.g. a Vulkan device selector). |
| `AGENT_PORT` | Start-All.bat, agent | Port the FastAPI agent binds to on `127.0.0.1`. |
| `LLM_MODEL_NAME` | agent | Model name string sent in `/v1/chat/completions` requests when using the llama-cpp backend; must match what your chosen backend reports for your loaded model. |
| `TOOL_MODE` | agent | `native` (OpenAI-style tool calls) or `fallback` (single JSON action per turn - more reliable on small/quantized models). |
| `MAX_AGENT_TURNS` | agent | Max turns in the agent's sequential planner→implementer→reviewer→tester→packager loop. |
| `COMMAND_TIMEOUT_SECONDS` | agent | Timeout for any single allowlisted shell command the agent runs. |
| `MODEL_BACKEND` | Start-Model.bat, Start-All.bat, agent | `llama-cpp` (default, the portable flow above) or `ollama` (opt-in). Never changes automatically. |
| `OLLAMA_HOST` | agent, ollama_client.py | Base URL of the Ollama HTTP API. Default `http://127.0.0.1:11434`. |
| `OLLAMA_MODEL_NAME` | agent | Which `ollama list` model name to use by default when `MODEL_BACKEND=ollama`. Can be left blank and chosen later via the UI/CLI model switcher. |
| `OLLAMA_EXE` | Start-Model.bat, Start-All.bat, agent | Bare name or full path of the `ollama` CLI binary, used to verify the service is up and as a fallback if the HTTP API is unreachable. |
| `TESTING_PHASE_DEFAULT` | agent, UI, CLI | Default state of the "testing phase" toggle (tester role runs `run_command`) before any per-request or UI override. |
| `VERBOSE_STREAM_DEFAULT` | agent, UI, CLI | Default state of the "verbose event streaming" toggle (every tool call/command streams live) before any per-request or UI override. |

Environment variables set before launching a script take precedence
over `.env`, which takes precedence over `.env.example`, which takes
precedence over the in-code defaults - so `set AGENT_PORT=9000 &&
Start-All.bat` works without editing any file.

## GPU tuning procedure

`.env.example` ships `GPU_LAYERS=0` (CPU-only) as a safe default that
works everywhere. To offload to a GPU:

1. Open a terminal and run a monitor for your GPU, e.g. on NVIDIA:
   ```
   nvidia-smi -l 1
   ```
   This refreshes GPU stats every second - watch the memory-used column.
   (Use your vendor's equivalent tool for AMD/Intel GPUs.)

2. In `.env`, increase `GPU_LAYERS` by a small increment (e.g. 2–4)
   from its current value, restart `Start-All.bat` (or just `Start-Model.bat`
   if you're running things manually), and send a test
   request (or just let it idle after loading - VRAM use is dominated
   by the loaded layers, not active generation).

3. Watch your GPU monitor while the model is loaded and while a request
   is running. Stop increasing `GPU_LAYERS` once memory use approaches
   your card's limit, leaving headroom for other processes (browser,
   OS compositor, driver overhead) that also claim VRAM.

4. If you see an out-of-memory error at any point, reduce `GPU_LAYERS`
   by more than your last increment - OOM errors usually mean you're
   already over budget by more than one layer's worth of memory.

5. `GPU_LAYERS=0` (fully CPU) always works as a fallback, assuming
   sufficient system RAM for your chosen model and quantization. This
   will be markedly slower than GPU offload but is a valid option if
   GPU tuning proves troublesome.

**CPU_THREADS:** benchmark a few values on your own machine - there is
no universally correct value; it depends on your core count and
background system load. Test it and set whichever you find fastest in
`.env`.

## Example API requests

**Health check:**

curl:
```
curl http://127.0.0.1:8787/health
```
PowerShell:
```
Invoke-RestMethod http://127.0.0.1:8787/health
```

**Run a task** (no commands, no ZIP - safest default):

curl:
```
curl -X POST http://127.0.0.1:8787/agent ^
  -H "Content-Type: application/json" ^
  -d "{\"task\": \"Create a Python CLI calculator in workspace/calculator with add, subtract, multiply, divide.\"}"
```
PowerShell:
```
$body = @{ task = "Create a Python CLI calculator in workspace/calculator with add, subtract, multiply, divide." } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8787/agent -Method Post -Body $body -ContentType "application/json"
```

**Run a task with tests and a ZIP artifact:**

curl:
```
curl -X POST http://127.0.0.1:8787/agent ^
  -H "Content-Type: application/json" ^
  -d "{\"task\": \"Create a Python CLI calculator in workspace/calculator with unit tests.\", \"allow_commands\": true, \"create_zip\": true}"
```
PowerShell:
```
$body = @{
    task = "Create a Python CLI calculator in workspace/calculator with unit tests."
    allow_commands = $true
    create_zip = $true
} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8787/agent -Method Post -Body $body -ContentType "application/json"
```

**List and download artifacts:**

curl:
```
curl http://127.0.0.1:8787/artifacts
curl -O http://127.0.0.1:8787/artifacts/calculator.zip
```
PowerShell:
```
Invoke-RestMethod http://127.0.0.1:8787/artifacts
Invoke-WebRequest http://127.0.0.1:8787/artifacts/calculator.zip -OutFile calculator.zip
```

**List models (portable + optional Ollama, local and cloud):**

curl:
```
curl http://127.0.0.1:8787/models
```
PowerShell:
```
Invoke-RestMethod http://127.0.0.1:8787/models
```

**Switch the active backend/model** (takes effect immediately, no restart):

curl:
```
curl -X POST http://127.0.0.1:8787/models/select ^
  -H "Content-Type: application/json" ^
  -d "{\"backend\": \"ollama\", \"model_name\": \"llama3.2:latest\"}"
```
PowerShell:
```
$body = @{ backend = "ollama"; model_name = "llama3.2:latest" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8787/models/select -Method Post -Body $body -ContentType "application/json"
```

**Download a project (or a single file within it) as a ZIP** - what the
UI's download icons and `cli.py --download-zip` both call:

curl:
```
curl -o calculator.zip "http://127.0.0.1:8787/explorer/download?relative_path=calculator"
curl -o main.py.zip "http://127.0.0.1:8787/explorer/download?relative_path=calculator/main.py"
```
PowerShell:
```
Invoke-WebRequest "http://127.0.0.1:8787/explorer/download?relative_path=calculator" -OutFile calculator.zip
```

Read `SECURITY.md` before setting `allow_commands: true` routinely.

## Troubleshooting

**"runtime\windows\llama-server.exe was not found"**
You haven't placed the binary yet, or placed it in the wrong folder.
See `runtime\windows\README.txt`. If you meant to use an installed
`llama.exe` instead, set `BACKEND=llama-cli` in `.env` (or leave
`BACKEND=auto`, which falls back to it automatically).

**"LLAMA_EXE ... was not found on PATH or as a direct path"**
Set `LLAMA_EXE` in `.env` to the full path of your `llama.exe`, or set
`BACKEND=llama-server` in `.env` to use `runtime\windows\llama-server.exe`
instead. Confirm the binary works standalone with
`<path>\llama.exe serve --help`.

**"Unknown BACKEND value"**
`BACKEND` in `.env` must be `auto`, `llama-server`, `llama-cli`, or
`ollama`.

**"'ollama' was not found on PATH" / "ollama list failed"**
Only relevant if you set `MODEL_BACKEND=ollama` or picked an Ollama
model from the UI/CLI. Install Ollama from
[ollama.com/download](https://ollama.com/download), confirm `ollama
list` works in a plain terminal, and make sure the Ollama background
service is actually running (it normally auto-starts after install;
restart it or run `ollama serve` manually otherwise). If `ollama` is
installed somewhere not on PATH, set `OLLAMA_EXE` in `.env` to its full
path.

**Model dropdown in Settings shows "Ollama unavailable"**
This just means the agent couldn't reach `OLLAMA_HOST`
(`http://127.0.0.1:11434` by default) - the portable llama.cpp model is
unaffected and still selectable. Check the same things as the previous
entry, or that `OLLAMA_HOST` in `.env` matches where Ollama is actually
listening if you've customized it.

**"Model file not found at ..."**
Check that `MODEL_PATH` in `.env` points at the exact file you
downloaded (case doesn't matter on Windows, but the full name must
match) and that the file actually exists at that path.

**Out-of-memory error on startup or mid-generation**
Lower `GPU_LAYERS` in `.env`. See "GPU tuning procedure" above.

**Python not found / "py is not recognized"**
Install Python 3.10+ from python.org and ensure "Add to PATH" was
checked during install, or manually add it to your PATH. Restart your
terminal after installing.

**Port conflict (address already in use)**
Something else is already using your configured `MODEL_PORT` or
`AGENT_PORT`. Change them in `.env` to unused ports (both scripts read
the same file, so change it once).

**Everything runs but generation is very slow**
Expected to some degree depending on your model size/quantization and
hardware. Check: (a) you're actually getting GPU offload (`GPU_LAYERS`
> 0 and no OOM fallback to CPU) if you intended to use one, (b)
`CONTEXT_SIZE` isn't set unnecessarily high, (c) another process isn't
competing for CPU/GPU, (d) if running from the USB drive itself rather
than copied to local disk, USB read speed affects initial model load
time specifically. Model load-once startup time is separate from
per-token generation speed - a slow *load* doesn't necessarily mean
slow *generation*.

**"missing DLL" error when starting llama-server.exe**
You only copied the executable and not its supporting DLLs from the
release archive. Go back and copy the entire extracted release folder's
contents (or at least all `.dll` files) into `runtime\windows\`.

**llama-cli backend starts but the agent can't reach it / wrong port**
Some `llama.exe serve` builds pick their own default port rather than
honoring `MODEL_PORT` the way `llama-server.exe` does. Run
`llama.exe serve --help` to check for a `--port`/`--host` flag; if one
exists, add it via `EXTRA_ARGS` (e.g. `EXTRA_ARGS=--port 8080`) so it
matches `MODEL_PORT` in `.env`, which is what the agent actually
connects to.