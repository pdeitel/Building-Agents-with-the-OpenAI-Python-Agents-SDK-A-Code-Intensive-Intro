@echo off
REM setup_windows.bat — create the deitel-openai conda environment on Windows
REM Run from the repo root in Anaconda Prompt:  setup\setup_windows.bat
REM Optional: pass a different environment name:  setup\setup_windows.bat my-env-name

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "ENVIRONMENT_FILE=%SCRIPT_DIR%environment.yml"
set "ENV_NAME=%~1"
if "%ENV_NAME%"=="" set "ENV_NAME=deitel-openai"

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
echo === Installing spaCy English model ===
python -m spacy download en_core_web_sm
if errorlevel 1 (
    echo ERROR: spaCy English model install failed.
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
echo  Setup complete!
echo.
echo  To start working, open Anaconda Prompt and run:
echo    conda activate %ENV_NAME%
echo    cd /d "%REPO_ROOT%"
echo    jupyter lab
echo ============================================================
