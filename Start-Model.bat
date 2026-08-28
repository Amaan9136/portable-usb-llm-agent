@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem =====================================================================
rem PortableCoder — Start-Model.bat
rem
rem Starts llama-server bound to 127.0.0.1 ONLY. Never edit this to bind
rem to 0.0.0.0 or a LAN-visible address — see SECURITY.md.
rem
rem Reads overrides from .env.example (KEY=VALUE, one per line, # comments
rem allowed). Falls back to the defaults below if .env.example is absent or
rem a key is missing. Command-line/user env vars set before calling this
rem script take precedence over .env.example (matches agent\config.py).
rem =====================================================================

set "MODEL_PATH=models\qwen2.5-coder-7b-instruct-q4_k_m.gguf"
set "CONTEXT_SIZE=2048"
set "GPU_LAYERS=12"
set "CPU_THREADS=6"
set "MODEL_PORT=8080"

if exist ".env.example" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env.example") do (
        if not "%%A"=="" if not "%%B"=="" (
            set "%%A=%%B"
        )
    )
)

echo.
echo PortableCoder - starting local model server
echo   Model:      %MODEL_PATH%
echo   Context:    %CONTEXT_SIZE%
echo   GPU layers: %GPU_LAYERS%
echo   CPU threads:%CPU_THREADS%
echo   Bind:       127.0.0.1:%MODEL_PORT%  (loopback only)
echo.

if not exist "runtime\windows\llama-server.exe" (
    echo [ERROR] runtime\windows\llama-server.exe was not found.
    echo         See runtime\windows\README.txt for where to get it.
    echo         Note: this project has been tested with both CUDA and
    echo         Vulkan-enabled llama.cpp Windows builds - pick the one
    echo         that matches the backend flag you plan to pass below.
    echo.
    pause
    exit /b 1
)

if not exist "%MODEL_PATH%" (
    echo [ERROR] Model file not found at: %MODEL_PATH%
    echo         Download it separately - see README.md, section
    echo         "Downloading the model", and scripts\download_model.py.
    echo         Expected filename: qwen2.5-coder-7b-instruct-q4_k_m.gguf
    echo.
    pause
    exit /b 1
)

rem ---------------------------------------------------------------------
rem GPU BACKEND NOTE
rem ---------------------------------------------------------------------
rem This project targets CUDA as the primary backend (see README.md).
rem   - CUDA builds:   no extra flag needed; GPU layers use CUDA by default
rem                    once you've placed a CUDA-enabled llama-server.exe
rem                    in runtime\windows\.
rem   - Vulkan builds: documented as a working fallback for this hardware
rem                    profile (RTX 3050 Laptop, 4GB VRAM). Some builds
rem                    auto-select Vulkan; others need a device flag such
rem                    as "-dev Vulkan1" (check
rem                    `llama-server.exe --list-devices` for the correct
rem                    index on your system before assuming Vulkan1).
rem If you need a backend-specific flag, add it to EXTRA_ARGS in
rem .env.example, e.g.:  EXTRA_ARGS=-dev Vulkan1
rem This keeps the batch file itself backend-agnostic — it works with
rem whichever llama-server.exe build you've placed in runtime\windows\.
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
    echo         Common causes: CUDA/Vulkan out-of-memory (lower GPU_LAYERS
    echo         in .env.example by 2 and retry), missing supporting DLLs
    echo         next to llama-server.exe, or a port already in use
    echo         (change MODEL_PORT in .env.example).
    echo         See README.md Troubleshooting section.
    echo.
)

pause
