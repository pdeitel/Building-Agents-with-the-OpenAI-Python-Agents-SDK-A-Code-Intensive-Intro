#!/usr/bin/env bash
# setup_pip_mac.sh — create a pip virtual environment on macOS / Linux
# Requires Python 3.14 or later already installed.
# Run from the repo root:  bash setup/setup_pip_mac.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"


# Prefer python3.14; fall back to python3/python only if it is also 3.14+.
PYTHON=$(command -v python3.14 || command -v python3 || command -v python || true)
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python not found. Install Python 3.14+ and rerun setup/setup_pip_mac.sh."
    exit 1
fi
echo "=== Using Python: $($PYTHON --version) ==="
"$PYTHON" - <<'PY'
import sys

if sys.version_info < (3, 14):
    raise SystemExit(
        "ERROR: Python 3.14 or later is required. "
        "Install Python 3.14+ and rerun setup/setup_pip_mac.sh."
    )
PY

echo ""
echo "=== Checking Graphviz ==="
if ! command -v dot >/dev/null 2>&1; then
    echo "ERROR: Graphviz is required for Agents SDK graph visualizations."
    echo "Install it first, for example: brew install graphviz"
    echo "Then rerun setup/setup_pip_mac.sh."
    exit 1
fi
dot -V

echo ""
echo "=== Creating virtual environment at .venv ==="
"$PYTHON" -m venv "$VENV_DIR"

echo ""
echo "=== Activating virtual environment ==="
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo ""
echo "=== Installing packages ==="
pip install --upgrade pip
pip install -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "=== Installing Playwright browser (Chromium) ==="
playwright install chromium

echo ""
echo "=== Installing spaCy English model ==="
python -m spacy download en_core_web_sm

echo ""
echo "=== Registering the Jupyter kernel ==="
python -m ipykernel install --user --name deitel-openai --display-name "Python (deitel-openai)"


echo ""
echo "============================================================"
echo " Setup complete!"
echo ""
echo " To start working:"
echo "   source .venv/bin/activate"
echo "   cd $REPO_ROOT"
echo "   jupyter lab"
echo "============================================================"
