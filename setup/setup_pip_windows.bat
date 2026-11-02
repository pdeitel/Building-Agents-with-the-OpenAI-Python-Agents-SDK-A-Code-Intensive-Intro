@echo off
setlocal
REM setup_pip_windows.bat — create or update a pip virtual environment (.venv) on Windows
REM Requires Python 3.14 from https://python.org
REM (Python 3.15 is not supported yet: LiteLLM, used by 02-05-09, requires
REM Python below 3.15.)
REM Run from the course folder in Command Prompt or PowerShell:
REM   setup\setup_pip_windows.bat
REM Optional: pass a different Jupyter kernel name:
REM   setup\setup_pip_windows.bat my-kernel-name
REM Running it again updates .venv to the current course pins.

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "REQUIREMENTS_FILE=%SCRIPT_DIR%requirements.txt"
set "VENV_DIR=%REPO_ROOT%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "KERNEL_NAME=deitel-openai-agents"
if not "%~1"=="" set "KERNEL_NAME=%~1"

echo === Finding Python 3.14 ===
REM Prefer the Python launcher (py), which python.org installs; fall back to python.
set "PYTHON="
py -3.14 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PYTHON=py -3.14"
if not defined PYTHON (
    python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 14) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON=python"
)
if not defined PYTHON (
    echo ERROR: Python 3.14 not found. Install it from https://python.org
    echo and check "Add python.exe to PATH" in the installer.
    exit /b 1
)
%PYTHON% --version

echo.
echo === Checking Graphviz ===
where dot >nul 2>nul
if errorlevel 1 (
    echo ERROR: Graphviz is required for Agents SDK graph visualizations.
    echo Install Graphviz from https://graphviz.org/download/ and make sure dot.exe is on PATH.
    exit /b 1
)
dot -V

echo.
echo === Creating virtual environment at .venv ===
%PYTHON% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo ERROR: venv creation failed.
    exit /b 1
)

echo.
echo === Installing packages ===
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: pip upgrade failed.
    exit /b 1
)
"%VENV_PYTHON%" -m pip install --upgrade -r "%REQUIREMENTS_FILE%"
if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
)

echo.
echo === Installing Playwright browser (Chromium) ===
"%VENV_PYTHON%" -m playwright install chromium
if errorlevel 1 (
    echo ERROR: playwright install failed.
    exit /b 1
)

echo.
echo === Registering the Jupyter kernel ===
"%VENV_PYTHON%" -m ipykernel install --user --name "%KERNEL_NAME%" --display-name "Python (%KERNEL_NAME%)"
if errorlevel 1 (
    echo ERROR: Jupyter kernel registration failed.
    exit /b 1
)

echo.
"%VENV_PYTHON%" "%SCRIPT_DIR%check_setup.py"

echo.
echo ============================================================
echo  Setup complete!
echo.
echo  To start working, open a new Command Prompt and run:
echo    cd /d "%REPO_ROOT%"
echo    .venv\Scripts\activate
echo    jupyter lab
echo ============================================================
endlocal
