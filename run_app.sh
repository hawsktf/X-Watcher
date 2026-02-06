#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Run app.py using the virtual environment's python interpreter
"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/app.py" "$@"
