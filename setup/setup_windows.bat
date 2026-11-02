@echo off
setlocal
REM setup_windows.bat — create or update the deitel-openai-agents conda environment on Windows
REM Run from the course folder in Anaconda Prompt:  setup\setup_windows.bat
REM Optional: pass a different environment name:  setup\setup_windows.bat my-env-name
REM Running it again updates an existing environment to the current course pins.
REM
REM Note: conda is itself a batch file, so every conda command below uses
REM "call". Without "call", Windows ends this script after the first conda command.

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "ENVIRONMENT_FILE=%SCRIPT_DIR%environment.yml"
set "ENV_NAME=%~1"
if "%ENV_NAME%"=="" set "ENV_NAME=deitel-openai-agents"

where conda >nul 2>nul
if errorlevel 1 (
    echo ERROR: conda not found. Run this script from Anaconda Prompt.
    echo Not using Anaconda? Run setup\setup_pip_windows.bat instead.
    exit /b 1
)

call conda env list | findstr /B /C:"%ENV_NAME% " >nul
if errorlevel 1 (
    echo === Creating conda environment '%ENV_NAME%' ===
    call conda env create -n "%ENV_NAME%" -f "%ENVIRONMENT_FILE%"
) else (
    echo === Updating existing conda environment '%ENV_NAME%' ===
    call conda env update -n "%ENV_NAME%" -f "%ENVIRONMENT_FILE%"
)
if errorlevel 1 (
    echo ERROR: conda environment create/update failed.
    exit /b 1
)

echo.
echo === Activating environment ===
call conda activate "%ENV_NAME%"
if errorlevel 1 (
    echo ERROR: conda activate failed.
    exit /b 1
)
if /I not "%CONDA_DEFAULT_ENV%"=="%ENV_NAME%" (
    echo ERROR: expected %ENV_NAME% to be active, but CONDA_DEFAULT_ENV is "%CONDA_DEFAULT_ENV%".
    exit /b 1
)
echo Active Conda environment: %CONDA_DEFAULT_ENV%
python -c "import sys; print('Python executable:', sys.executable)"

echo.
echo === Installing Playwright browser (Chromium) ===
python -m playwright install chromium
if errorlevel 1 (
    echo ERROR: playwright install failed.
    exit /b 1
)

echo.
echo === Registering the Jupyter kernel ===
python -m ipykernel install --user --name "%ENV_NAME%" --display-name "Python (%ENV_NAME%)"
if errorlevel 1 (
    echo ERROR: Jupyter kernel registration failed.
    exit /b 1
)

echo.
python "%SCRIPT_DIR%check_setup.py"

echo.
echo ============================================================
echo  Setup complete!
echo.
echo  To start working, open Anaconda Prompt and run:
echo    conda activate %ENV_NAME%
echo    cd /d "%REPO_ROOT%"
echo    jupyter lab
echo ============================================================
endlocal
