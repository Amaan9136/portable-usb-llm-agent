# PortableCoder

A portable, offline, local coding agent for a Windows USB drive. Runs
Qwen2.5-Coder-7B-Instruct (GGUF, Q4_K_M) through llama.cpp's local
OpenAI-compatible server, driven by a small FastAPI agent that writes
files, runs a narrow allowlist of commands, and packages finished
projects into ZIP artifacts — all contained inside a `workspace/`
sandbox on your machine.

**Honest scope statement:** this is a Windows-portable project only,
unless you separately add Linux/macOS `llama-server` binaries to a
corresponding `runtime/<platform>/` folder and adjust the batch scripts
accordingly (not provided here). Performance depends entirely on your
host CPU, RAM, USB drive read speed, and GPU/VRAM — this will not run
"fast on any system," and a 7B model on a 4 GB laptop GPU with partial
CPU offload is genuinely slow compared to cloud-hosted alternatives.
Expect this to be useful for small, well-scoped tasks, not large
codebases or long unattended sessions.

## What's in the box vs. what you provide

| Provided in this ZIP | You download separately |
|---|---|
| Agent source code, tests, docs | Qwen2.5-Coder-7B-Instruct GGUF model (~4.4–4.7 GB) |
| Batch launch scripts | A CUDA- or Vulkan-enabled `llama-server.exe` build |
| Empty `workspace/`, `artifacts/`, `logs/`, `models/` folders | — |

The model and the llama.cpp binary are excluded deliberately — see
`runtime/windows/README.txt` and the model download guide below.

## USB space budget

| Item | Approx. size |
|---|---|
| This project's source, docs, scripts | < 5 MB |
| `.venv` (created on first Start-Agent.bat run) | ~150–300 MB |
| llama-server.exe + supporting DLLs | ~50–300 MB depending on backend |
| Qwen2.5-Coder-7B-Instruct Q4_K_M model | ~4.4–4.7 GB |
| Working headroom for generated projects/artifacts | plan for 1–2 GB+ |

A 32 GB USB drive has comfortable headroom for all of this. A smaller
drive (8–16 GB) would be tight once you account for generated project
churn — clear old `workspace/` and `artifacts/` content periodically.

## Setup — first time

1. **Verify your environment** (after cloning/extracting this project):
   ```
   python scripts\verify_environment.py
   ```
   This checks Python version, disk space, and reports what's missing.
   It will report the model and `llama-server.exe` as missing on a
   fresh checkout — that's expected until you complete steps 2–3.

