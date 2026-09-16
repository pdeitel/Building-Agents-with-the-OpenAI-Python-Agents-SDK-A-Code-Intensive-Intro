#!/usr/bin/env bash
# setup_litellm_pip_mac.sh — create a pip virtual environment for 02-05-09 (LiteLLM + Ollama)
# Requires Python 3.14 or later already installed.
# Run from the repo root:  bash setup/setup_litellm_pip_mac.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv-litellm"
KERNEL_NAME="deitel-openai-litellm"

PYTHON=$(command -v python3.14 || command -v python3 || command -v python || true)
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python not found. Install Python 3.14+ and rerun setup/setup_litellm_pip_mac.sh."
    exit 1
fi
echo "=== Using Python: $($PYTHON --version) ==="
"$PYTHON" - <<'PY'
import sys

if sys.version_info < (3, 14):
    raise SystemExit(
        "ERROR: Python 3.14 or later is required. "
        "Install Python 3.14+ and rerun setup/setup_litellm_pip_mac.sh."
    )
PY

echo ""
echo "=== Creating virtual environment at .venv-litellm ==="
"$PYTHON" -m venv "$VENV_DIR"

echo ""
echo "=== Activating virtual environment ==="
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo ""
echo "=== Installing packages ==="
pip install --upgrade pip
pip install -r "$SCRIPT_DIR/requirements-litellm.txt"

echo ""
echo "=== Registering the Jupyter kernel ==="
python -m ipykernel install --user --name "$KERNEL_NAME" --display-name "Python ($KERNEL_NAME)"

echo ""
echo "============================================================"
echo " LiteLLM environment ready!"
echo ""
echo " Launch JupyterLab from the main course environment as usual,"
echo " open 02-05-09, and choose the kernel:  Python ($KERNEL_NAME)"
echo " (Kernel > Change Kernel...)"
echo "============================================================"
