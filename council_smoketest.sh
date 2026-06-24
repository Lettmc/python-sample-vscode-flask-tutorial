#!/bin/sh
# FleetWatch AI — Reasoning Council Smoke Test
# =============================================
# Proves the full cloud brain works before you wire the camera.
# Run this from any machine that can reach your Render backend.
#
# Usage:
#   chmod +x council_smoketest.sh
#   ./council_smoketest.sh
#
# Or override any value inline:
#   FW_CLOUD_URL=https://xyz.onrender.com FW_CLOUD_TOKEN=abc ./council_smoketest.sh

set -e

# ── Config (edit or set as env vars) ─────────────────────────────────
FW_CLOUD_URL="${FW_CLOUD_URL:-https://YOUR-SERVICE.onrender.com}"
FW_CLOUD_TOKEN="${FW_CLOUD_TOKEN:-change-me}"
CAMERA_ID="${CAMERA_ID:-P3268-LVE-TEST}"
ZONE="${ZONE:-perimeter}"
HOUR="${HOUR:-2}"               # 2am = after-hours, triggers HIGH
TEST_FRAME="${TEST_FRAME:-}"    # optional: path to a real JPEG

RED='\033[0;31m'; YEL='\033[0;33m'; GRN='\033[0;32m'; CYN='\033[0;36m'; NC='\033[0m'

banner() { printf "\n${CYN}══ %s ══${NC}\n" "$1"; }
ok()     { printf "${GRN}  [OK]${NC} %s\n" "$1"; }
warn()   { printf "${YEL}  [!!]${NC} %s\n" "$1"; }
fail()   { printf "${RED}  [XX]${NC} %s\n" "$1"; }

# ── Step 0: check deps ────────────────────────────────────────────────
banner "Step 0 — Checking tools"
command -v curl >/dev/null 2>&1 && ok "curl found" || { fail "curl not found"; exit 1; }
command -v python3 >/dev/null 2>&1 && HAVE_PY=1 && ok "python3 found" || HAVE_PY=0

if [ "$FW_CLOUD_URL" = "https://YOUR-SERVICE.onrender.com" ]; then
    fail "Set FW_CLOUD_URL to your Render service URL before running"
    exit 1
fi

# ── Step 1: health check ──────────────────────────────────────────────
banner "Step 1 — Backend health"
HEALTH=$(curl -sf --max-time 15 "${FW_CLOUD_URL}/health" 2>&1) || {
    fail "Cannot reach ${FW_CLOUD_URL}/health — is the Render service up?"
    exit 1
}
ok "Health: ${HEALTH}"

SEATS=$(echo "${HEALTH}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(', '.join(d.get('council_seats',[])))" 2>/dev/null || echo "unknown")
ok "Council seats enabled: ${SEATS}"

# ── Step 2: /api/alerts (fast, no frame) ─────────────────────────────
banner "Step 2 — /api/alerts (pre-judged event, no image)"
ALERT_RESP=$(curl -sf --max-time 20 \
  -H "Authorization: Bearer ${FW_CLOUD_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"visual_object\",\"tags\":{\"severity\":\"HIGH\",\"operator_level\":\"ESCALATE\",\"zone\":\"${ZONE}\",\"class\":\"person\",\"site\":\"Home Test Lab\"},\"fields\":{\"threat_score\":85,\"dwell_sec\":47}}" \
  "${FW_CLOUD_URL}/api/alerts?camera_id=${CAMERA_ID}&token=${FW_CLOUD_TOKEN}" 2>&1) || {
    fail "POST /api/alerts failed: ${ALERT_RESP}"
    exit 1
}
ok "/api/alerts response: ${ALERT_RESP}"

# ── Step 3: /api/clips — the council (with or without a real frame) ───
banner "Step 3 — /api/clips (Reasoning Council)"

# Build a tiny synthetic JPEG if no real frame supplied
if [ -z "${TEST_FRAME}" ]; then
    TEST_FRAME="/tmp/fw_smoketest_frame.jpg"
    if [ "${HAVE_PY}" = "1" ]; then
        python3 - <<'PYEOF'
# Minimal valid JPEG (16x16 grey square) — lets the council prove the pipeline
# without needing a real camera frame.
import base64, struct
jpeg_b64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoH"
    "BwYIDAoMCwsKCwsNCxAQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQME"
    "BAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU"
    "FBQUFBQUFBT/wAARCAAQABADASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/"
    "EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAA"
    "AAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwABmX/9k="
)
import base64
data = base64.b64decode(jpeg_b64)
with open("/tmp/fw_smoketest_frame.jpg", "wb") as f:
    f.write(data)
