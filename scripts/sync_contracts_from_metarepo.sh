#!/usr/bin/env bash
set -e

REF="${METAREPO_REF:-main}"
URL="https://raw.githubusercontent.com/heimgewebe/metarepo/${REF}/contracts/knowledge.observatory.schema.json"
TARGET="contracts/knowledge.observatory.schema.json"

echo "Syncing ${TARGET} from ${URL}..."
curl -sSL -f -o "${TARGET}" "${URL}"
echo "Done."
