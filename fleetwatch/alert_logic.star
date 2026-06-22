# FleetWatch AI — Severity Classifier (alert_logic.star)
# =====================================================================
# Canonical decision brain per the Build Playbook.
# Runs INSIDE the FixedIT Data Agent (Telegraf) pipeline on the camera.
#
# Output: every event gets a "severity" tag of HIGH / LOW / IGNORE.
# Keep this IN SYNC with classify_severity() in backend/detection_reasoning.py
# so the edge and the cloud always agree.
#
# Philosophy (from the playbook): detection is free on the camera;
# JUDGMENT is the product. This file is the judgment.

# ── Tunables (match detection_reasoning.py) ──────────────────────────
MIN_CONFIDENCE = 0.55

# Custom hazards that are HIGH no matter where/when they appear.
# These come from the Roboflow model, not AOA.
HIGH_SEVERITY_LABELS = {
    "hard-hat-off": True,
    "no-vest":      True,
    "fire":         True,
    "smoke":        True,
    "open-gate":    True,
    "intruder":     True,
    "weapon":       True,
}

# Zones that are sensitive at any hour.
SENSITIVE_ZONES = {
    "restricted": True,
    "perimeter":  True,
    "battery-box": True,
    "mast":       True,
    "generator":  True,
}

# Night window — outside business hours everything is more suspicious.
NIGHT_START_HOUR = 20   # 8pm
NIGHT_END_HOUR   = 6    # 6am


def is_night(hour):
    return hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR


def classify(metric):
    """Assign HIGH / LOW / IGNORE to one enriched visual_object event."""
    fields = metric.fields()
    tags   = metric.tags()

    label      = tags.get("class", fields.get("class", "object"))
    confidence = float(fields.get("confidence", 0.0))
    zone       = tags.get("zone", "general")
    hour       = int(fields.get("hour_of_day", 12))
    dwell_sec  = float(fields.get("dwell_sec", 0.0))

    # Below confidence floor → not worth an operator's attention.
    if confidence < MIN_CONFIDENCE:
        metric.add_tag("severity", "IGNORE")
        metric.add_tag("severity_reason", "low_confidence")
        return metric

    # Custom hazard labels are always HIGH.
    if HIGH_SEVERITY_LABELS.get(label, False):
        metric.add_tag("severity", "HIGH")
        metric.add_tag("severity_reason", "hazard:" + label)
        return metric

    # Sensitive zone OR after-hours → HIGH for people/vehicles.
    if SENSITIVE_ZONES.get(zone, False) or is_night(hour):
        metric.add_tag("severity", "HIGH")
        reason = "sensitive_zone" if SENSITIVE_ZONES.get(zone, False) else "after_hours"
        metric.add_tag("severity_reason", reason)
        return metric

    # Long dwell anywhere is at least worth a look.
    if dwell_sec >= 120.0:
        metric.add_tag("severity", "HIGH")
        metric.add_tag("severity_reason", "dwell_exceeded")
        return metric

    # Everything else that cleared confidence → LOW (log, don't alert loudly).
    metric.add_tag("severity", "LOW")
    metric.add_tag("severity_reason", "routine_activity")
    return metric


# ── Operator-facing level mapping ────────────────────────────────────
# The UI displays Observe / Challenge / Escalate. Map internal severity:
#   IGNORE  -> (suppressed, not shown)
#   LOW     -> Observe
#   HIGH    -> Escalate  (Challenge is reserved for HIGH that needs human verify)
OPERATOR_LEVEL = {
    "IGNORE":   "OBSERVE",
    "LOW":      "OBSERVE",
    "HIGH":     "ESCALATE",
}


def apply(metric):
    """Telegraf entry point."""
    metric = classify(metric)
    sev = metric.tags().get("severity", "IGNORE")
    metric.add_tag("operator_level", OPERATOR_LEVEL.get(sev, "OBSERVE"))
    return metric
