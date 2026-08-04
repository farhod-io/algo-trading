#!/usr/bin/env bash
# Auto‑run script for the ICT‑ML Telegram signal system.
# It ensures we are in the directory where the Python package resides
# and then launches the main entry point.

set -e

# Move to the directory containing this script (loyiha)
cd "$(dirname "${BASH_SOURCE[0]}")"

# Activate virtual environment if it exists (optional)
if [[ -f ../venv/bin/activate ]]; then
    source ../venv/bin/activate
fi

# Run the application
python3 main.py "$@"
