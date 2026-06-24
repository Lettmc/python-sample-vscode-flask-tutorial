#!/bin/sh
# FleetWatch AI — Clip / Snapshot Upload Helper
# Captures a JPEG from the camera and POSTs it to the cloud backend's
# /api/clips endpoint, where the Reasoning Council judges it.
#
# Called by the FixedIT pipeline (or an AXIS event recipient) for events
# that warrant a frame for the council to look at.
#
# REQUIRED ENV VARS (set in FixedIT Environment tab):
#   FW_CLOUD_URL    base URL, e.g. https://fleetwatch-backend.onrender.com
#   FW_CLOUD_TOKEN  Bearer token (must match backend FW_CLOUD_TOKEN)
#   VAPIX_USERNAME  camera user
#   VAPIX_PASSWORD  camera password
# OPTIONAL:
#   FW_ZONE   logical zone for this camera (default: general)
#
# Uses /bin/sh only (no bash) — portable for all Axis devices.

set -e

CAMERA_HOST="127.0.0.1"
SNAP_URL="http://${CAMERA_HOST}/axis-cgi/jpg/image.cgi?resolution=1280x720"
CLIP_DIR="/tmp/fw_clips"
LOG_PREFIX="[FleetWatch clip_upload]"
ZONE="${FW_ZONE:-general}"
SERIAL="${DEVICE_PROP_SERIAL:-unknown}"

mkdir -p "${CLIP_DIR}"

if [ -z "${FW_CLOUD_URL:-}" ]; then
    echo "${LOG_PREFIX} FW_CLOUD_URL not set — skipping cloud push" >&2
    exit 0
fi

# Read optional event JSON from stdin (passed by outputs.exec)
EVENT_JSON=""
while IFS= read -r line; do
    EVENT_JSON="${EVENT_JSON}${line}"
done
[ -z "${EVENT_JSON}" ] && EVENT_JSON="{}"

TS=$(date -u +"%Y%m%dT%H%M%SZ")
HOUR=$(date -u +%H)
SNAPSHOT_FILE="${CLIP_DIR}/snap_${TS}.jpg"

# Capture a frame from the camera
curl -s --anyauth \
    --user "${VAPIX_USERNAME:-root}:${VAPIX_PASSWORD:-}" \
    --max-time 8 \
    --output "${SNAPSHOT_FILE}" \
    "${SNAP_URL}" 2>/dev/null || true

ENDPOINT="${FW_CLOUD_URL}/api/clips?camera_id=${SERIAL}&token=${FW_CLOUD_TOKEN:-}&zone=${ZONE}&hour=${HOUR}"

if [ -f "${SNAPSHOT_FILE}" ]; then
    curl -s --max-time 45 \
        -H "Authorization: Bearer ${FW_CLOUD_TOKEN:-}" \
        -F "event=${EVENT_JSON};type=application/json" \
        -F "snapshot=@${SNAPSHOT_FILE};type=image/jpeg" \
        "${ENDPOINT}" >/dev/null 2>&1 || true
    rm -f "${SNAPSHOT_FILE}"
    echo "${LOG_PREFIX} Frame sent to council: zone=${ZONE} ts=${TS}" >&2
else
    # No snapshot — still send the event JSON for rule-only judging
    curl -s --max-time 20 \
        -H "Authorization: Bearer ${FW_CLOUD_TOKEN:-}" \
        -F "event=${EVENT_JSON};type=application/json" \
        "${ENDPOINT}" >/dev/null 2>&1 || true
    echo "${LOG_PREFIX} Event-only push (no snapshot): ts=${TS}" >&2
fi
