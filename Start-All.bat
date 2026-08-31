@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0."
rem =====================================================================
rem Portable USB LLM Agent - Start-All.bat
rem
rem This is the ONLY script you need to run. It starts the local model
rem server, starts the agent API, waits for both to come up, and opens
rem the cosmic UI in your browser. Start-Model.bat and Start-Agent.bat
rem are not used by this script and are not required.
rem
rem Everything below is folded in from what used to be two separate
rem scripts, so this file can be run entirely on its own.
rem =====================================================================
rem --------------------------- shared config ---------------------------
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
set "AGENT_PORT=8787"
if not exist ".env" goto :after_env
for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do call :apply_env_line "%%A" "%%B"
goto :after_env
:apply_env_line
set "_KEY=%~1"
set "_VAL=%~2"
if "%_KEY%"=="" goto :eof
if "%_VAL%"=="" goto :eof
for /f "tokens=* delims= " %%K in ("%_KEY%") do set "_KEY=%%K"
for /f "tokens=* delims= " %%V in ("%_VAL%") do set "_VAL=%%V"
:trim_trailing_space
if "%_VAL:~-1%"==" " (
    set "_VAL=%_VAL:~0,-1%"
    goto :trim_trailing_space
)
set "%_KEY%=%_VAL%"
goto :eof
:after_env
set "BACKEND=%BACKEND: =%"
echo.
echo =======================================================================
echo  Portable USB LLM Agent - starting model server + agent API + UI
echo =======================================================================
echo   Model port: %MODEL_PORT%
echo   Agent port: %AGENT_PORT%
echo.
rem --------------------- step 1: launch model server --------------------
if /i not "%BACKEND%"=="auto" goto :backend_not_auto
if exist "runtime\windows\llama-server.exe" (
    set "RESOLVED_BACKEND=llama-server"
) else (
    set "RESOLVED_BACKEND=llama-cli"
)
goto :backend_resolved
:backend_not_auto
if /i "%BACKEND%"=="llama-server" (
    set "RESOLVED_BACKEND=llama-server"
    goto :backend_resolved
)
if /i "%BACKEND%"=="llama-cli" (
    set "RESOLVED_BACKEND=llama-cli"
    goto :backend_resolved
)
if /i "%BACKEND%"=="ollama" (
    set "RESOLVED_BACKEND=ollama"
    goto :backend_resolved
)
echo [ERROR] Unknown BACKEND value "%BACKEND%" in .env - expected auto, llama-server, llama-cli, or ollama.
echo         Fix the BACKEND= line in .env - check for trailing spaces or an
echo         inline comment on that line - only auto, llama-server,
echo         llama-cli, or ollama are valid, nothing else on the line.
echo.
pause
exit /b 1
:backend_resolved
if /i "%RESOLVED_BACKEND%"=="ollama" goto :launch_ollama
if not exist "%MODEL_PATH%" (
    echo [ERROR] Model file not found at: %MODEL_PATH%
    echo         Download it separately - see RUN.md, section
    echo         Downloading a model, and scripts\download_model.py.
    echo         Set MODEL_PATH in .env to match whatever .gguf file
    echo         and location you actually use.
    echo.
    pause
    exit /b 1
)
if /i not "%RESOLVED_BACKEND%"=="llama-server" goto :launch_llama_cli
if not exist "runtime\windows\llama-server.exe" (
    echo [ERROR] runtime\windows\llama-server.exe was not found.
    echo         See runtime\windows\README.txt for where to get it, or
    echo         set BACKEND=llama-cli in .env to use LLAMA_EXE instead.
    echo.
    pause
    exit /b 1
)
echo Launching model server (llama-server) in a new window...
> "%TEMP%\_pua_start_model.bat" (
    echo @echo off
    echo cd /d "%~dp0."
    echo runtime\windows\llama-server.exe -m "%MODEL_PATH%" -c %CONTEXT_SIZE% -ngl %GPU_LAYERS% -t %CPU_THREADS% --jinja --host 127.0.0.1 --port %MODEL_PORT% %EXTRA_ARGS%
    echo pause
)
start "LLM Model Server" cmd /k "%TEMP%\_pua_start_model.bat"
goto :model_server_launched
:launch_llama_cli
where %LLAMA_EXE% >nul 2>nul
if errorlevel 1 (
    if not exist "%LLAMA_EXE%" (
        echo [ERROR] "%LLAMA_EXE%" was not found on PATH or as a direct path.
        echo         Set LLAMA_EXE in .env to the full path of your llama.exe,
        echo         or set BACKEND=llama-server in .env to use
        echo         runtime\windows\llama-server.exe instead.
        echo.
        pause
        exit /b 1
    )
)
echo Launching model server (llama.exe serve) in a new window...
> "%TEMP%\_pua_start_model.bat" (
    echo @echo off
    echo cd /d "%~dp0."
    echo "%LLAMA_EXE%" serve -m "%MODEL_PATH%" -ngl %GPU_LAYERS% -t %CPU_THREADS% %EXTRA_ARGS%
    echo pause
)
start "LLM Model Server" cmd /k "%TEMP%\_pua_start_model.bat"
goto :model_server_launched
:launch_ollama
echo Checking Ollama is installed and reachable at %OLLAMA_HOST% ...
where %OLLAMA_EXE% >nul 2>nul
if errorlevel 1 (
    echo [ERROR] "%OLLAMA_EXE%" was not found on PATH.
    echo         Install Ollama from https://ollama.com/download, or set
    echo         OLLAMA_EXE in .env to its full path.
    echo.
    pause
    exit /b 1
)
%OLLAMA_EXE% list >nul 2>nul
if errorlevel 1 (
    echo [ERROR] "%OLLAMA_EXE% list" failed - is the Ollama background
    echo         service running? Try restarting it, or run
    echo         "ollama serve" manually in another window and retry.
    echo.
    pause
    exit /b 1
)
echo Ollama is reachable. Installed models ^(local and cloud^):
echo.
%OLLAMA_EXE% list
echo.
echo Ollama runs its own persistent background service, so no separate
echo "LLM Model Server" window is needed - continuing straight to the
echo agent API. Set OLLAMA_MODEL_NAME in .env, or pick the model later
echo from the UI/CLI model switcher.
echo.
set "MODEL_READY=1"
goto :after_model_wait
:model_server_launched
echo Waiting for model server on 127.0.0.1:%MODEL_PORT% ...
set "MODEL_READY=0"
for /l %%i in (1,1,120) do (
    if "!MODEL_READY!"=="0" (
        powershell -NoProfile -Command "try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect('127.0.0.1', %MODEL_PORT%); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>nul
        if not errorlevel 1 (
            set "MODEL_READY=1"
        ) else (
            timeout /t 1 /nobreak >nul
        )
    )
)
if "%MODEL_READY%"=="0" (
    echo.
    echo [ERROR] Model server did not open port %MODEL_PORT% within 120 seconds.
    echo         Check the "LLM Model Server" window for errors before retrying.
    echo         Common causes: GPU out-of-memory - lower GPU_LAYERS in .env,
    echo         missing DLLs next to llama-server.exe, or the port already
    echo         being in use - change MODEL_PORT in .env.
    echo         The agent and UI were NOT started.
    echo.
    pause
    exit /b 1
)
:after_model_wait
if /i "%RESOLVED_BACKEND%"=="ollama" (
    echo Ollama backend confirmed ready.
) else (
    echo Model server is up.
)
rem ----------------------- step 2: launch agent API ----------------------
where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] No Python interpreter found - tried 'py' and 'python'.
        echo         Install Python 3.10+ and ensure it is on PATH.
        pause
        exit /b 1
    )
    set "PYLAUNCHER=python"
) else (
    set "PYLAUNCHER=py"
)
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment - first run only...
    %PYLAUNCHER% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r agent\requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies. Check your internet
        echo         connection - this is the ONE step that requires it,
        echo         first-time setup only.
        pause
        exit /b 1
    )
    call .venv\Scripts\deactivate.bat 2>nul
)
echo Launching agent API in a new window...
> "%TEMP%\_pua_start_agent.bat" (
    echo @echo off
    echo cd /d "%~dp0."
    echo call .venv\Scripts\activate.bat
    echo cd agent
    echo ..\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port %AGENT_PORT%
    echo pause
)
start "LLM Agent API" cmd /k "%TEMP%\_pua_start_agent.bat"
echo Waiting for agent API on 127.0.0.1:%AGENT_PORT% ...
set "AGENT_READY=0"
for /l %%i in (1,1,60) do (
    if "!AGENT_READY!"=="0" (
        powershell -NoProfile -Command "try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect('127.0.0.1', %AGENT_PORT%); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>nul
        if not errorlevel 1 (
            set "AGENT_READY=1"
        ) else (
            timeout /t 1 /nobreak >nul
        )
    )
)
if "%AGENT_READY%"=="0" (
    echo.
    echo [ERROR] Agent API did not open port %AGENT_PORT% within 60 seconds.
    echo         Check the "LLM Agent API" window for errors before retrying.
    echo         The UI was NOT opened.
    echo.
    pause
    exit /b 1
)
echo Agent API is up.
rem ------------------------- step 3: open the UI -------------------------
echo Opening UI in your default browser...
start "" "http://127.0.0.1:%AGENT_PORT%/"
echo.
echo =======================================================================
echo  Everything is running:
echo    - "LLM Model Server" window: llama backend on port %MODEL_PORT%
echo    - "LLM Agent API" window:    FastAPI agent on port %AGENT_PORT% (also serves the UI)
echo    - Your browser:              http://127.0.0.1:%AGENT_PORT%/
echo.
echo  You can also use the CLI from a separate terminal while this is
echo  running, e.g.:  python cli.py --list-projects
echo.
echo  Close this window any time - the two spawned windows keep running
echo  independently. Use Stop-All.bat, or Ctrl+C in each window, to stop.
echo =======================================================================
echo.
pause