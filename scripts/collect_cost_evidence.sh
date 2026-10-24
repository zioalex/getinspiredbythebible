#!/usr/bin/env bash
# BITB-150 cost evidence collector — thin wrapper around collect_cost_evidence.py.
#
# All collection logic lives in the Python collector so the two entry points
# cannot drift. This wrapper only locates the sibling script (works from
# scripts/ on the host and from the flat /app layout in the Docker image) and
# replaces itself with python3, so environment variables (AZURE_*, DATABASE_URL,
# POSTGRES_SERVER_NAME, ...), arguments and the exit status pass through unchanged.
#
# Prerequisite: python3 (3.8+) on PATH, in addition to az and psql.
set -euo pipefail

if ! command -v python3 > /dev/null 2>&1; then
  echo "ERROR: python3 is required by collect_cost_evidence.sh" >&2
  exit 127
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/collect_cost_evidence.py" "$@"
