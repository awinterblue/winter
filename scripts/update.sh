#!/bin/bash
# Winter — fetch the latest version and reinstall (macOS / Linux).
set -e
cd "$(dirname "$0")/.."

echo "Fetching the latest Winter…"
git pull

echo "Updating dependencies…"
uv pip install -e .

echo
echo "Winter is up to date. Restart it to use the new version."
