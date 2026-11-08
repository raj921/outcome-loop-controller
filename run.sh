#!/usr/bin/env bash
set -euo pipefail
SIM_URL="${1:?usage: ./run.sh <SIM_URL>}"
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
exec "$PY" -m controller "$SIM_URL"
