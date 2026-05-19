#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="$(basename "$ROOT_DIR")"
cd "$ROOT_DIR"

echo "============================================================"
echo "$PROJECT_NAME setup from scratch for Linux"
echo "============================================================"
echo
echo "Project folder detected:"
echo "  $ROOT_DIR"
echo
echo "To run this on any Linux machine:"
echo "1. Download or copy the whole project folder."
echo "2. Open a terminal."
echo "3. Move into the project folder with:"
echo "     cd /path/to/your/$PROJECT_NAME"
echo "4. Run:"
echo "     ./scripts/setup_scengen_from_scratch.sh"
echo

PYTHON_CMD=""
if command -v python3.9 >/dev/null 2>&1; then
    PYTHON_CMD="python3.9"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "Python was not found."
    echo "Install Python 3.9 first, then run this script again."
    exit 1
fi

echo "[1/6] Checking Python..."
"$PYTHON_CMD" --version
echo

echo "[2/6] Creating virtual environment in ./venv ..."
if [ ! -f "venv/bin/python" ]; then
    "$PYTHON_CMD" -m venv venv
else
    echo "Existing virtual environment found. Reusing it."
fi
echo

echo "[3/6] Activating virtual environment..."
# shellcheck disable=SC1091
source "venv/bin/activate"
echo

echo "[4/6] Installing requirements from requirements.txt ..."
python -m pip install --upgrade pip
pip install -r requirements.txt
echo

echo "[5/6] Checking ADB..."
if ! command -v adb >/dev/null 2>&1; then
    echo "ADB was not found in PATH."
    echo "Install Android platform-tools and make sure adb works in the terminal."
    echo "Example check:"
    echo "  adb devices"
else
    adb version
fi
echo

echo "[6/6] Checking Ollama..."
if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama was not found in PATH."
    echo "Install Ollama, then run:"
    echo "  ollama pull llama3:8b"
    echo "  ollama serve"
else
    ollama --version
    if ollama list | grep -q "llama3:8b"; then
        echo "Model llama3:8b is available."
    else
        echo "Model llama3:8b is not installed yet."
        echo "Run:"
        echo "  ollama pull llama3:8b"
    fi
fi
echo

echo "Final run checklist"
echo "1. Make sure Ollama is running and llama3:8b is installed:"
echo "     ollama pull llama3:8b"
echo "     ollama serve"
echo
echo "2. Connect your Android device and verify it is visible:"
echo "     adb devices"
echo
echo "3. Start $PROJECT_NAME with an app ID and scenario ID:"
echo "     python test.py A34 S8"
echo
echo "4. Or use the helper run script:"
echo "     ./scripts/start_scengen.sh A34 S8"
echo
echo "5. If you cloned this project into a different folder name, that is fine."
echo "   These scripts always use the folder they are currently inside."
echo
echo "Example IDs already present in testbot/conf.json:"
echo "  App A34 = Calculator-2"
echo "  Scenario S8 = calculation (8+5)"
echo
echo "Setup script complete."
