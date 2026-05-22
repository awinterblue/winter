#!/bin/bash
#
# Winter — bootstrap installer for macOS / Linux.
#
# Installs everything Winter needs — uv, Ollama, Winter itself, and the AI
# model — into a "Winter" folder in your home directory. Run it with:
#
#   curl -fsSL https://raw.githubusercontent.com/awinterblue/winter/main/scripts/bootstrap.sh | bash
#
set -e

INSTALL_DIR="$HOME/Winter"
REPO="https://github.com/awinterblue/winter.git"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

step() { printf "\n\033[1;36m==> %s\033[0m\n" "$1"; }

step "Installing Winter — this takes a few minutes."

# --- git (macOS ships it with the developer tools) -------------------------
if ! command -v git >/dev/null 2>&1; then
    step "macOS needs to install developer tools first — a popup will appear."
    xcode-select --install || true
    echo "Click Install, wait for it to finish, then run this command again."
    exit 1
fi

# --- uv (manages Python + packages) ----------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    step "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

# --- Ollama (the local AI runtime) -----------------------------------------
if ! command -v ollama >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
        step "Installing Ollama..."
        brew install ollama
    else
        step "Please install Ollama from https://ollama.com, then run this again."
        exit 1
    fi
fi
(ollama serve >/dev/null 2>&1 &)   # make sure the model server is running
sleep 3

# --- download Winter -------------------------------------------------------
step "Downloading Winter to $INSTALL_DIR..."
if [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" pull --ff-only
else
    git clone "$REPO" "$INSTALL_DIR"
fi

# --- install Winter --------------------------------------------------------
step "Installing Winter's dependencies (a few GB, one time)..."
cd "$INSTALL_DIR"
uv venv --python 3.12 .venv
uv pip install -e .
bash scripts/make_app.sh || true   # build Winter.app for one-click launching

# --- voice cloning ---------------------------------------------------------
step "Setting up voice cloning (this adds a couple of GB)..."
.venv/bin/python scripts/setup_voice.py || \
    echo "Voice cloning setup didn't finish — run scripts/setup_voice.py later."

# --- the AI model ----------------------------------------------------------
step "Downloading the AI model (~2 GB)..."
ollama pull llama3.2:3b

step "Winter is installed!"
echo "Open the \"Winter\" folder in your home directory and double-click Winter.app."
open "$INSTALL_DIR" 2>/dev/null || true
