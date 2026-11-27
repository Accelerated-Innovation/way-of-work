#!/bin/sh
# Find a Python 3.11+ interpreter (python3 / python / py -3) and run the guard.
# If none is found, warn and allow the action: CI and GitHub push protection still enforce.
DIR="$(cd "$(dirname "$0")" && pwd)"
for PY in python3 python "py -3"; do
  if $PY -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
    exec $PY "$DIR/guard.py" "$@"
  fi
done
echo "Way of Work guard: Python 3.11+ not found; local checks skipped (CI still enforces)." >&2
exit 0
