#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

./scripts/setup_scengen_from_scratch.sh

echo
echo "When setup is done, run this next:"
echo "  ollama pull llama3:8b"
echo "  ollama serve"
echo "  ./scripts/start_scengen.sh A34 S8"
