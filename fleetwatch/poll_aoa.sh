#!/bin/sh
# FleetWatcher AI — AOA Configuration + Alarm State Poller
# Calls the AOA VAPIX API to retrieve current scenario configuration
# and alarm state. Emits JSON consumed by config_input_aoa_events.conf.
# Uses /bin/sh only — portable for all Axis devices.

CAMERA_HOST="127.0.0.1"
VAPIX_AUTH="${VAPIX_USERNAME:-root}:${VAPIX_PASSWORD:-}"
AOA_CGI="/local/objectanalytics/control.cgi"

curl -s \
    --anyauth \
    --user "${VAPIX_AUTH}" \
    --max-time 4 \
    -H "Content-Type: application/json" \
    -d '{"apiVersion":"1.2","context":"fleetwatch","method":"getConfiguration"}' \
    "http://${CAMERA_HOST}${AOA_CGI}" 2>/dev/null
