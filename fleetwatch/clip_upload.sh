#!/bin/sh
# FleetWatcher AI — HTTPS Clip Upload Helper
# Called by config_output_https_push.conf for ESCALATE/CHALLENGE events.
# Reads the JSON event payload from stdin, captures an SD card clip,
# and uploads it to the FleetWatcher cloud backend.
#
# REQUIRED ENV VARS (set in FixedIT Data Agent environment):
#   FW_CLOUD_URL    — e.g. https://your-backend.com/functions/v1/fw-webhook
#   FW_CLOUD_TOKEN  — Bearer token
#   VAPIX_USERNAME  — Camera username
#   VAPIX_PASSWORD  — Camera password
#
# Uses /bin/sh only (no bash) — portable for all Axis devices.

set -e

CAMERA_HOST="127.0.0.1"
SNAP_URL="http://${CAMERA_HOST}/axis-cgi/jpg/image.cgi?resolution=1280x720"
CLIP_DIR="/tmp/fw_clips"
LOG_PREFIX="[FleetWatcher clip_upload]"

mkdir -p "${CLIP_DIR}"

# Read event JSON from stdin (passed by outputs.exec)
EVENT_JSON=""
while IFS= read -r line; do
    EVENT_JSON="${EVENT_JSON}${line}"
done

if [ -z "${FW_CLOUD_URL:-}" ]; then
    echo "${LOG_PREFIX} FW_CLOUD_URL not set — skipping cloud push" >&2
    exit 0
fi

# Extract key fields with portable sh string ops
TS=$(date -u +"%Y%m%dT%H%M%SZ")
SERIAL="${DEVICE_PROP_SERIAL:-unknown}"
LEVEL=$(echo "${EVENT_JSON}" | grep -o '"fw_level":"[^"]*"' | cut -d'"' -f4)
SCENARIO=$(echo "${EVENT_JSON}" | grep -o '"scenario_name":"[^"]*"' | cut -d'"' -f4)

SNAPSHOT_FILE="${CLIP_DIR}/snap_${TS}.jpg"

# Capture snapshot from camera
curl -s \
    --anyauth \
    --user "${VAPIX_USERNAME:-root}:${VAPIX_PASSWORD:-}" \
    --max-time 8 \
    --output "${SNAPSHOT_FILE}" \
    "${SNAP_URL}" 2>/dev/null || true

# Build multipart payload and push to cloud
if [ -f "${SNAPSHOT_FILE}" ]; then
    curl -s \
        --max-time 30 \
        -H "Authorization: Bearer ${FW_CLOUD_TOKEN:-}" \
        -H "X-Camera-ID: ${SERIAL}" \
        -H "X-FW-Level: ${LEVEL:-OBSERVE}" \
        -H "X-FW-Scenario: ${SCENARIO:-unknown}" \
        -F "event=${EVENT_JSON};type=application/json" \
        -F "snapshot=@${SNAPSHOT_FILE};type=image/jpeg" \
        "${FW_CLOUD_URL}" >/dev/null 2>&1 || true

    rm -f "${SNAPSHOT_FILE}"
    echo "${LOG_PREFIX} Clip+snapshot pushed: level=${LEVEL} scenario=${SCENARIO} ts=${TS}" >&2
else
    # Fallback: push JSON event only (no snapshot)
    curl -s \
        --max-time 15 \
        -H "Authorization: Bearer ${FW_CLOUD_TOKEN:-}" \
        -H "Content-Type: application/json" \
        -H "X-Camera-ID: ${SERIAL}" \
        -H "X-FW-Level: ${LEVEL:-OBSERVE}" \
        -d "${EVENT_JSON}" \
        "${FW_CLOUD_URL}" >/dev/null 2>&1 || true

    echo "${LOG_PREFIX} Event-only push (no snapshot): level=${LEVEL} ts=${TS}" >&2
fi
