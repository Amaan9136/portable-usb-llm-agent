# Running Portable USB LLM Agent

This is the detailed setup and operation guide. See `README.md` for a
short overview and project structure.

## USB space budget

| Item | Approx. size |
|---|---|
| This project's source, docs, scripts | < 5 MB |
| `.venv` (created on first Start-Agent.bat run) | ~150–300 MB |
| llama-server.exe + supporting DLLs | ~50–300 MB depending on backend |
| Your chosen GGUF model | varies — a few hundred MB to tens of GB depending on model size/quantization |
| Working headroom for generated projects/artifacts | plan for 1–2 GB+ |

Budget your drive size around the model you actually pick — check its
file size on the model's Hugging Face (or other host) page before
downloading. Clear old `workspace/` and `artifacts/` content
periodically on smaller drives.

## Setup — first time

1. **Verify your environment** (after cloning/extracting this project):
   ```
   python scripts\verify_environment.py
   ```
   This checks Python version, disk space, and reports what's missing.
   It will report the model and `llama-server.exe` as missing on a
   fresh checkout — that's expected until you complete steps 2–4.

2. **Copy the config template** and edit it for your setup:
   ```
   copy .env.example .env
   ```
   Open `.env` and set at minimum `MODEL_PATH` and `LLM_MODEL_NAME` to
   match the model you plan to use. See "Configuration reference" below
   for every key.

3. **Get a `llama-server.exe` build matching your backend** (CPU-only,
   CUDA, Vulkan, or another backend llama.cpp publishes Windows builds
   for). See `runtime\windows\README.txt` for exact download
   instructions and the official release URL to use. Place
   `llama-server.exe` (and any supporting DLLs from the same release
   archive) into `runtime\windows\`.

4. **Download a model.** See "Downloading a model" below. Place the
   resulting file at the path you set for `MODEL_PATH` in `.env`.

5. **Re-run verification:**
   ```
   python scripts\verify_environment.py
   ```
   All checks should pass (nvidia-smi is optional/informational, and
   only relevant if you're targeting an NVIDIA GPU).

## First-run commands

Open two terminal/console windows in the project root:

**Window 1 — model server:**
```
Start-Model.bat
```
Wait for it to print that the server is listening before continuing.
Leave this window open.

**Window 2 — agent API:**
```
Start-Agent.bat
```
First run creates a Python virtual environment and installs
dependencies (`agent/requirements.txt`) — this is the one step in
normal operation that needs internet access, and only on first setup.
Subsequent runs reuse the existing `.venv`.

Once both are running, open:
```
http://127.0.0.1:8787/docs
```
(or whatever `AGENT_PORT` you set) for interactive API docs, or run the
smoke test from a third window:
```
python scripts\smoke_test.py
```

To stop both servers, close their console windows or run `Stop-All.bat`.

## Downloading a model

This project is not tied to any specific model — any GGUF-format model
works, as long as `llama-server.exe` can load it and your hardware can
run it. A coding-focused instruct model is a natural fit for this
agent's workflow, but the choice is yours.

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
`Start-Model.bat`, `Start-Agent.bat`, and `agent/config.py` all read the
same file, so every process agrees on ports, paths, and model without
duplicating values.

| Key | Read by | Meaning |
|---|---|---|
| `MODEL_PATH` | Start-Model.bat, scripts | Path to your `.gguf` file, relative to project root. |
| `CONTEXT_SIZE` | Start-Model.bat | Context window size passed to llama-server (`-c`). |
| `GPU_LAYERS` | Start-Model.bat | Layers offloaded to GPU (`-ngl`). `0` = CPU-only. |
| `CPU_THREADS` | Start-Model.bat | CPU threads passed to llama-server (`-t`). |
| `MODEL_PORT` | Start-Model.bat, agent, scripts | Port llama-server binds to on `127.0.0.1`. |
| `EXTRA_ARGS` | Start-Model.bat | Extra flags appended verbatim to the llama-server command line (backend-specific, e.g. a Vulkan device selector). |
| `AGENT_PORT` | Start-Agent.bat, agent | Port the FastAPI agent binds to on `127.0.0.1`. |
| `LLM_MODEL_NAME` | agent | Model name string sent in `/v1/chat/completions` requests; must match what llama-server reports for your loaded model. |
| `TOOL_MODE` | agent | `native` (OpenAI-style tool calls) or `fallback` (single JSON action per turn — more reliable on small/quantized models). |
| `MAX_AGENT_TURNS` | agent | Max turns in the agent's sequential planner→implementer→reviewer→tester→packager loop. |
| `COMMAND_TIMEOUT_SECONDS` | agent | Timeout for any single allowlisted shell command the agent runs. |

Environment variables set before launching a script take precedence
over `.env`, which takes precedence over `.env.example`, which takes
precedence over the in-code defaults — so `set AGENT_PORT=9000 &&
Start-Agent.bat` works without editing any file.

## GPU tuning procedure

`.env.example` ships `GPU_LAYERS=0` (CPU-only) as a safe default that
works everywhere. To offload to a GPU:

1. Open a terminal and run a monitor for your GPU, e.g. on NVIDIA:
   ```
   nvidia-smi -l 1
   ```
   This refreshes GPU stats every second — watch the memory-used column.
   (Use your vendor's equivalent tool for AMD/Intel GPUs.)

2. In `.env`, increase `GPU_LAYERS` by a small increment (e.g. 2–4)
   from its current value, restart `Start-Model.bat`, and send a test
   request (or just let it idle after loading — VRAM use is dominated
   by the loaded layers, not active generation).

3. Watch your GPU monitor while the model is loaded and while a request
   is running. Stop increasing `GPU_LAYERS` once memory use approaches
   your card's limit, leaving headroom for other processes (browser,
   OS compositor, driver overhead) that also claim VRAM.

4. If you see an out-of-memory error at any point, reduce `GPU_LAYERS`
   by more than your last increment — OOM errors usually mean you're
   already over budget by more than one layer's worth of memory.

5. `GPU_LAYERS=0` (fully CPU) always works as a fallback, assuming
   sufficient system RAM for your chosen model and quantization. This
   will be markedly slower than GPU offload but is a valid option if
   GPU tuning proves troublesome.

**CPU_THREADS:** benchmark a few values on your own machine — there is
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

**Run a task** (no commands, no ZIP — safest default):

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

Read `SECURITY.md` before setting `allow_commands: true` routinely.

## Running the test suite

```
cd agent
pip install -r requirements.txt
pytest tests/ -v
```
Tests mock the LLM server entirely (no running `llama-server.exe`
required) so the suite runs fast and fully offline — consistent with
this project's own no-network-during-operation principle.

## Troubleshooting

**"runtime\windows\llama-server.exe was not found"**
You haven't placed the binary yet, or placed it in the wrong folder.
See `runtime\windows\README.txt`.

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
per-token generation speed — a slow *load* doesn't necessarily mean
slow *generation*.

**"missing DLL" error when starting llama-server.exe**
You only copied the executable and not its supporting DLLs from the
release archive. Go back and copy the entire extracted release folder's
contents (or at least all `.dll` files) into `runtime\windows\`.
