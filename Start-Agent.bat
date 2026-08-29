@echo off
setlocal
cd /d "%~dp0"

echo.
echo Portable USB LLM Agent - starting agent API
echo.

where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] No Python interpreter found ^(tried 'py' and 'python'^).
        echo         Install Python 3.10+ and ensure it is on PATH.
        pause
        exit /b 1
    )
    set "PYLAUNCHER=python"
) else (
    set "PYLAUNCHER=py"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
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
        echo         connection - this is the ONE step that requires it
        echo         ^(first-time setup only^).
        pause
        exit /b 1
    )
) else (
    call .venv\Scripts\activate.bat
)

set "AGENT_PORT=8787"
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if "%%A"=="AGENT_PORT" if not "%%B"=="" set "AGENT_PORT=%%B"
    )
)

echo.
echo Agent will be available at: http://127.0.0.1:%AGENT_PORT%/docs
echo Docs will be available at: http://127.0.0.1:%AGENT_PORT%/redoc
echo Make sure Start-Model.bat is already running in another window.
echo.

cd agent
..\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port %AGENT_PORT%

pause