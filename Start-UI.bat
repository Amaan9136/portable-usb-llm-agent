@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem =====================================================================
rem Portable USB LLM Agent - Start-UI.bat
rem
rem Launches the model server and agent API (same sequencing as
rem Start-All.bat), then opens the cosmic UI in your default browser
rem once the agent is confirmed ready. The UI is served by the agent's
rem own FastAPI process (StaticFiles mount) - no separate web server.
rem =====================================================================

set "MODEL_PORT=8080"
set "AGENT_PORT=8787"
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if "%%A"=="MODEL_PORT" if not "%%B"=="" set "MODEL_PORT=%%B"
        if "%%A"=="AGENT_PORT" if not "%%B"=="" set "AGENT_PORT=%%B"
    )
)

if not exist "Start-Model.bat" (
    echo [ERROR] Start-Model.bat not found in %cd%.
    pause
    exit /b 1
)
if not exist "Start-Agent.bat" (
    echo [ERROR] Start-Agent.bat not found in %cd%.
    pause
    exit /b 1
)

echo.
echo Portable USB LLM Agent - starting model + agent + UI
echo   Model port: %MODEL_PORT%  (from .env, default 8080)
echo   Agent port: %AGENT_PORT%  (from .env, default 8787)
echo.

echo Launching model server in a new window...
start "LLM Model Server" cmd /k call "Start-Model.bat"

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
    echo         The agent and UI were NOT started.
    echo.
    pause
    exit /b 1
)

echo Model server is up. Launching agent API in a new window...
start "LLM Agent API" cmd /k call "Start-Agent.bat"

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

echo Agent API is up. Opening UI in your default browser...
start "" "http://127.0.0.1:%AGENT_PORT%/"

echo.
echo Three things are now running:
echo   - "LLM Model Server" window: llama backend
echo   - "LLM Agent API" window:    FastAPI agent (also serves the UI)
echo   - Your browser:              the cosmic UI at http://127.0.0.1:%AGENT_PORT%/
echo Close this window any time - the spawned windows keep running
echo independently. Use Stop-All.bat or Ctrl+C in each window to stop them.
echo.
pause
