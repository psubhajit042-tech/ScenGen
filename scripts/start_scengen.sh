#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="$(basename "$ROOT_DIR")"
cd "$ROOT_DIR"

APP_ID="${1:-A34}"
SCENARIO_ID="${2:-S8}"

echo "============================================================"
echo "Starting $PROJECT_NAME from Linux terminal"
echo "============================================================"
echo "Folder   : $ROOT_DIR"
echo "App ID   : $APP_ID"
echo "Scenario : $SCENARIO_ID"
echo

if [ ! -f "venv/bin/python" ]; then
    echo "Virtual environment not found."
    echo "Run this first in the terminal:"
    echo "  ./scripts/setup_scengen_from_scratch.sh"
    exit 1
fi

# shellcheck disable=SC1091
source "venv/bin/activate"

if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama was not found in PATH."
    echo "Install Ollama and run:"
    echo "  ollama pull llama3:8b"
    echo "  ollama serve"
    exit 1
fi

if ! ollama list | grep -q "llama3:8b"; then
    echo "Ollama model llama3:8b was not found."
    echo "Run:"
    echo "  ollama pull llama3:8b"
    exit 1
fi

if ! command -v adb >/dev/null 2>&1; then
    echo "adb was not found in PATH."
    echo "Install Android platform-tools and verify:"
    echo "  adb devices"
    exit 1
fi

echo "Checking connected devices..."
adb devices
echo
echo "Make sure Ollama is running in the background."
echo "If it is not running, start it in another terminal with:"
echo "  ollama serve"
echo
echo "Running:"
echo "  python test.py $APP_ID $SCENARIO_ID"
echo
python test.py "$APP_ID" "$SCENARIO_ID"
