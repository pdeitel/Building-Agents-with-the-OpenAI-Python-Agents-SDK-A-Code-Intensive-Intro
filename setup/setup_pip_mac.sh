#!/usr/bin/env bash
# setup_pip_mac.sh — create or update a pip virtual environment (.venv) on
# macOS / Linux. Requires Python 3.14 already installed. (Python 3.15 is not
# supported yet: LiteLLM, used by 02-05-09, requires Python below 3.15.)
# Run from the course folder:  bash setup/setup_pip_mac.sh
# Optional: pass a different Jupyter kernel name:  bash setup/setup_pip_mac.sh my-kernel-name
# Running it again updates .venv to the current course pins.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
KERNEL_NAME="${1:-deitel-openai-agents}"

# Use the first interpreter found that is Python 3.14.
PYTHON=""
for candidate in python3.14 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 14) else 1)' 2>/dev/null; then
        PYTHON="$(command -v "$candidate")"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.14 not found. Install it from https://python.org"
    echo "(or with Homebrew: brew install python@3.14), then rerun setup/setup_pip_mac.sh."
    exit 1
fi
echo "=== Using Python: $("$PYTHON" --version) ($PYTHON) ==="

echo ""
echo "=== Checking Graphviz ==="
if ! command -v dot >/dev/null 2>&1; then
    echo "ERROR: Graphviz is required for Agents SDK graph visualizations."
    echo "Install it first, for example: brew install graphviz"
    echo "(Debian/Ubuntu: sudo apt install graphviz). Then rerun setup/setup_pip_mac.sh."
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
python -m pip install --upgrade pip
python -m pip install --upgrade -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "=== Installing Playwright browser (Chromium) ==="
python -m playwright install chromium

echo ""
echo "=== Registering the Jupyter kernel ==="
python -m ipykernel install --user --name "$KERNEL_NAME" --display-name "Python ($KERNEL_NAME)"

echo ""
python "$SCRIPT_DIR/check_setup.py" || true

echo ""
echo "============================================================"
echo " Setup complete!"
echo ""
echo " To start working:"
echo "   cd \"$REPO_ROOT\""
echo "   source .venv/bin/activate"
echo "   jupyter lab"
echo "============================================================"
