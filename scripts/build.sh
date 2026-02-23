#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"

rm -rf "${DIST_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python3}"

${PYTHON_BIN} -m pip install -U pip
${PYTHON_BIN} -m pip install "pyinstaller>=6.0"

DATA_ARG="src/clicards/data:clicards/data"

${PYTHON_BIN} -m PyInstaller --clean --onefile \
  --name clicards \
  --add-data "${DATA_ARG}" \
  -m clicards.client

${PYTHON_BIN} -m PyInstaller --clean --onefile \
  --name clicards-server \
  --add-data "${DATA_ARG}" \
  -m clicards.server

echo "Binaries are in ${DIST_DIR}"
