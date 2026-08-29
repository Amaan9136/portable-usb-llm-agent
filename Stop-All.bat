@echo off
rem =====================================================================
rem Portable USB LLM Agent - Stop-All.bat
rem
rem Best-effort stop for the model server (llama-server.exe) and the
rem uvicorn agent process. This kills by process name/window title
rem match, which is blunt - if you run other copies of these processes
rem for unrelated work, close those manually first, or close each
rem Portable USB LLM Agent window directly with Ctrl+C instead of
rem running this script.
rem =====================================================================
echo Stopping Portable USB LLM Agent processes (best-effort)...
taskkill /F /IM llama-server.exe >nul 2>nul
if not errorlevel 1 (
    echo   Stopped llama-server.exe
) else (
    echo   llama-server.exe was not running.
)
rem llama.exe (the llama-cli backend) is not force-killed by name here,
rem the same way python.exe is not below - "llama.exe" is a generic
rem enough name that other unrelated processes could share it. If you
rem used BACKEND=llama-cli, close that window manually with Ctrl+C.
echo   If you used the llama-cli backend (llama.exe), close that window
echo   manually with Ctrl+C - it is not force-killed by name for the
echo   same reason as the agent process below.
rem uvicorn runs as a python.exe process; we can't safely kill "python.exe"
rem by name alone since that would also kill unrelated Python processes.
rem Instead, ask the user to close that window directly.
echo   The agent (uvicorn) window must be closed manually with Ctrl+C or
echo   by closing its console window - it runs as a generic python.exe
echo   process and is not safe to force-kill by name.
echo.
echo Done.
pause