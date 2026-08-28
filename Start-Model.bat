@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem =====================================================================
rem Portable USB LLM Agent — Start-Model.bat
rem
rem Starts llama-server bound to 127.0.0.1 ONLY. Never edit this to bind
rem to 0.0.0.0 or a LAN-visible address — see SECURITY.md.
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

if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%B"=="" (
            set "%%A=%%B"
        )
    )
)

echo.
echo Portable USB LLM Agent - starting local model server
echo   Model:      %MODEL_PATH%
echo   Context:    %CONTEXT_SIZE%
echo   GPU layers: %GPU_LAYERS%
echo   CPU threads:%CPU_THREADS%
echo   Bind:       127.0.0.1:%MODEL_PORT%  (loopback only)
echo.

if not exist "runtime\windows\llama-server.exe" (
    echo [ERROR] runtime\windows\llama-server.exe was not found.
    echo         See runtime\windows\README.txt for where to get it.
    echo         Any llama.cpp Windows build works - CPU-only, CUDA,
    echo         Vulkan, or another backend - pick whichever matches
    echo         your hardware and set EXTRA_ARGS in .env if that
    echo         build needs a backend-specific flag.
    echo.
    pause
    exit /b 1
)

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

rem ---------------------------------------------------------------------
rem GPU BACKEND NOTE
rem ---------------------------------------------------------------------
rem This script is backend-agnostic — it works with whichever
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
