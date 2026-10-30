#!/bin/bash

set -euo pipefail

# app.py looks for .env in the current working directory, so always run from
# the project root regardless of where this script was invoked from.
cd "$(dirname "$0")"

VENV_DIR="venv"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Error: no virtual environment found in $VENV_DIR/." >&2
    echo "Run ./install.sh first." >&2
    exit 1
fi

if [ ! -f .env ]; then
    echo "Error: configuration file .env not found." >&2
    echo "Create it with:  cp .env.example .env" >&2
    exit 1
fi

# exec so that Ctrl-C and termination signals reach Python directly
exec "$VENV_DIR/bin/python" app.py "$@"
