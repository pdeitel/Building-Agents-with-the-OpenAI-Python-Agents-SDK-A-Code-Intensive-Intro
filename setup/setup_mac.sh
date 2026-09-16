#!/usr/bin/env bash
# setup_mac.sh — create the deitel-openai conda environment on macOS
# Run from the repo root:  bash setup/setup_mac.sh
# Optional: pass a different environment name:  bash setup/setup_mac.sh my-env-name

set -e  # stop on first error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_NAME="${1:-deitel-openai}"


echo "=== Creating conda environment '$ENV_NAME' ==="
conda env create -n "$ENV_NAME" -f "$SCRIPT_DIR/environment.yml"

echo ""
echo "=== Activating environment ==="
# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

echo ""
echo "=== Installing Playwright browser (Chromium) ==="
playwright install chromium

echo ""
echo "=== Installing spaCy English model ==="
python -m spacy download en_core_web_sm

echo ""
echo "=== Registering the Jupyter kernel ==="
python -m ipykernel install --user --name "$ENV_NAME" --display-name "Python ($ENV_NAME)"


echo ""
echo "============================================================"
echo " Setup complete!"
echo ""
echo " To start working:"
echo "   conda activate $ENV_NAME"
echo "   cd $REPO_ROOT"
echo "   jupyter lab"
echo "============================================================"
