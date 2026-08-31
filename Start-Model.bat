@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
rem =====================================================================
rem Portable USB LLM Agent - Start-Model.bat
rem
rem Starts a local llama.cpp server bound to 127.0.0.1 ONLY. Never edit
rem this to bind to 0.0.0.0 or a LAN-visible address - see SECURITY.md.
rem
rem Supports three backend styles:
rem   llama-server - the standalone runtime\windows\llama-server.exe
rem                  binary (flags: -m -c -ngl -t --host --port)
rem   llama-cli    - a "llama.exe serve" style build resolved via
rem                  LLAMA_EXE, either on PATH or a full path (flags:
rem                  -m -ngl -t; no -c/--host/--port in the same form,
rem                  so those are only passed through EXTRA_ARGS if your
rem                  build supports them)
rem   ollama       - OPTIONAL, opt-in only. Does not start a new process;
rem                  it just confirms `ollama` is on PATH and the Ollama
rem                  background service is reachable, since Ollama runs
rem                  its own persistent service rather than a script-
rem                  launched process. Set OLLAMA_MODEL_NAME in .env to
rem                  the model shown by `ollama list` you want to use, or
rem                  pick it later from the UI/CLI model switcher.
rem BACKEND in .env picks one, or "auto" (default) to prefer
rem llama-server.exe when present and fall back to LLAMA_EXE otherwise.
rem BACKEND=ollama is never chosen by "auto" - it must be set explicitly,
rem so the plain portable USB flow above is completely unaffected unless
rem you opt in.
rem
rem Reads overrides from .env (KEY=VALUE, one per line, # comments
rem allowed). Falls back to the defaults below if .env is absent or a
rem key is missing. Command-line/user env vars set before calling this
rem script take precedence over .env (matches agent\config.py).
rem =====================================================================
set "MODEL_PATH=models\your-model.gguf"
set "CONTEXT_SIZE=4096"
set "GPU_LAYERS=0"
set "CPU_THREADS=6"
set "MODEL_PORT=8080"
set "BACKEND=auto"
set "LLAMA_EXE=llama.exe"
set "OLLAMA_HOST=http://127.0.0.1:11434"
set "OLLAMA_MODEL_NAME="
set "OLLAMA_EXE=ollama"
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%B"=="" (
            set "_KEY=%%A"
            set "_VAL=%%B"
            for /f "tokens=* delims= " %%K in ("!_KEY!") do set "_KEY=%%K"
            for /f "tokens=* delims= " %%V in ("!_VAL!") do set "_VAL=%%V"
            if "!_VAL:~-1!"==" " (
                for /l %%Z in (1,1,20) do if "!_VAL:~-1!"==" " set "_VAL=!_VAL:~0,-1!"
            )
            set "!_KEY!=!_VAL!"
        )
    )
    set "_KEY="
    set "_VAL="
)
set "BACKEND=%BACKEND: =%"
if /i "%BACKEND%"=="auto" (
    if exist "runtime\windows\llama-server.exe" (
        set "RESOLVED_BACKEND=llama-server"
    ) else (
        set "RESOLVED_BACKEND=llama-cli"
    )
) else if /i "%BACKEND%"=="llama-server" (
    set "RESOLVED_BACKEND=llama-server"
) else if /i "%BACKEND%"=="llama-cli" (
    set "RESOLVED_BACKEND=llama-cli"
) else if /i "%BACKEND%"=="ollama" (
    set "RESOLVED_BACKEND=ollama"
) else (
    echo [ERROR] Unknown BACKEND value "%BACKEND%" in .env - expected auto, llama-server, llama-cli, or ollama.
    echo         Fix the BACKEND= line in .env ^(check for trailing spaces or an
    echo         inline comment on that line - only "auto", "llama-server",
    echo         "llama-cli", or "ollama" are valid, nothing else on the line^).
    echo.
    pause
    exit /b 1
)
echo.
echo Portable USB LLM Agent - starting local model server
echo   Backend:    %RESOLVED_BACKEND% (BACKEND=%BACKEND%)
if /i "%RESOLVED_BACKEND%"=="ollama" goto show_ollama_banner
echo   Model:      %MODEL_PATH%
echo   GPU layers: %GPU_LAYERS%
echo   CPU threads:%CPU_THREADS%
echo   Bind:       127.0.0.1:%MODEL_PORT%  (loopback only)
goto after_banner
:show_ollama_banner
echo   Ollama host: %OLLAMA_HOST%
echo   Model:       %OLLAMA_MODEL_NAME% (blank = choose later in UI/CLI)
:after_banner
echo.
if /i "%RESOLVED_BACKEND%"=="ollama" goto run_ollama
if not exist "%MODEL_PATH%" (
    echo [ERROR] Model file not found at: %MODEL_PATH%
    echo         Download it separately - see RUN.md, section
    echo         "Downloading a model", and scripts\download_model.py.
    echo         Set MODEL_PATH in .env to match whatever .gguf file
    echo         and location you actually use.
    echo.
    pause
    exit /b 1
)
if /i "%RESOLVED_BACKEND%"=="llama-server" goto run_llama_server
if /i "%RESOLVED_BACKEND%"=="llama-cli" goto run_llama_cli
echo [ERROR] Internal error resolving backend "%RESOLVED_BACKEND%".
echo         This should not happen - please report this as a bug.
echo.
pause
exit /b 1
:run_ollama
where %OLLAMA_EXE% >nul 2>nul
if errorlevel 1 (
    echo [ERROR] "%OLLAMA_EXE%" was not found on PATH.
    echo         Install Ollama from https://ollama.com/download, or set
    echo         OLLAMA_EXE in .env to its full path.
    echo.
    pause
    exit /b 1
)
echo Checking Ollama is reachable at %OLLAMA_HOST% ...
%OLLAMA_EXE% list >nul 2>nul
if errorlevel 1 (
    echo [ERROR] "%OLLAMA_EXE% list" failed - is the Ollama background
    echo         service running? On Windows it normally starts
    echo         automatically after installation; try restarting it, or
    echo         run "ollama serve" manually in another window and retry.
    echo.
    pause
    exit /b 1
)
echo Ollama is reachable. Installed models ^(local and cloud^):
echo.
%OLLAMA_EXE% list
echo.
echo Ollama runs its own persistent background service, so there is
echo nothing further for this script to launch - it just verified the
echo service is up. Set MODEL_BACKEND=ollama and OLLAMA_MODEL_NAME=^<name
echo from the list above^> in .env, or pick the model later from the
echo UI/CLI model switcher, then run Start-Agent.bat or Start-All.bat.
echo.
pause
exit /b 0
:run_llama_server
if not exist "runtime\windows\llama-server.exe" (
    echo [ERROR] runtime\windows\llama-server.exe was not found.
    echo         See runtime\windows\README.txt for where to get it, or
    echo         set BACKEND=llama-cli in .env to use LLAMA_EXE instead.
    echo         Any llama.cpp Windows build works - CPU-only, CUDA,
    echo         Vulkan, or another backend - pick whichever matches
    echo         your hardware and set EXTRA_ARGS in .env if that
    echo         build needs a backend-specific flag.
    echo.
    pause
    exit /b 1
)
rem ---------------------------------------------------------------------
rem GPU BACKEND NOTE
rem ---------------------------------------------------------------------
rem This script is backend-agnostic - it works with whichever
rem llama-server.exe build you've placed in runtime\windows\ (CPU-only,
rem CUDA, Vulkan, ROCm, etc.). GPU_LAYERS=0 in .env means CPU-only.
rem If your build needs a backend-specific flag (e.g. a Vulkan device
rem index), add it to EXTRA_ARGS in .env, for example:
rem   EXTRA_ARGS=-dev Vulkan1
rem Check `llama-server.exe --list-devices` to find the right index/name
rem for your system before assuming any particular value is correct.
rem ---------------------------------------------------------------------
runtime\windows\llama-server.exe ^
  -m "%MODEL_PATH%" ^
  -c %CONTEXT_SIZE% ^
  -ngl %GPU_LAYERS% ^
  -t %CPU_THREADS% ^
  --jinja ^
  --host 127.0.0.1 ^
  --port %MODEL_PORT% ^
  %EXTRA_ARGS%