2. **Get a CUDA- or Vulkan-enabled `llama-server.exe`.** See
   `runtime\windows\README.txt` for exact download instructions and the
   official release URL to use. Place `llama-server.exe` (and any
   supporting DLLs from the same release archive) into
   `runtime\windows\`.

3. **Download the model.** See "Downloading the model" below. Place the
   resulting file at:
   ```
   models\qwen2.5-coder-7b-instruct-q4_k_m.gguf
   ```

4. **Re-run verification:**
   ```
   python scripts\verify_environment.py
   ```
   All checks should pass (nvidia-smi is optional/informational).

5. **Copy the config template** (optional but recommended so you can
   tune values without touching the batch files):
   ```
   copy .env.example .env
   ```
   Edit `.env.example` to match your hardware — see "GPU tuning" below.

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
for interactive API docs, or run the smoke test from a third window:
```
python scripts\smoke_test.py
```

## Downloading the model

See the full walkthrough printed by:
```
python scripts\download_model.py
```
Summary: get **Qwen2.5-Coder-7B-Instruct-GGUF, Q4_K_M quantization**
from the official Qwen repository (verify the publishing organization).
Do not substitute the 14B or 32B variants — they exceed what this
project's turn/timeout budgets and this hardware's VRAM were designed
around. If the file is split into multiple parts, merge them with
`llama-gguf-split --merge` (ships alongside most llama.cpp release
builds) before placing the single resulting file in `models\`.

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

## GPU tuning procedure

Defaults ship conservative (`CONTEXT_SIZE=2048`, `GPU_LAYERS=12`) because
VRAM headroom on a 4 GB card is tight once Windows and driver overhead
are accounted for. To tune for your specific machine:

1. Open a terminal and run:
   ```
   nvidia-smi -l 1
   ```
   This refreshes GPU stats every second — watch the memory-used column.

2. In `.env.example`, increase `GPU_LAYERS` by **2** from its current
   value, restart `Start-Model.bat`, and send a test request (or just
   let it idle after loading — VRAM use is dominated by the loaded
   layers, not active generation).

3. Watch `nvidia-smi -l 1` while the model is loaded and while a request
   is running. **Stop increasing `GPU_LAYERS` once memory use approaches
   ~3.7 GB** — this leaves headroom before you hit a CUDA/Vulkan
   out-of-memory error, since other processes (browser, Windows
   compositor, driver overhead) also claim a slice of your 4 GB budget.

4. If you see a CUDA or Vulkan out-of-memory error at any point, reduce
   `GPU_LAYERS` by at least 2 from the last value you tried, not just 1
   — OOM errors usually mean you're already over budget by more than
   one layer's worth of memory.

5. The project also works with `GPU_LAYERS=0` (fully CPU), assuming
   sufficient system RAM (roughly 6–8 GB free is a reasonable target for
   a 7B Q4_K_M model plus OS/agent overhead). This will be markedly
   slower than partial GPU offload but is a valid fallback if GPU tuning
   proves troublesome.

**CPU_THREADS:** benchmark 4, 6, and 8 on your own machine — there is no
universally correct value. This project ships `CPU_THREADS=6` as a
conservative default for a 4-physical-core CPU (leaves headroom for the
OS and the agent's own Python process), but some users see better
throughput at 8 (all logical threads on a hyperthreaded chip) depending
on background system load. Test it and set whichever you find fastest in
`.env.example`.

## Troubleshooting

**"runtime\windows\llama-server.exe was not found"**
You haven't placed the binary yet, or placed it in the wrong folder.
See `runtime\windows\README.txt`.

**"Model file not found at ..."**
Check the exact filename matches `qwen2.5-coder-7b-instruct-q4_k_m.gguf`
(case doesn't matter on Windows, but the full name must match) and that
it's directly inside `models\`, not a subfolder.

**CUDA/Vulkan out-of-memory error on startup or mid-generation**
Lower `GPU_LAYERS` in `.env.example` by at least 2 from your last attempt.
See "GPU tuning procedure" above.

**Python not found / "py is not recognized"**
Install Python 3.10+ from python.org and ensure "Add to PATH" was
checked during install, or manually add it to your PATH. Restart your
terminal after installing.

**Port conflict (address already in use)**
Something else is already using port 8080 or 8787. Change `MODEL_PORT`
and/or `AGENT_PORT` in `.env.example` to unused ports (both scripts read
the same file, so change it once).

**Everything runs but generation is very slow**
Expected on this hardware profile to some degree. Check: (a) you're
actually getting GPU offload (`GPU_LAYERS` > 0 and no OOM fallback to
CPU), (b) `CONTEXT_SIZE` isn't set unnecessarily high, (c) another
process isn't competing for CPU/GPU, (d) if running from the USB drive
itself rather than copied to local disk, USB read speed affects initial
model load time specifically. Model load-once startup time is separate
from per-token generation speed — a slow *load* doesn't necessarily mean
slow *generation*.

**"missing DLL" error when starting llama-server.exe**
You only copied the executable and not its supporting DLLs from the
release archive. Go back and copy the entire extracted release folder's
contents (or at least all `.dll` files) into `runtime\windows\`.

## Project structure

```
PortableCoder/
├── models/                  # place the .gguf model here (not included)
├── runtime/windows/         # place llama-server.exe here (not included)
├── agent/
│   ├── app.py               # FastAPI app: /health, /agent, /artifacts
│   ├── config.py            # .env.example loader, shared by agent + docs
│   ├── tools.py             # sandboxed file/command/zip tools
│   ├── schemas.py           # Pydantic request/response models
│   ├── system_prompt.txt    # sequential-role agent instructions
│   ├── requirements.txt
│   └── tests/                # pytest suite (path security, API, etc.)
├── workspace/                # agent's sandboxed working directory
├── artifacts/                 # generated ZIP outputs land here
├── logs/                      # structured logs (no prompts/content logged)
├── scripts/
│   ├── download_model.py     # guided model download (no blind auto-fetch)
│   ├── verify_environment.py # pre-flight checks
│   └── smoke_test.py         # health-check both servers, no generation
├── .env.example         # copy to .env.example and edit
├── Start-Model.bat
├── Start-Agent.bat
├── Stop-All.bat
├── SECURITY.md
├── LICENSE
└── README.md                  # this file
```

## Running the test suite

```
cd agent
pip install -r requirements.txt
pytest tests/ -v
```
Tests mock the LLM server entirely (no running `llama-server.exe`
required) so the suite runs fast and fully offline — consistent with
this project's own no-network-during-operation principle.
