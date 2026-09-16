@echo off
REM setup_litellm_windows.bat — create the deitel-openai-litellm conda environment on Windows
REM This environment is used only by 02-05-09 (LiteLLM + Ollama). Run the main
REM course setup first; then run this from the repo root in Anaconda Prompt:
REM     setup\setup_litellm_windows.bat
REM Optional: pass a different environment name:  setup\setup_litellm_windows.bat my-env-name

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "ENVIRONMENT_FILE=%SCRIPT_DIR%environment-litellm.yml"
set "ENV_NAME=%~1"
if "%ENV_NAME%"=="" set "ENV_NAME=deitel-openai-litellm"

echo === Creating conda environment '%ENV_NAME%' ===
conda env create -n "%ENV_NAME%" -f "%ENVIRONMENT_FILE%"
if errorlevel 1 (
    echo ERROR: conda env create failed.
    exit /b 1
)

echo.
echo === Activating environment ===
call conda activate "%ENV_NAME%"
if errorlevel 1 (
    echo ERROR: conda activate failed.
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
echo ============================================================
echo  LiteLLM environment ready!
echo.
echo  Launch JupyterLab from the main course environment as usual,
echo  open 02-05-09, and choose the kernel:  Python (%ENV_NAME%)
echo  (Kernel ^> Change Kernel...)
echo ============================================================
