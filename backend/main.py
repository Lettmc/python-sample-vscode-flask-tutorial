"""
FleetWatch AI — Cloud Backend
=============================
Canonical backend per the Build Playbook, upgraded with the Reasoning Council.

Endpoints
---------
  POST /api/alerts   Receive a judged event from the camera (FixedIT HTTP output).
                     Store it, push a card to Microsoft Teams.
  POST /api/clips    Receive a video clip / snapshot (AXIS HTTPS push). Run the
                     detection + reasoning COUNCIL, store, alert if HIGH.
  GET  /api/events   Query stored events (UI / operator dashboard).
  GET  /api/events/{id}        Single event.
  PATCH /api/events/{id}/resolve   Operator marks resolved (feedback loop).
  POST /api/events/{id}/feedback   One-click false-alarm / real-threat label.
  GET  /api/snapshots/{id}     Stored JPEG.
  GET  /api/stats              Open-event counts by level.
  GET  /health

Storage: PostgreSQL if DATABASE_URL is set (playbook Phase 7), else SQLite.
Auth:    Bearer token (FW_CLOUD_TOKEN) on write/query endpoints.
Alerts:  Microsoft Teams incoming webhook (TEAMS_WEBHOOK_URL).
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
from fastapi.responses import Response

import reasoning_council
import detection_reasoning

# ── Config ────────────────────────────────────────────────────────────────────
FW_TOKEN          = os.getenv("FW_CLOUD_TOKEN", "change-me")
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")
DATABASE_URL      = os.getenv("DATABASE_URL", "")          # postgres if set
DB_PATH           = os.getenv("FW_DB_PATH", "/tmp/fleetwatch.db")
MAX_EVENTS        = int(os.getenv("FW_MAX_EVENTS", "5000"))
SITE_NAME         = os.getenv("SITE", "Home Test Lab")

USE_PG = DATABASE_URL.startswith("postgres")


# ── Storage abstraction (Postgres or SQLite) ─────────────────────────────────
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
    ddl = """
    CREATE TABLE IF NOT EXISTS events (
        id            {pk},
        received_at   TEXT NOT NULL,
        camera_id     TEXT NOT NULL DEFAULT 'unknown',
        severity      TEXT NOT NULL DEFAULT 'LOW',
        operator_level TEXT NOT NULL DEFAULT 'OBSERVE',
        threat_score  INTEGER DEFAULT 0,
        recommended_action TEXT,
        narrative     TEXT,
        visual_description TEXT,
        zone          TEXT,
        detected_class TEXT,
        site          TEXT,
        provider      TEXT,
        raw_json      TEXT,
        snapshot_id   TEXT,
        resolved      INTEGER DEFAULT 0,
        resolved_at   TEXT,
        feedback      TEXT
    );
    CREATE TABLE IF NOT EXISTS snapshots (
        id TEXT PRIMARY KEY, camera_id TEXT, captured_at TEXT, data {blob}
    );
    """
    pk   = "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    blob = "BYTEA" if USE_PG else "BLOB"
    conn = get_db()
    cur  = conn.cursor()
    for stmt in ddl.format(pk=pk, blob=blob).split(";"):
        if stmt.strip():
            cur.execute(stmt)
    conn.commit()
    cur.close()
    conn.close()


# ── Auth ──────────────────────────────────────────────────────────────────────
def verify_token(authorization: str = Header(default=""),
                 token: str = ""):
    supplied = token or authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(supplied, FW_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return supplied


# ── Teams alert ───────────────────────────────────────────────────────────────
def send_teams_alert(event):
    if not TEAMS_WEBHOOK_URL:
        return
    color = {"HIGH": "FF0000", "LOW": "F97316", "IGNORE": "3B82F6"}.get(
        event.get("severity", "LOW"), "808080")
    card = {
        "@type": "MessageCard", "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": f"FleetWatch {event.get('severity')} alert",
        "sections": [{
            "activityTitle": f"🚨 FleetWatch AI — {event.get('operator_level','')} "
                             f"({event.get('severity','')})",
            "activitySubtitle": f"{event.get('site', SITE_NAME)} · "
                                f"{event.get('camera_id','?')}",
            "text": event.get("narrative") or event.get("visual_description") or "Event detected.",
            "facts": [
                {"name": "Threat score", "value": str(event.get("threat_score", "-"))},
                {"name": "Zone",         "value": event.get("zone", "-")},
                {"name": "Action",       "value": event.get("recommended_action", "-")},
                {"name": "Class",        "value": event.get("detected_class", "-")},
            ],
        }],
    }
    try:
        requests.post(TEAMS_WEBHOOK_URL, json=card, timeout=10)
    except Exception as e:
        print(f"[teams] webhook failed: {e}")


# ── Persist an event ──────────────────────────────────────────────────────────
def store_event(event):
    now = datetime.now(timezone.utc).isoformat()
    cols = ["received_at", "camera_id", "severity", "operator_level",
            "threat_score", "recommended_action", "narrative",
            "visual_description", "zone", "detected_class", "site",
            "provider", "raw_json", "snapshot_id"]
    vals = [now, event.get("camera_id", "unknown"), event.get("severity", "LOW"),
            event.get("operator_level", "OBSERVE"), int(event.get("threat_score", 0)),
            event.get("recommended_action", ""), event.get("narrative", ""),
            event.get("visual_description", ""), event.get("zone", ""),
            event.get("detected_class", ""), event.get("site", SITE_NAME),
            event.get("provider", ""), json.dumps(event),
            event.get("snapshot_id")]
    ph = ", ".join([PLACEHOLDER] * len(cols))
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"INSERT INTO events ({', '.join(cols)}) VALUES ({ph})", vals)
    conn.commit(); cur.close(); conn.close()


# ── App ───────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="FleetWatch AI Backend", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok", "storage": "postgres" if USE_PG else "sqlite",
            "council_seats": [k for k, v in reasoning_council.SEATS.items() if v["enabled"]],
            "ts": datetime.now(timezone.utc).isoformat()}


# ── /api/alerts — pre-judged event from the camera pipeline ──────────────────
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
    event = {
        "camera_id":      camera_id,
        "severity":       tags.get("severity", "LOW"),
        "operator_level": tags.get("operator_level", "OBSERVE"),
        "zone":           tags.get("zone", ""),
        "detected_class": tags.get("class", ""),
        "threat_score":   int(fields.get("threat_score", 0)),
        "narrative":      tags.get("severity_reason", ""),
        "site":           tags.get("site", SITE_NAME),
        "raw_json":       body.decode("utf-8", "replace"),
    }
    store_event(event)
    if event["severity"] == "HIGH":
        send_teams_alert(event)
    return {"ok": True, "severity": event["severity"]}


# ── /api/clips — raw clip/snapshot, run the full council ─────────────────────
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

    # TIER 1 — custom detection (Roboflow / Robovision)
    try:
        detections = detection_reasoning.detect_objects(None, image_bytes=img_bytes) \
            if img_bytes else []
    except Exception as e:
        print(f"[detect] {e}")
        detections = []

    rule_sev = detection_reasoning.classify_severity(
        detections, zone=zone, hour_of_day=hour)

    # TIER 2 — the reasoning council
    verdict = reasoning_council.convene(
        img_bytes, detections, ctx, rule_severity=rule_sev, site_name=SITE_NAME)

    # Store snapshot
    snap_id = None
    if img_bytes:
        snap_id = hashlib.sha1(img_bytes).hexdigest()[:16] + f"_{int(time.time())}"
        conn = get_db(); cur = conn.cursor()
        cur.execute(f"INSERT INTO snapshots (id,camera_id,captured_at,data) "
                    f"VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})",
                    [snap_id, camera_id, datetime.now(timezone.utc).isoformat(),
                     img_bytes if USE_PG else sqlite3.Binary(img_bytes)])
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
    }
    event_row["raw_json"] = json.dumps({"verdict": verdict, "ctx": ctx})
    store_event(event_row)
    if verdict["severity"] == "HIGH":
        send_teams_alert(event_row)
    return {"ok": True, "verdict": verdict, "snapshot_id": snap_id}


# ── Query ─────────────────────────────────────────────────────────────────────
@app.get("/api/events")
def get_events(limit: int = 100, level: str = "", camera: str = "",
               resolved: int = 0, token: str = "", _auth=Depends(verify_token)):
    where = [f"resolved = {PLACEHOLDER}"]; params = [resolved]
    if level:
        where.append(f"severity = {PLACEHOLDER}"); params.append(level)
    if camera:
        where.append(f"camera_id = {PLACEHOLDER}"); params.append(camera)
    sql = (f"SELECT * FROM events WHERE {' AND '.join(where)} "
           f"ORDER BY id DESC LIMIT {PLACEHOLDER}")
    params.append(min(limit, 500))
    conn = get_db(); cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


@app.get("/api/events/{event_id}")
def get_event(event_id: int, token: str = "", _auth=Depends(verify_token)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM events WHERE id = {PLACEHOLDER}", [event_id])
    row = cur.fetchone()
    cols = [d[0] for d in cur.description] if cur.description else []
    cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "Not found")
    return dict(zip(cols, row))


@app.patch("/api/events/{event_id}/resolve")
def resolve_event(event_id: int, token: str = "", _auth=Depends(verify_token)):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"UPDATE events SET resolved=1, resolved_at={PLACEHOLDER} "
                f"WHERE id={PLACEHOLDER}", [now, event_id])
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}


# ── Feedback loop (playbook Phase 6): the data moat ──────────────────────────
@app.post("/api/events/{event_id}/feedback")
async def event_feedback(event_id: int, request: Request, token: str = "",
                         _auth=Depends(verify_token)):
    body = await request.json()
    label = body.get("label", "")          # "false_alarm" | "real_threat"
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"UPDATE events SET feedback={PLACEHOLDER} WHERE id={PLACEHOLDER}",
                [label, event_id])
    conn.commit(); cur.close(); conn.close()
    return {"ok": True, "label": label}


@app.get("/api/snapshots/{snap_id}")
def get_snapshot(snap_id: str, token: str = "", _auth=Depends(verify_token)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT data FROM snapshots WHERE id={PLACEHOLDER}", [snap_id])
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "Snapshot not found")
    return Response(content=bytes(row[0]), media_type="image/jpeg")


@app.get("/api/stats")
def get_stats(token: str = "", _auth=Depends(verify_token)):
    conn = get_db(); cur = conn.cursor()
    def count(sql, p=()):
        cur.execute(sql, p); return cur.fetchone()[0]
    stats = {
        "open_total": count("SELECT COUNT(*) FROM events WHERE resolved=0"),
        "high":       count(f"SELECT COUNT(*) FROM events WHERE severity='HIGH' AND resolved=0"),
        "low":        count(f"SELECT COUNT(*) FROM events WHERE severity='LOW' AND resolved=0"),
        "active_cameras": count("SELECT COUNT(DISTINCT camera_id) FROM events WHERE resolved=0"),
    }
    cur.close(); conn.close()
    return stats
