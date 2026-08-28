@echo off
rem =====================================================================
rem Portable USB LLM Agent — Stop-All.bat
rem
rem Best-effort stop for llama-server.exe and the uvicorn agent process.
rem This kills by process name/window title match, which is blunt — if
rem you run other copies of these processes for unrelated work, close
rem those manually first, or close each Portable USB LLM Agent window directly
rem with Ctrl+C instead of running this script.
rem =====================================================================

echo Stopping Portable USB LLM Agent processes (best-effort)...

taskkill /F /IM llama-server.exe >nul 2>nul
if not errorlevel 1 (
    echo   Stopped llama-server.exe
) else (
    echo   llama-server.exe was not running.
)

rem uvicorn runs as a python.exe process; we can't safely kill "python.exe"
rem by name alone since that would also kill unrelated Python processes.
rem Instead, ask the user to close that window directly.
echo   The agent (uvicorn) window must be closed manually with Ctrl+C or
echo   by closing its console window - it runs as a generic python.exe
echo   process and is not safe to force-kill by name.

echo.
echo Done.
pause