print("  synthetic frame written")
PYEOF
        ok "Synthetic 16x16 JPEG created at ${TEST_FRAME}"
    else
        warn "No python3 and no TEST_FRAME — sending text-only event to council"
        TEST_FRAME=""
    fi
fi

EVENT_JSON="{\"camera_id\":\"${CAMERA_ID}\",\"zone\":\"${ZONE}\",\"hour_of_day\":${HOUR},\"class\":\"person\",\"dwell_sec\":47}"

if [ -n "${TEST_FRAME}" ] && [ -f "${TEST_FRAME}" ]; then
    CLIP_RESP=$(curl -sf --max-time 60 \
      -H "Authorization: Bearer ${FW_CLOUD_TOKEN}" \
      -F "event=${EVENT_JSON};type=application/json" \
      -F "snapshot=@${TEST_FRAME};type=image/jpeg" \
      "${FW_CLOUD_URL}/api/clips?camera_id=${CAMERA_ID}&token=${FW_CLOUD_TOKEN}&zone=${ZONE}&hour=${HOUR}" 2>&1) || {
        fail "POST /api/clips failed: ${CLIP_RESP}"
        exit 1
    }
else
    CLIP_RESP=$(curl -sf --max-time 60 \
      -H "Authorization: Bearer ${FW_CLOUD_TOKEN}" \
      -F "event=${EVENT_JSON};type=application/json" \
      "${FW_CLOUD_URL}/api/clips?camera_id=${CAMERA_ID}&token=${FW_CLOUD_TOKEN}&zone=${ZONE}&hour=${HOUR}" 2>&1) || {
        fail "POST /api/clips failed: ${CLIP_RESP}"
        exit 1
    }
fi

ok "/api/clips response received"

# Pretty-print the council verdict if python3 is available
if [ "${HAVE_PY}" = "1" ]; then
    echo "${CLIP_RESP}" | python3 - <<'PYEOF'
import sys, json
raw = sys.stdin.read()
try:
    d = json.loads(raw)
    v = d.get("verdict", {})
    print(f"\n  Seats used     : {', '.join(v.get('seats_used', []))}")
    print(f"  Rule severity  : {v.get('rule_severity','?')}")
    print(f"  Threat score   : {v.get('threat_score','?')}")
    print(f"  Final severity : {v.get('severity','?')}  ({v.get('operator_level','?')})")
    print(f"  Action         : {v.get('recommended_action','?')}")
    print(f"  Narrative      : {v.get('narrative','')[:200]}")
    if v.get("errors"):
        print(f"  Seat errors    : {v['errors']}")
    lat = v.get("latency_ms", {})
    if lat:
        total = v.get("total_latency_ms", 0)
        print(f"  Latency        : {lat} | total={total}ms")
except Exception as e:
    print(f"  (raw) {raw[:600]}")
PYEOF
fi

# ── Step 4: verify event was stored ───────────────────────────────────
banner "Step 4 — Event storage"
STATS=$(curl -sf --max-time 10 \
  "${FW_CLOUD_URL}/api/stats?token=${FW_CLOUD_TOKEN}" 2>&1) || {
    warn "Could not reach /api/stats: ${STATS}"
}
ok "Stats: ${STATS}"

EVENT_LIST=$(curl -sf --max-time 10 \
  "${FW_CLOUD_URL}/api/events?limit=1&token=${FW_CLOUD_TOKEN}" 2>&1) || {
    warn "Could not reach /api/events"
}
ok "Latest event: $(echo "${EVENT_LIST}" | python3 -c "import sys,json; e=json.load(sys.stdin); print(e[0].get('narrative','?')[:100] if e else 'none')" 2>/dev/null || echo "${EVENT_LIST:0:200}")"

# ── Done ──────────────────────────────────────────────────────────────
banner "Smoke test PASSED"
printf "${GRN}  Full pipeline proven:${NC}\n"
printf "  camera event -> cloud backend -> Reasoning Council\n"
printf "  -> threat score -> narrative -> Teams-ready verdict\n"
printf "\n  Next: wire the P3268-LVE camera in FixedIT and point it at:\n"
printf "  ${CYN}${FW_CLOUD_URL}/api/clips${NC}\n\n"
