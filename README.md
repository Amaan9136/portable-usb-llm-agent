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
├── models/                  # place your .gguf model here (not included)
├── runtime/windows/         # place llama-server.exe here (not needed if using an installed llama.exe)
├── agent/
│   ├── app.py               # FastAPI app: /health, /agent, /agent/stream, /projects, /tree, /file, /artifacts
│   ├── config.py            # .env loader, shared by agent + docs
│   ├── tools.py             # sandboxed file/command/zip/project-import tools
│   ├── schemas.py           # Pydantic request/response models
│   └── system_prompt.txt    # sequential-role agent instructions
│   └── requirements.txt
├── ui/                       # cosmic-neon web UI, served by the agent itself
│   ├── index.html
│   ├── app.js                # SSE client, file explorer, chat, project management
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