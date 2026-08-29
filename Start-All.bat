@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
rem =====================================================================
rem Portable USB LLM Agent - Start-All.bat
rem
rem Convenience wrapper: launches Start-Model.bat and Start-Agent.bat in
rem two separate console windows, waiting for the model server to accept
rem connections on MODEL_PORT before starting the agent (instead of a
rem blind timeout, which is either too short on big models or wastes
rem time on small ones).
rem
rem This does NOT replace Start-Model.bat / Start-Agent.bat - it just
rem sequences them. You can still run either one directly, and Stop-All
rem still needs manual Ctrl+C in each window per its own README notes.
rem =====================================================================
set "MODEL_PORT=8080"
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if "%%A"=="MODEL_PORT" if not "%%B"=="" set "MODEL_PORT=%%B"
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
echo Portable USB LLM Agent - starting model + agent
echo   Model port: %MODEL_PORT%  (from .env, default 8080)
echo.
echo Launching model server in a new window...
start "LLM Model Server" cmd /k call "Start-Model.bat"
echo Waiting for model server on 127.0.0.1:%MODEL_PORT% ...
set "READY=0"
for /l %%i in (1,1,120) do (
    if "!READY!"=="0" (
        powershell -NoProfile -Command "try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect('127.0.0.1', %MODEL_PORT%); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>nul
        if not errorlevel 1 (
            set "READY=1"
        ) else (
            timeout /t 1 /nobreak >nul
        )
    )
)
if "%READY%"=="0" (
    echo.
    echo [ERROR] Model server did not open port %MODEL_PORT% within 120 seconds.
    echo         Check the "LLM Model Server" window for errors ^(missing
    echo         model file, GPU OOM, backend not found, etc.^) before
    echo         retrying. The agent was NOT started.
    echo.
    pause
    exit /b 1
)
echo Model server is up. Launching agent in a new window...
start "LLM Agent API" cmd /k call "Start-Agent.bat"
echo.
echo Both windows launched:
echo   - "LLM Model Server" window: llama backend
echo   - "LLM Agent API" window:    FastAPI agent
echo Close this window any time - the two spawned windows keep running
echo independently. Use Stop-All.bat or Ctrl+C in each window to stop them.
echo.
pause