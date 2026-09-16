@echo off
REM setup_litellm_pip_windows.bat — create a pip virtual environment for 02-05-09 (LiteLLM + Ollama)
REM Requires Python 3.14 or later already installed and on PATH.
REM Run from the repo root in Command Prompt or PowerShell:
REM   setup\setup_litellm_pip_windows.bat

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "REQUIREMENTS_FILE=%SCRIPT_DIR%requirements-litellm.txt"
set "VENV_DIR=%REPO_ROOT%\.venv-litellm"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "KERNEL_NAME=deitel-openai-litellm"

echo === Checking Python version ===
python --version
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.14+ from https://python.org
    exit /b 1
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 14) else 1)"
if errorlevel 1 (
    echo ERROR: Python 3.14 or later is required. Install Python 3.14+ from https://python.org
    exit /b 1
)

echo.
echo === Creating virtual environment at .venv-litellm ===
python -m venv "%VENV_DIR%"
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
"%VENV_PYTHON%" -m pip install -r "%REQUIREMENTS_FILE%"
if errorlevel 1 (
    echo ERROR: pip install failed.
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
echo ============================================================
echo  LiteLLM environment ready!
echo.
echo  Launch JupyterLab from the main course environment as usual,
echo  open 02-05-09, and choose the kernel:  Python (%KERNEL_NAME%)
echo  (Kernel ^> Change Kernel...)
echo ============================================================
