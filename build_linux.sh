#!/usr/bin/env bash
set -euo pipefail

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
elif [[ -x "venv/bin/python" ]]; then
  PYTHON="venv/bin/python"
else
  PYTHON="python3"
fi

echo "[build] using python: ${PYTHON}"

"${PYTHON}" -m pip install --upgrade pip pyinstaller
"${PYTHON}" -m PyInstaller --noconfirm --clean ./gametracker.spec

echo
echo "[build] done"
echo "Output: ./dist/GameTracker/"