if errorlevel 1 (
    echo.
    echo [ERROR] llama-server.exe exited with an error.
    echo         Common causes: GPU out-of-memory (lower GPU_LAYERS
    echo         in .env by 2 and retry), missing supporting DLLs next
    echo         to llama-server.exe, or a port already in use (change
    echo         MODEL_PORT in .env).
    echo         See RUN.md Troubleshooting section.
    echo.
)
pause
exit /b 0
:run_llama_cli
where %LLAMA_EXE% >nul 2>nul
if errorlevel 1 (
    if exist "%LLAMA_EXE%" (
        goto :llama_cli_found
    )
    echo [ERROR] "%LLAMA_EXE%" was not found on PATH or as a direct path.
    echo         Set LLAMA_EXE in .env to the full path of your llama.exe,
    echo         e.g. LLAMA_EXE=C:\Users\you\AppData\Local\Microsoft\WindowsApps\llama.exe
    echo         or set BACKEND=llama-server in .env to use
    echo         runtime\windows\llama-server.exe instead.
    echo.
    pause
    exit /b 1
)
:llama_cli_found
rem ---------------------------------------------------------------------
rem GPU BACKEND NOTE
rem ---------------------------------------------------------------------
rem GPU_LAYERS=0 means CPU-only. If your llama.exe build needs a
rem backend-specific device flag (e.g. Vulkan device index), add it to
rem EXTRA_ARGS in .env:
rem   EXTRA_ARGS=-dev Vulkan1
rem CONTEXT_SIZE, --host, and --port are NOT passed here - the "serve"
rem subcommand on many llama.exe builds does not accept -c/--host/--port
rem in the same form as llama-server.exe. If your build does support
rem them, add them via EXTRA_ARGS, e.g. EXTRA_ARGS=-c 4096 --port %MODEL_PORT%
rem Run `%LLAMA_EXE% serve --help` to confirm which flags your build
rem actually supports before assuming any particular value is correct.
rem ---------------------------------------------------------------------
"%LLAMA_EXE%" serve ^
  -m "%MODEL_PATH%" ^
  -ngl %GPU_LAYERS% ^
  -t %CPU_THREADS% ^
  %EXTRA_ARGS%
if errorlevel 1 (
    echo.
    echo [ERROR] %LLAMA_EXE% exited with an error.
    echo         Common causes: GPU out-of-memory (lower GPU_LAYERS
    echo         in .env by 2 and retry), a flag this build doesn't
    echo         support (check with "%LLAMA_EXE% serve --help"), or a
    echo         port already in use (change MODEL_PORT in .env - note:
    echo         confirm with --help whether this build even accepts a
    echo         --port/--host flag; some serve subcommands pick these
    echo         automatically).
    echo         See RUN.md Troubleshooting section.
    echo.
)
pause
exit /b 0