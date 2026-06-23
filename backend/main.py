"""
FleetWatch AI — Cloud Backend v3
=================================
Endpoints
---------
  POST /api/alerts              Pre-judged event from FixedIT pipeline
  POST /api/clips               Raw clip/snapshot → full Reasoning Council
  GET  /api/events              Query events (filter: level, camera, resolved)
  GET  /api/events/{id}         Single event with full verdict
  PATCH /api/events/{id}/resolve
  POST /api/events/{id}/feedback   false_alarm | real_threat
  GET  /api/events/{id}/candidates  Multi-candidate AI descriptions
  GET  /api/snapshots/{id}      Stored JPEG
  GET  /api/stats               Counts by severity + camera breakdown
  POST /api/notify              Manual re-send to notification channels
  POST /api/voice/response      Twilio voice call keypress handler
  GET  /api/cameras             Camera registry
  POST /api/cameras             Register / update a camera
  GET  /health

Storage: PostgreSQL (DATABASE_URL set) or SQLite.
Auth:    Bearer token (FW_CLOUD_TOKEN) on all write/query endpoints.
"""

import os
import json
import time
import secrets
import hashlib
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import requests
from fastapi import (FastAPI, Request, Header, HTTPException, Depends,
                     UploadFile, File, Form)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse

import reasoning_council
import detection_reasoning
import notifications

# ── Config ────────────────────────────────────────────────────────────────────
FW_TOKEN      = os.getenv("FW_CLOUD_TOKEN", "change-me")
DATABASE_URL  = os.getenv("DATABASE_URL", "")
DB_PATH       = os.getenv("FW_DB_PATH", "/tmp/fleetwatch.db")
MAX_EVENTS    = int(os.getenv("FW_MAX_EVENTS", "5000"))
SITE_NAME     = os.getenv("SITE", "Home Test Lab")

USE_PG = DATABASE_URL.startswith("postgres")

# ── Storage abstraction ────────────────────────────────────────────────────────
if USE_PG:
    import psycopg2
    import psycopg2.extras

    def get_db():
        return psycopg2.connect(DATABASE_URL)

    PLACEHOLDER = "%s"
else:
    import sqlite3

    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    PLACEHOLDER = "?"


def init_db():
    pk   = "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    blob = "BYTEA"              if USE_PG else "BLOB"
    stmts = [
        f"""CREATE TABLE IF NOT EXISTS events (
            id                  {pk},
            received_at         TEXT NOT NULL,
            camera_id           TEXT NOT NULL DEFAULT 'unknown',
            severity            TEXT NOT NULL DEFAULT 'LOW',
            operator_level      TEXT NOT NULL DEFAULT 'OBSERVE',
            threat_score        INTEGER DEFAULT 0,
            recommended_action  TEXT,
            narrative           TEXT,
            visual_description  TEXT,
            zone                TEXT,
            detected_class      TEXT,
            site                TEXT,
            provider            TEXT,
            raw_json            TEXT,
            bounding_boxes      TEXT,
            snapshot_id         TEXT,
            seats_used          TEXT,
            resolved            INTEGER DEFAULT 0,
            resolved_at         TEXT,
            feedback            TEXT,
            notified_channels   TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS snapshots (
            id          TEXT PRIMARY KEY,
            camera_id   TEXT,
            captured_at TEXT,
            data        {blob}
        )""",
        """CREATE TABLE IF NOT EXISTS cameras (
            camera_id   TEXT PRIMARY KEY,
            site        TEXT,
            zone        TEXT,
            model       TEXT,
            firmware    TEXT,
            ip          TEXT,
            status      TEXT DEFAULT 'unknown',
            last_seen   TEXT,
            first_seen  TEXT,
            event_count INTEGER DEFAULT 0,
            meta_json   TEXT
        )""",
    ]
    conn = get_db(); cur = conn.cursor()
    for stmt in stmts:
        try:
            cur.execute(stmt)
        except Exception as e:
            # Column already exists on upgrades — safe to ignore
            print(f"[init_db] {e}")
    conn.commit(); cur.close(); conn.close()


