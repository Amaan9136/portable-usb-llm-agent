# Portable USB LLM Agent

A portable, offline, local coding agent for a Windows USB drive. Runs
any GGUF model of your choice through llama.cpp's local
OpenAI-compatible server, driven by a small FastAPI agent that writes
files, runs a narrow allowlist of commands, and packages finished
projects into ZIP artifacts - all contained inside a `workspace/`
sandbox on your machine.

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

## What's in the box vs. what you provide

| Provided in this ZIP | You download separately |
|---|---|
| Agent source code, tests, docs | A GGUF model of your choice |
| Batch launch scripts | Either a `llama-server.exe` build matching your backend (CPU/CUDA/Vulkan/etc.), or an already-installed `llama.exe` (with a `serve` subcommand) - either works |
| Empty `workspace/`, `artifacts/`, `logs/`, `models/` folders | - |

The model and the llama.cpp binary are excluded deliberately - see
`runtime/windows/README.txt` and `RUN.md`.

## Quick start

1. Copy `.env.example` to `.env` and set `MODEL_PATH` / `LLM_MODEL_NAME` (and any GPU/backend settings) for your setup.
2. Get a server backend: place a `llama-server.exe` build in `runtime\windows\`, **or** point `LLAMA_EXE` in `.env` at an already-installed `llama.exe` (defaults to resolving `llama.exe` on PATH). `BACKEND=auto` in `.env` picks whichever is available. Also place your `.gguf` model at the path from `MODEL_PATH`.
3. Run `Start-Model.bat`, then `Start-Agent.bat` in a second window.
4. Open `http://127.0.0.1:8787/docs` or run `python scripts\smoke_test.py`.

Full setup, configuration reference, GPU tuning, API examples, and
troubleshooting live in **[RUN.md](RUN.md)** - read that before your
first run.

## Project structure

```
Portable USB LLM Agent/
├── models/                  # place your .gguf model here (not included)
├── runtime/windows/         # place llama-server.exe here (not needed if using an installed llama.exe)
├── agent/
│   ├── app.py               # FastAPI app: /health, /agent, /artifacts
│   ├── config.py            # .env loader, shared by agent + docs
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
├── .env.example         # copy to .env and edit
├── Start-Model.bat
├── Start-Agent.bat
├── Stop-All.bat
├── SECURITY.md
├── RUN.md                      # detailed setup, tuning, API, troubleshooting
├── LICENSE
└── README.md                  # this file
```

See `SECURITY.md` before setting `allow_commands: true` routinely.