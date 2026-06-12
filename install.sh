#!/usr/bin/env bash
# Launch the Bergner Skills installer TUI (macOS / Linux).
# Prefers uv (auto-installs Textual via PEP 723 inline deps); falls back to a
# local virtualenv + pip on systems without uv.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if command -v uv >/dev/null 2>&1; then
    exec uv run installer.py "$@"
fi

echo "uv not found — falling back to a local virtualenv (.venv)."
echo "Tip: install uv for a faster, zero-setup launch: https://docs.astral.sh/uv/"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "error: need either 'uv' or '$PY' on PATH." >&2
    exit 1
fi

[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet "textual>=0.60"
exec python installer.py "$@"