# ── Auth ──────────────────────────────────────────────────────────────────────
def verify_token(authorization: str = Header(default=""), token: str = ""):
    supplied = token or authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(supplied, FW_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return supplied


# ── Persist helpers ───────────────────────────────────────────────────────────
def store_event(event: dict) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cols = ["received_at", "camera_id", "severity", "operator_level",
            "threat_score", "recommended_action", "narrative",
            "visual_description", "zone", "detected_class", "site",
            "provider", "raw_json", "bounding_boxes", "snapshot_id",
            "seats_used", "notified_channels"]
    vals = [
        now,
        event.get("camera_id", "unknown"),
        event.get("severity", "LOW"),
        event.get("operator_level", "OBSERVE"),
        int(event.get("threat_score", 0)),
        event.get("recommended_action", ""),
        event.get("narrative", ""),
        event.get("visual_description", ""),
        event.get("zone", ""),
        event.get("detected_class", ""),
        event.get("site", SITE_NAME),
        event.get("provider", ""),
        json.dumps(event),
        json.dumps(event.get("bounding_boxes") or []),
        event.get("snapshot_id"),
        json.dumps(event.get("seats_used") or []),
        json.dumps(event.get("notified_channels") or {}),
    ]
    ph  = ", ".join([PLACEHOLDER] * len(cols))
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"INSERT INTO events ({', '.join(cols)}) VALUES ({ph})", vals)
    conn.commit()
    # Return the new event ID
    if USE_PG:
        cur.execute("SELECT lastval()")
    else:
        cur.execute("SELECT last_insert_rowid()")
    new_id = cur.fetchone()[0]
    cur.close(); conn.close()
    return new_id


def upsert_camera(camera_id: str, meta: dict):
    now  = datetime.now(timezone.utc).isoformat()
    conn = get_db(); cur = conn.cursor()
    if USE_PG:
        cur.execute(
            """INSERT INTO cameras (camera_id, site, zone, model, firmware, ip,
                status, last_seen, first_seen, event_count, meta_json)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s)
               ON CONFLICT (camera_id) DO UPDATE SET
                 status=EXCLUDED.status, last_seen=EXCLUDED.last_seen,
                 event_count=cameras.event_count+1,
                 zone=EXCLUDED.zone, meta_json=EXCLUDED.meta_json""",
            [camera_id, meta.get("site", SITE_NAME), meta.get("zone"),
             meta.get("model"), meta.get("firmware"), meta.get("ip"),
             "online", now, now, json.dumps(meta)]
        )
    else:
        cur.execute("SELECT camera_id FROM cameras WHERE camera_id=?", [camera_id])
        if cur.fetchone():
            cur.execute(
                "UPDATE cameras SET status='online', last_seen=?, event_count=event_count+1,"
                " zone=?, meta_json=? WHERE camera_id=?",
                [now, meta.get("zone"), json.dumps(meta), camera_id]
            )
        else:
            cur.execute(
                "INSERT INTO cameras VALUES (?,?,?,?,?,?,'online',?,?,1,?)",
                [camera_id, meta.get("site", SITE_NAME), meta.get("zone"),
                 meta.get("model"), meta.get("firmware"), meta.get("ip"),
                 now, now, json.dumps(meta)]
            )
    conn.commit(); cur.close(); conn.close()


def row_to_dict(row, cols) -> dict:
    d = dict(zip(cols, row))
    for f in ("bounding_boxes", "seats_used", "notified_channels"):
        if isinstance(d.get(f), str):
            try:
                d[f] = json.loads(d[f])
            except Exception:
                pass
    return d


# ── App ───────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="FleetWatch AI Backend", version="3.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.get("/health")
def health():
    return {
        "status":     "ok",
        "version":    "3.0.0",
        "storage":    "postgres" if USE_PG else "sqlite",
        "council_seats": [k for k, v in reasoning_council.SEATS.items() if v["enabled"]],
        "channels":   notifications.get_channel_status(),
        "ts":         datetime.now(timezone.utc).isoformat(),
    }


# ── /api/alerts — pre-judged event from FixedIT pipeline ─────────────────────
@app.post("/api/alerts")
async def api_alerts(request: Request, camera_id: str = "unknown",
                     token: str = "", _auth=Depends(verify_token)):
    body = await request.body()
    try:
        payload = json.loads(body or "{}")
    except Exception:
        payload = {}
    if isinstance(payload, list):
        payload = payload[0] if payload else {}

    tags   = payload.get("tags", {})
    fields = payload.get("fields", {})
    event  = {
        "camera_id":      camera_id,
        "severity":       tags.get("severity", "LOW"),
        "operator_level": tags.get("operator_level", "OBSERVE"),
        "zone":           tags.get("zone", ""),
        "detected_class": tags.get("class", ""),
        "threat_score":   int(fields.get("threat_score", 0)),
        "narrative":      tags.get("severity_reason", ""),
        "site":           tags.get("site", SITE_NAME),
        "bounding_boxes": [],
        "seats_used":     [],
        "raw_json":       body.decode("utf-8", "replace"),
    }
    upsert_camera(camera_id, {"site": event["site"], "zone": event["zone"]})
    event_id = store_event(event)
    notif_results = {}
    if event["severity"] == "HIGH":
        event["id"] = event_id
        notif_results = notifications.notify_all(event)
        event["notified_channels"] = notif_results
    return {"ok": True, "id": event_id, "severity": event["severity"],
            "notified": notif_results}


