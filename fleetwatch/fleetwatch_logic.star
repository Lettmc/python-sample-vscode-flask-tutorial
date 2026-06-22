# FleetWatcher AI — Observe / Challenge / Escalate Classification Engine
# Starlark (Python-like) logic that runs inside the FixedIT Data Agent pipeline.
# Processes every AOA event and Scene Metadata detection in real time.
#
# LEVEL DEFINITIONS:
#   OBSERVE   — Notable activity. Log and display. No immediate response needed.
#   CHALLENGE — Requires human verification. Notify on-duty staff.
#   ESCALATE  — Immediate security response required. Push alert + trigger clip upload.

# ── Persistent state (survives across metric calls within one run) ─────────────
state = {
    "dwell": {},          # objectId -> first_seen_unix_ms
    "alarm_seen": {},     # scenario_id -> last_alarm_unix_ms
    "frame_count": {},    # scenario_id -> count per heartbeat window
    "last_heartbeat": 0,
}

# ── Thresholds (tunable via tags or hardcoded here) ───────────────────────────
DWELL_CHALLENGE_SEC = 120    # person in area >2 min → CHALLENGE
DWELL_ESCALATE_SEC  = 300    # person in area >5 min → ESCALATE
VELOCITY_HIGH       = 3.0    # fast movement (m/s) → CHALLENGE
GROUP_THRESHOLD     = 4      # ≥4 people simultaneously → CHALLENGE

# ── Scenario type severity base ───────────────────────────────────────────────
SCENARIO_BASE = {
    "motion":            "OBSERVE",
    "fence":             "CHALLENGE",
    "crosslinecounting": "OBSERVE",
    "occupancyInArea":   "OBSERVE",
    "tailgating":        "ESCALATE",
    "timeInArea":        "CHALLENGE",
    "ppemonitoring":     "CHALLENGE",
}

def classify_aoa(metric):
    """Classify an AOA event metric and add fw_level tag."""
    fields = metric.fields()
    tags   = metric.tags()

    scenario_type = fields.get("scenario_type", "motion")
    alarm_active  = fields.get("alarm_active", False)
    scenario_id   = str(fields.get("scenario_id", "0"))

    # No alarm → still OBSERVE (AOA is just reporting state, not firing)
    if not alarm_active:
        metric.add_tag("fw_level", "OBSERVE")
        metric.add_tag("fw_reason", "no_alarm")
        return metric

    # Track alarm timestamp per scenario
    now_ms = int(metric.time().unix_nano() / 1_000_000)
    state["alarm_seen"][scenario_id] = now_ms

    # Base level from scenario type
    level  = SCENARIO_BASE.get(scenario_type, "OBSERVE")
    reason = "scenario_type:" + scenario_type

    # Elevate fence breach with human to ESCALATE
    if scenario_type == "fence":
        level  = "ESCALATE"
        reason = "fence_breach"

    # Tailgating is always ESCALATE
    if scenario_type == "tailgating":
        level  = "ESCALATE"
        reason = "tailgating_detected"

    metric.add_tag("fw_level",  level)
    metric.add_tag("fw_reason", reason)
    return metric


def classify_scene_metadata(metric):
    """Classify a Scene Metadata detection and track dwell time."""
    fields    = metric.fields()
    object_id = str(fields.get("objectId", ""))
    obj_class = str(fields.get("class", ""))
    velocity  = float(fields.get("velocity", 0.0))
    now_ms    = int(metric.time().unix_nano() / 1_000_000)

    # Track when we first saw this object
    if object_id and object_id not in state["dwell"]:
        state["dwell"][object_id] = now_ms

    dwell_sec = 0
    if object_id and object_id in state["dwell"]:
        dwell_sec = (now_ms - state["dwell"][object_id]) / 1000.0

    # Determine level
    level  = "OBSERVE"
    reason = "initial_detection"

    # Dwell escalation
    if dwell_sec >= DWELL_ESCALATE_SEC:
        level  = "ESCALATE"
        reason = "dwell_exceeded_{}s".format(int(DWELL_ESCALATE_SEC))
    elif dwell_sec >= DWELL_CHALLENGE_SEC:
        level  = "CHALLENGE"
        reason = "dwell_exceeded_{}s".format(int(DWELL_CHALLENGE_SEC))

    # Fast-moving human → CHALLENGE
    if obj_class == "human" and velocity >= VELOCITY_HIGH and level == "OBSERVE":
        level  = "CHALLENGE"
        reason = "high_velocity_{:.1f}mps".format(velocity)

    metric.add_tag("fw_level",     level)
    metric.add_tag("fw_reason",    reason)
    metric.add_field("dwell_sec",  int(dwell_sec))

    return metric


def cleanup_stale_dwell(now_ms):
    """Remove objects not seen for >30 minutes to prevent memory leak."""
    stale_ids = [k for k, v in state["dwell"].items()
                 if (now_ms - v) > 1_800_000]
    for k in stale_ids:
        state["dwell"].pop(k)


def apply(metric):
    """Entry point — called by Telegraf for every metric."""
    name = metric.name

    if name == "aoa_event":
        return classify_aoa(metric)

    if name == "scene_metadata":
        now_ms = int(metric.time().unix_nano() / 1_000_000)
        # Periodic cleanup every ~5 minutes
        if now_ms - state.get("last_cleanup", 0) > 300_000:
            cleanup_stale_dwell(now_ms)
            state["last_cleanup"] = now_ms
        return classify_scene_metadata(metric)

    # Pass everything else through untouched
    return metric
