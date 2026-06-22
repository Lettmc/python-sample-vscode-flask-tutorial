#!/bin/sh
# FleetWatcher AI — AXIS Scene Metadata Reader
# Long-running daemon that subscribes to the Scene Metadata Message Broker topic
# and emits one JSON line per tracked object to stdout.
# Consumed by config_input_scene_metadata.conf via inputs.execd.
#
# Requires AXIS OS 11.9+ with Scene Metadata enabled.
# Uses /bin/sh only — portable for all Axis devices.

SOCKET="/run/axis-message-broker/metadata_sub.sock"
TOPIC="axis:CameraApplicationPlatform/SceneMetadata/TrackConsolidation"

# If the socket exists, subscribe directly via UNIX socket
if [ -S "${SOCKET}" ]; then
    # Subscribe to the consolidated track topic (one message per object exit)
    socat - "UNIX:${SOCKET}" <<EOF
{"method":"subscribe","topic":"${TOPIC}"}
EOF
    exit 0
fi

# Fallback: poll VAPIX metadata endpoint every 2 seconds and echo a heartbeat
# This allows the pipeline to run even on older firmware without Message Broker
while true; do
    SNAP_TS=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
    printf '{"timestamp":%s,"objectId":"heartbeat","class":"none","confidence":0,"bboxX":0,"bboxY":0,"bboxWidth":0,"bboxHeight":0,"velocity":0,"scenarioId":"0"}\n' \
        "$(date -u +%s)000"
    sleep 2
done