# ── /api/clips — raw clip + optional snapshot → full council ──────────────────
@app.post("/api/clips")
async def api_clips(camera_id: str = "unknown", token: str = "",
                    zone: str = "general", hour: int = 12,
                    snapshot: UploadFile = File(default=None),
                    event: str = Form(default="{}"),
                    _auth=Depends(verify_token)):
    img_bytes = await snapshot.read() if snapshot else b""
    try:
        ctx = json.loads(event)
    except Exception:
        ctx = {}
    ctx.setdefault("camera_id", camera_id)
    ctx.setdefault("zone", zone)
    ctx.setdefault("hour_of_day", hour)

    # TIER 1 — custom detection
    detections = []
    try:
        if img_bytes:
            detections = detection_reasoning.detect_objects(None, image_bytes=img_bytes)
    except Exception as e:
        print(f"[detect] {e}")

    rule_sev = detection_reasoning.classify_severity(detections, zone=zone, hour_of_day=hour)

    # TIER 2 — Reasoning Council (multi-candidate + verdict)
    verdict = reasoning_council.convene(
        img_bytes, detections, ctx, rule_severity=rule_sev, site_name=SITE_NAME
    )

    # Generate multi-candidate descriptions for HIGH events
    candidates = []
    if verdict.get("severity") == "HIGH" and img_bytes:
        try:
            _, candidates = reasoning_council.generate_candidates(
                img_bytes, detections, ctx, site_name=SITE_NAME
            )
        except Exception as e:
            print(f"[candidates] {e}")

    # Store snapshot
    snap_id = None
    if img_bytes:
        snap_id = hashlib.sha1(img_bytes).hexdigest()[:16] + f"_{int(time.time())}"
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            f"INSERT INTO snapshots (id,camera_id,captured_at,data) "
            f"VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})",
            [snap_id, camera_id, datetime.now(timezone.utc).isoformat(),
             img_bytes if USE_PG else sqlite3.Binary(img_bytes) if not USE_PG else img_bytes]
        )
        conn.commit(); cur.close(); conn.close()

    event_row = {
        "camera_id":          camera_id,
        "severity":           verdict["severity"],
        "operator_level":     verdict["operator_level"],
        "threat_score":       verdict["threat_score"],
        "recommended_action": verdict["recommended_action"],
        "narrative":          verdict["narrative"],
        "visual_description": verdict["visual_description"],
        "zone":               zone,
        "detected_class":     detections[0]["label"] if detections else "",
        "site":               SITE_NAME,
        "provider":           detection_reasoning.DETECTION_PROVIDER,
        "snapshot_id":        snap_id,
        "bounding_boxes":     detections,
        "seats_used":         verdict.get("seats_used", []),
    }
    event_row["raw_json"] = json.dumps({"verdict": verdict, "ctx": ctx, "candidates": candidates})

    upsert_camera(camera_id, {"site": SITE_NAME, "zone": zone})
    event_id = store_event(event_row)

    notif_results = {}
    if verdict["severity"] == "HIGH":
        event_row["id"] = event_id
        notif_results = notifications.notify_all(event_row)

    return {
        "ok":          True,
        "id":          event_id,
        "verdict":     verdict,
        "snapshot_id": snap_id,
        "candidates":  candidates,
        "notified":    notif_results,
    }


