#!/bin/bash
# Winter — one-step install for macOS / Linux.
#
# Prerequisites (install these first):
#   - uv      : brew install uv          (or https://docs.astral.sh/uv/)
#   - Ollama  : https://ollama.com
set -e
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required but not installed."
    echo "Install it with:  brew install uv"
    exit 1
fi

echo "Creating the Python environment…"
uv venv --python 3.12 .venv

echo "Installing Winter and its dependencies (a few GB, one time)…"
uv pip install -e .

echo "Setting up voice cloning (this adds a couple of GB)…"
.venv/bin/python scripts/setup_voice.py || \
    echo "Voice cloning setup didn't finish — run scripts/setup_voice.py later."

echo
echo "Winter is installed."
if ! command -v ollama >/dev/null 2>&1; then
    echo "Next: install Ollama from https://ollama.com, then run:"
    echo "    ollama pull llama3.2:3b"
else
    echo "Make sure the model is pulled:  ollama pull llama3.2:3b"
fi
echo "Start Winter with:  .venv/bin/python -m winter"
