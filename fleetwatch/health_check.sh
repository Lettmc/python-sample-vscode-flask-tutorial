#!/bin/sh
# FleetWatcher AI — Camera Health Check Helper
# Called every 30s by config_input_camera_health.conf.
# Queries VAPIX system APIs and emits a JSON health metric.
# Uses /bin/sh only — portable for all Axis devices.

CAMERA_HOST="127.0.0.1"
VAPIX_AUTH="${VAPIX_USERNAME:-root}:${VAPIX_PASSWORD:-}"

vapix_get() {
    curl -s --anyauth --user "${VAPIX_AUTH}" --max-time 5 "http://${CAMERA_HOST}${1}" 2>/dev/null
}

vapix_post() {
    curl -s --anyauth --user "${VAPIX_AUTH}" --max-time 5 \
        -H "Content-Type: application/json" \
        -d "${2}" \
        "http://${CAMERA_HOST}${1}" 2>/dev/null
}

# ── Device info ──────────────────────────────────────────────
DEV_INFO=$(vapix_post "/axis-cgi/basicdeviceinfo.cgi" \
    '{"apiVersion":"1.0","method":"getAllProperties"}')

FW_VER=$(echo "${DEV_INFO}" | grep -o '"Version":"[^"]*"'   | head -1 | cut -d'"' -f4)
SERIAL=$(echo "${DEV_INFO}"  | grep -o '"SerialNumber":"[^"]*"' | head -1 | cut -d'"' -f4)
MODEL=$(echo "${DEV_INFO}"   | grep -o '"Model":"[^"]*"'    | head -1 | cut -d'"' -f4)

# ── System load via /proc ────────────────────────────────────
CPU_LOAD="0"
if [ -f /proc/loadavg ]; then
    CPU_LOAD=$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo "0")
fi

MEM_USED_PCT="0"
if [ -f /proc/meminfo ]; then
    MEM_TOTAL=$(awk '/^MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo "1")
    MEM_FREE=$(awk '/^MemAvailable/{print $2}' /proc/meminfo 2>/dev/null || echo "0")
    MEM_USED=$(( MEM_TOTAL - MEM_FREE ))
    MEM_USED_PCT=$(( MEM_USED * 100 / MEM_TOTAL ))
fi

UPTIME_SEC="0"
if [ -f /proc/uptime ]; then
    UPTIME_SEC=$(awk '{print int($1)}' /proc/uptime 2>/dev/null || echo "0")
fi

# ── SD card usage ────────────────────────────────────────────
SD_USED_PCT="0"
SD_TOTAL_MB="0"
SD_FREE_MB="0"
DF_OUT=$(df /var/spool/storage/SD_DISK 2>/dev/null | tail -1)
if [ -n "${DF_OUT}" ]; then
    SD_TOTAL_MB=$(echo "${DF_OUT}" | awk '{print int($2/1024)}')
    SD_FREE_MB=$(echo "${DF_OUT}"  | awk '{print int($4/1024)}')
    SD_USED_PCT=$(echo "${DF_OUT}" | awk '{print int($3*100/$2)}')
fi

# ── Network counters (loopback-safe) ────────────────────────
NET_RX="0"
NET_TX="0"
if [ -f /proc/net/dev ]; then
    NET_RX=$(awk 'NR>2 && $1!="lo:"{sum+=$2} END{print sum+0}' /proc/net/dev 2>/dev/null || echo "0")
    NET_TX=$(awk 'NR>2 && $1!="lo:"{sum+=$10} END{print sum+0}' /proc/net/dev 2>/dev/null || echo "0")
fi

# ── Temperature (if available) ───────────────────────────────
TEMP="0"
TEMP_FILE=$(find /sys/class/thermal -name 'temp' 2>/dev/null | head -1)
if [ -n "${TEMP_FILE}" ]; then
    RAW=$(cat "${TEMP_FILE}" 2>/dev/null || echo "0")
    TEMP=$(( RAW / 1000 ))
fi

# ── Emit JSON ────────────────────────────────────────────────
printf '{"serial":"%s","model":"%s","firmware_version":"%s","cpu_load":%s,"mem_used_pct":%s,"uptime_seconds":%s,"sd_used_pct":%s,"sd_total_mb":%s,"sd_free_mb":%s,"temperature_celsius":%s,"network_rx_bytes":%s,"network_tx_bytes":%s}\n' \
    "${SERIAL:-unknown}" \
    "${MODEL:-unknown}" \
    "${FW_VER:-unknown}" \
    "${CPU_LOAD}" \
    "${MEM_USED_PCT}" \
    "${UPTIME_SEC}" \
    "${SD_USED_PCT}" \
    "${SD_TOTAL_MB}" \
    "${SD_FREE_MB}" \
    "${TEMP}" \
    "${NET_RX}" \
    "${NET_TX}"