# ── /api/events — query ────────────────────────────────────────────────────────
@app.get("/api/events")
def get_events(limit: int = 100, level: str = "", camera: str = "",
               resolved: int = 0, token: str = "", _auth=Depends(verify_token)):
    where  = [f"resolved = {PLACEHOLDER}"]; params = [resolved]
    if level:
        where.append(f"severity = {PLACEHOLDER}"); params.append(level.upper())
    if camera:
        where.append(f"camera_id = {PLACEHOLDER}"); params.append(camera)
    sql = (f"SELECT * FROM events WHERE {' AND '.join(where)} "
           f"ORDER BY id DESC LIMIT {PLACEHOLDER}")
    params.append(min(limit, 500))
    conn = get_db(); cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = [row_to_dict(r, cols) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


@app.get("/api/events/{event_id}")
def get_event(event_id: int, token: str = "", _auth=Depends(verify_token)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM events WHERE id = {PLACEHOLDER}", [event_id])
    row  = cur.fetchone()
    cols = [d[0] for d in cur.description] if cur.description else []
    cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "Not found")
    return row_to_dict(row, cols)


@app.get("/api/events/{event_id}/candidates")
def get_candidates(event_id: int, token: str = "", _auth=Depends(verify_token)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT raw_json FROM events WHERE id = {PLACEHOLDER}", [event_id])
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row or not row[0]:
        raise HTTPException(404, "Not found")
    try:
        raw = json.loads(row[0])
        return {"candidates": raw.get("candidates", [])}
    except Exception:
        return {"candidates": []}


@app.patch("/api/events/{event_id}/resolve")
def resolve_event(event_id: int, token: str = "", _auth=Depends(verify_token)):
    now  = datetime.now(timezone.utc).isoformat()
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        f"UPDATE events SET resolved=1, resolved_at={PLACEHOLDER} WHERE id={PLACEHOLDER}",
        [now, event_id]
    )
    conn.commit(); cur.close(); conn.close()
    return {"ok": True, "resolved_at": now}


@app.post("/api/events/{event_id}/feedback")
async def event_feedback(event_id: int, request: Request, token: str = "",
                         _auth=Depends(verify_token)):
    body  = await request.json()
    label = body.get("label", "")
    conn  = get_db(); cur = conn.cursor()
    cur.execute(f"UPDATE events SET feedback={PLACEHOLDER} WHERE id={PLACEHOLDER}",
                [label, event_id])
    conn.commit(); cur.close(); conn.close()
    return {"ok": True, "label": label}


# ── /api/notify — manual re-send ──────────────────────────────────────────────
@app.post("/api/notify")
async def manual_notify(request: Request, token: str = "", _auth=Depends(verify_token)):
    """Manually trigger notification for a stored event or ad-hoc payload."""
    body = await request.json()
    event_id = body.get("event_id")
    channels = body.get("channels")  # optional override

    if event_id:
        conn = get_db(); cur = conn.cursor()
        cur.execute(f"SELECT * FROM events WHERE id={PLACEHOLDER}", [event_id])
        row  = cur.fetchone()
        cols = [d[0] for d in cur.description] if cur.description else []
        cur.close(); conn.close()
        if not row:
            raise HTTPException(404, "Event not found")
        event = row_to_dict(row, cols)
    else:
        event = body.get("event", {})

    results = notifications.notify_all(event, force_channels=channels)
    return {"ok": True, "results": results}


# ── /api/voice/response — Twilio keypress handler ─────────────────────────────
@app.post("/api/voice/response")
async def voice_response(request: Request):
    """Handle Twilio keypress response. Press 9 = escalate to emergency."""
    form = await request.form()
    digit = form.get("Digits", "")
    if digit == "9":
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna">Escalating to emergency services. Stay on the line.</Say>
  <Dial><Number>911</Number></Dial>
</Response>"""
    else:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna">Alert acknowledged. FleetWatch AI has logged your response. Goodbye.</Say>
  <Hangup/>
</Response>"""
    return HTMLResponse(content=twiml, media_type="application/xml")


# ── /api/snapshots ─────────────────────────────────────────────────────────────
@app.get("/api/snapshots/{snap_id}")
def get_snapshot(snap_id: str, token: str = "", _auth=Depends(verify_token)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT data FROM snapshots WHERE id={PLACEHOLDER}", [snap_id])
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "Snapshot not found")
    return Response(content=bytes(row[0]), media_type="image/jpeg")


# ── /api/cameras — fleet registry ─────────────────────────────────────────────
@app.get("/api/cameras")
def list_cameras(token: str = "", _auth=Depends(verify_token)):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM cameras ORDER BY last_seen DESC")
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


@app.post("/api/cameras")
async def register_camera(request: Request, token: str = "", _auth=Depends(verify_token)):
    body = await request.json()
    camera_id = body.get("camera_id")
    if not camera_id:
        raise HTTPException(400, "camera_id required")
    upsert_camera(camera_id, body)
    return {"ok": True, "camera_id": camera_id}


# ── /api/stats ─────────────────────────────────────────────────────────────────
@app.get("/api/stats")
def get_stats(token: str = "", _auth=Depends(verify_token)):
    conn = get_db(); cur = conn.cursor()

    def count(sql, p=()):
        cur.execute(sql, p); return cur.fetchone()[0]

    total  = count("SELECT COUNT(*) FROM events WHERE resolved=0")
    high   = count("SELECT COUNT(*) FROM events WHERE severity='HIGH' AND resolved=0")
    low    = count("SELECT COUNT(*) FROM events WHERE severity='LOW' AND resolved=0")
    active = count("SELECT COUNT(DISTINCT camera_id) FROM events WHERE resolved=0")
    total_cam = count("SELECT COUNT(*) FROM cameras")

    # Per-camera breakdown
    cur.execute(
        "SELECT camera_id, COUNT(*) as cnt, MAX(received_at) as last "
        "FROM events WHERE resolved=0 GROUP BY camera_id ORDER BY cnt DESC LIMIT 20"
    )
    by_cam = [{"camera_id": r[0], "open_events": r[1], "last_event": r[2]}
              for r in cur.fetchall()]

    cur.close(); conn.close()
    return {
        "open_total":     total,
        "high":           high,
        "low":            low,
        "active_cameras": active,
        "total_cameras":  total_cam,
        "by_camera":      by_cam,
        "channels":       notifications.get_channel_status(),
    }
