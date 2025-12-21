#!/usr/bin/env bash
set -euo pipefail

# Check requirements
if ! command -v curl >/dev/null 2>&1; then
    echo "Error: curl is required but not installed." >&2
    exit 1
fi

REF="${METAREPO_REF:-main}"
URL="https://raw.githubusercontent.com/heimgewebe/metarepo/${REF}/contracts/knowledge.observatory.schema.json"
TARGET="${1:-contracts/knowledge.observatory.schema.json}"

# Ensure parent directory exists if target is a file path
mkdir -p "$(dirname "$TARGET")"

echo "Syncing to ${TARGET} from ${URL}..."
curl -sSL -f --retry 3 --retry-delay 2 --retry-connrefused -o "${TARGET}" "${URL}"
echo "Done."
