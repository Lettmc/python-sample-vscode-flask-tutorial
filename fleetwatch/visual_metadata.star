# FleetWatch AI — Scene Metadata Parser (visual_metadata.star)
# =====================================================================
# Canonical perception parser per the Build Playbook.
# Consumes raw AXIS Scene Metadata (delivered over MQTT into FixedIT) and
# emits clean, ENRICHED "visual_object" events with zone, dwell, and
# direction filled in — the inputs alert_logic.star needs to judge.
#
# Tune ZONES, FOCUS_X/Y, and MIN_SCORE at the top to match YOUR scene.
# AXIS detection point: a human's is the FEET, a vehicle's is the CENTER.

# ── SCENE TUNING (edit these for each camera) ────────────────────────
MIN_SCORE = 0.30   # drop low-confidence detections early

# Zones are normalized rectangles [x_min, y_min, x_max, y_max] in 0..1
# coordinates. Order matters — first match wins. Add your real zones.
ZONES = [
    ("perimeter",  [0.00, 0.00, 1.00, 0.25]),   # top strip = far fence line
    ("restricted", [0.35, 0.30, 0.65, 0.70]),   # center = protected asset
    ("entrance",   [0.40, 0.75, 0.60, 1.00]),   # bottom-center = gate/door
]

# Focus point: the asset you care most about (battery box, mast). Used to
# compute whether an object is approaching it. Normalized 0..1.
FOCUS_X = 0.50
FOCUS_Y = 0.50

# ── Persistent tracking state (per object across frames) ─────────────
state = {
    "tracks": {},   # trackingId -> {first_ms, last_ms, last_cx, last_cy, last_dist}
}

DWELL_FORGET_MS = 30 * 60 * 1000   # forget tracks idle >30 min


def point_in_zone(cx, cy, rect):
    return rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3]


def zone_for(cx, cy):
    for name, rect in ZONES:
        if point_in_zone(cx, cy, rect):
            return name
    return "general"


def detection_point(obj_class, left, top, right, bottom):
    """Feet for humans, center for everything else (AXIS convention)."""
    cx = (left + right) / 2.0
    if obj_class == "human" or obj_class == "person":
        cy = bottom            # feet
    else:
        cy = (top + bottom) / 2.0   # center
    return cx, cy


def dist(ax, ay, bx, by):
    dx = ax - bx
    dy = ay - by
    return (dx * dx + dy * dy) ** 0.5


def apply(metric):
    """Telegraf entry point — one call per detected object in a frame."""
    fields = metric.fields()
    tags   = metric.tags()

    score = float(fields.get("confidence", fields.get("score", 0.0)))
    if score < MIN_SCORE:
        return None   # drop early, never reaches the classifier

    track_id  = str(fields.get("trackingId", tags.get("trackingId", "0")))
    obj_class = str(fields.get("class", fields.get("type", "object"))).lower()

    left   = float(fields.get("bbox_left",   fields.get("left",   0.0)))
    top    = float(fields.get("bbox_top",    fields.get("top",    0.0)))
    right  = float(fields.get("bbox_right",  fields.get("right",  0.0)))
    bottom = float(fields.get("bbox_bottom", fields.get("bottom", 0.0)))

    cx, cy = detection_point(obj_class, left, top, right, bottom)
    zone   = zone_for(cx, cy)

    now_ms = int(metric.time().unix_nano() / 1000000)

    # ── Dwell + direction tracking ───────────────────────────────────
    tr = state["tracks"].get(track_id)
    dist_to_focus = dist(cx, cy, FOCUS_X, FOCUS_Y)

    if tr == None:
        tr = {"first_ms": now_ms, "last_ms": now_ms,
              "last_cx": cx, "last_cy": cy, "last_dist": dist_to_focus}
        state["tracks"][track_id] = tr
        direction = "new"
    else:
        # Approaching the focus asset if distance shrank.
        if dist_to_focus < tr["last_dist"] - 0.02:
            direction = "approaching"
        elif dist_to_focus > tr["last_dist"] + 0.02:
            direction = "leaving"
        else:
            direction = "lingering"
        tr["last_ms"]   = now_ms
        tr["last_cx"]   = cx
        tr["last_cy"]   = cy
        tr["last_dist"] = dist_to_focus

    dwell_sec = (now_ms - tr["first_ms"]) / 1000.0

    # ── Periodic forget of stale tracks (memory hygiene) ─────────────
    if now_ms - state.get("last_gc", 0) > 60000:
        stale = [k for k, v in state["tracks"].items()
                 if now_ms - v["last_ms"] > DWELL_FORGET_MS]
        for k in stale:
            state["tracks"].pop(k)
        state["last_gc"] = now_ms

    # ── Emit enriched event ──────────────────────────────────────────
    hour = (int(now_ms / 3600000) % 24)

    metric.name = "visual_object"
    metric.add_tag("class", obj_class)
    metric.add_tag("zone", zone)
    metric.add_tag("direction", direction)
    metric.add_tag("trackingId", track_id)
    metric.add_field("confidence", score)
    metric.add_field("center_x", cx)
    metric.add_field("center_y", cy)
    metric.add_field("dwell_sec", dwell_sec)
    metric.add_field("dist_to_focus", dist_to_focus)
    metric.add_field("hour_of_day", hour)
    return metric
