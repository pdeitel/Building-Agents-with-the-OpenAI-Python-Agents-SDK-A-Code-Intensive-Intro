#!/usr/bin/env bash
# setup_mac.sh — create or update the deitel-openai-agents conda environment
# on macOS (also works on Linux).
# Run from the course folder:  bash setup/setup_mac.sh
# Optional: pass a different environment name:  bash setup/setup_mac.sh my-env-name
# Running it again updates an existing environment to the current course pins.

set -e  # stop on first error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_NAME="${1:-deitel-openai-agents}"

if ! command -v conda >/dev/null 2>&1; then
    echo "ERROR: conda not found. Install Anaconda or Miniconda, open a new"
    echo "terminal (or run: conda init zsh), then rerun setup/setup_mac.sh."
    echo "Not using Anaconda? Run setup/setup_pip_mac.sh instead."
    exit 1
fi

# make `conda activate` work inside this script
# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"

if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    echo "=== Updating existing conda environment '$ENV_NAME' ==="
    conda env update -n "$ENV_NAME" -f "$SCRIPT_DIR/environment.yml"
else
    echo "=== Creating conda environment '$ENV_NAME' ==="
    conda env create -n "$ENV_NAME" -f "$SCRIPT_DIR/environment.yml"
fi

echo ""
echo "=== Activating environment ==="
conda activate "$ENV_NAME"
python -c "import sys; print('Python executable:', sys.executable)"

echo ""
echo "=== Installing Playwright browser (Chromium) ==="
python -m playwright install chromium

echo ""
echo "=== Registering the Jupyter kernel ==="
python -m ipykernel install --user --name "$ENV_NAME" --display-name "Python ($ENV_NAME)"

echo ""
python "$SCRIPT_DIR/check_setup.py" || true

echo ""
echo "============================================================"
echo " Setup complete!"
echo ""
echo " To start working:"
echo "   conda activate $ENV_NAME"
echo "   cd \"$REPO_ROOT\""
echo "   jupyter lab"
echo "============================================================"
