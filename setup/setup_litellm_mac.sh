#!/usr/bin/env bash
# setup_litellm_mac.sh — create the deitel-openai-litellm conda environment on macOS
# This environment is used only by 02-05-09 (LiteLLM + Ollama). Run the main
# course setup first; then run this from the repo root:
#     bash setup/setup_litellm_mac.sh
# Optional: pass a different environment name:  bash setup/setup_litellm_mac.sh my-env-name

set -e  # stop on first error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_NAME="${1:-deitel-openai-litellm}"

echo "=== Creating conda environment '$ENV_NAME' ==="
conda env create -n "$ENV_NAME" -f "$SCRIPT_DIR/environment-litellm.yml"

echo ""
echo "=== Activating environment ==="
# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

echo ""
echo "=== Registering the Jupyter kernel ==="
python -m ipykernel install --user --name "$ENV_NAME" --display-name "Python ($ENV_NAME)"

echo ""
echo "============================================================"
echo " LiteLLM environment ready!"
echo ""
echo " Launch JupyterLab from the main course environment as usual,"
echo " open 02-05-09, and choose the kernel:  Python ($ENV_NAME)"
echo " (Kernel > Change Kernel...)"
echo "============================================================"
