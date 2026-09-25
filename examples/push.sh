#!/usr/bin/env bash
# Send one track to Cloudbase as a test jump.
#
#   CLOUDBASE_TOKEN=cb_pat_... ./push.sh sample-track.csv
#
# Needs curl and jq. Drop "isSimulated" once you're sending real jumps.
set -euo pipefail

csv_file="${1:?usage: push.sh <track.csv>}"
: "${CLOUDBASE_TOKEN:?set CLOUDBASE_TOKEN to a cb_pat_ token}"

jq -Rs '{deviceType: "flysight", deviceId: "flysight:EXAMPLE", isSimulated: true, csv: .}' "$csv_file" |
  curl --fail-with-body -sS https://api.getcloudbase.com/jumps/import-gps-csv \
    -H "Authorization: Bearer ${CLOUDBASE_TOKEN}" \
    -H "Content-Type: application/json" \
    --data-binary @-
echo
# → {"jumpId":"…","matchResult":"created"}
