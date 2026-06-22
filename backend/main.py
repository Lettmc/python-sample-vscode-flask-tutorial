"""
FleetWatcher AI — Cloud Backend
Receives events and snapshots from on-camera FleetWatcher pipeline.
Stores them in SQLite and exposes a REST API for the UI and operators.

Deploy on Render as a Python web service (see render.yaml).
"""

import os
import json
import time
import sqlite3
import hashlib
import secrets
import base64
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI, Request, Header, HTTPException,
    UploadFile, File, Form, Depends
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH      = os.getenv("FW_DB_PATH",    "/tmp/fleetwatch.db")
FW_TOKEN     = os.getenv("FW_CLOUD_TOKEN", "change-me-in-render-env")
MAX_EVENTS   = int(os.getenv("FW_MAX_EVENTS", "5000"))
SNAP_DIR     = Path(os.getenv("FW_SNAP_DIR", "/tmp/fw_snapshots"))
SNAP_DIR.mkdir(parents=True, exist_ok=True)


# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT    NOT NULL,
            camera_id   TEXT    NOT NULL DEFAULT 'unknown',
            fw_level    TEXT    NOT NULL DEFAULT 'OBSERVE',
            fw_reason   TEXT,
            measurement TEXT,
            scenario_id TEXT,
            scenario_name TEXT,
            scenario_type TEXT,
            dwell_sec   REAL    DEFAULT 0,
            site        TEXT,
            area        TEXT,
            raw_json    TEXT,
            snapshot_id TEXT,
            resolved    INTEGER DEFAULT 0,
            resolved_at TEXT
        );
        CREATE TABLE IF NOT EXISTS snapshots (
            id        TEXT    PRIMARY KEY,
            camera_id TEXT,
            captured_at TEXT,
            data      BLOB
        );
        CREATE INDEX IF NOT EXISTS idx_events_level ON events(fw_level);
        CREATE INDEX IF NOT EXISTS idx_events_camera ON events(camera_id);
        CREATE INDEX IF NOT EXISTS idx_events_received ON events(received_at);
        """)


# ── Auth ──────────────────────────────────────────────────────────────────────
def verify_token(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, FW_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token


# ── App startup ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="FleetWatcher AI Cloud Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


# ── Ingest: JSON event from outputs.http ─────────────────────────────────────
@app.post("/functions/v1/fw-webhook")
async def ingest_json(
    request: Request,
    x_camera_id: str = Header(default="unknown"),
    x_fw_level: str  = Header(default="OBSERVE"),
    x_fw_scenario: str = Header(default="unknown"),
    _auth = Depends(verify_token),
):
    body = await request.body()
    try:
        payload = json.loads(body)
    except Exception:
        payload = {}

    snap_id = None
    _store_event(
        camera_id     = x_camera_id,
        fw_level      = x_fw_level,
        fw_reason     = payload.get("tags", {}).get("fw_reason", ""),
        measurement   = payload.get("name", ""),
        scenario_id   = str(payload.get("fields", {}).get("scenario_id", "")),
        scenario_name = payload.get("tags", {}).get("scenario_name", x_fw_scenario),
        scenario_type = payload.get("tags", {}).get("scenario_type", ""),
        dwell_sec     = float(payload.get("fields", {}).get("dwell_sec", 0)),
        site          = payload.get("tags", {}).get("site", ""),
        area          = payload.get("tags", {}).get("area", ""),
        raw_json      = body.decode("utf-8", errors="replace"),
        snapshot_id   = snap_id,
    )
    return {"ok": True}


# ── Ingest: multipart from clip_upload.sh (event JSON + snapshot JPEG) ───────
@app.post("/functions/v1/fw-clip")
async def ingest_clip(
    event: str           = Form(default="{}"),
    snapshot: UploadFile = File(default=None),
    x_camera_id: str     = Header(default="unknown"),
    x_fw_level: str      = Header(default="OBSERVE"),
    x_fw_scenario: str   = Header(default="unknown"),
    _auth = Depends(verify_token),
):
    try:
        payload = json.loads(event)
    except Exception:
        payload = {}

    snap_id = None
    if snapshot:
        snap_bytes = await snapshot.read()
        snap_id    = hashlib.sha1(snap_bytes).hexdigest()[:16] + f"_{int(time.time())}"
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO snapshots(id,camera_id,captured_at,data) VALUES(?,?,?,?)",
                (snap_id, x_camera_id, datetime.now(timezone.utc).isoformat(), snap_bytes)
            )

    _store_event(
        camera_id     = x_camera_id,
        fw_level      = x_fw_level,
        fw_reason     = payload.get("fw_reason", ""),
        measurement   = payload.get("name", "aoa_event"),
        scenario_id   = str(payload.get("scenario_id", "")),
        scenario_name = payload.get("scenario_name", x_fw_scenario),
        scenario_type = payload.get("scenario_type", ""),
        dwell_sec     = float(payload.get("dwell_sec", 0)),
        site          = payload.get("site", ""),
        area          = payload.get("area", ""),
        raw_json      = event,
        snapshot_id   = snap_id,
    )
    return {"ok": True, "snapshot_id": snap_id}


def _store_event(**kwargs):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute("""
            INSERT INTO events
              (received_at,camera_id,fw_level,fw_reason,measurement,
               scenario_id,scenario_name,scenario_type,dwell_sec,
               site,area,raw_json,snapshot_id)
            VALUES
              (:ts,:camera_id,:fw_level,:fw_reason,:measurement,
               :scenario_id,:scenario_name,:scenario_type,:dwell_sec,
               :site,:area,:raw_json,:snapshot_id)
        """, {"ts": now, **kwargs})
        # Trim oldest events to keep DB size bounded
        db.execute(f"""
            DELETE FROM events WHERE id IN (
              SELECT id FROM events ORDER BY id ASC
              LIMIT MAX(0, (SELECT COUNT(*) FROM events) - {MAX_EVENTS})
            )
        """)


# ── Query: recent events ──────────────────────────────────────────────────────
@app.get("/api/events")
def get_events(
    limit: int    = 100,
    level: str    = "",
    camera: str   = "",
    resolved: int = 0,
    _auth = Depends(verify_token),
):
    where, params = ["resolved = ?"], [resolved]
    if level:
        where.append("fw_level = ?");  params.append(level)
    if camera:
        where.append("camera_id = ?"); params.append(camera)

    sql = f"""
        SELECT id, received_at, camera_id, fw_level, fw_reason,
               measurement, scenario_name, scenario_type, dwell_sec,
               site, area, snapshot_id, resolved, resolved_at
        FROM events
        WHERE {' AND '.join(where)}
        ORDER BY id DESC LIMIT ?
    """
    params.append(min(limit, 500))
    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ── Query: single event ───────────────────────────────────────────────────────
@app.get("/api/events/{event_id}")
def get_event(event_id: int, _auth = Depends(verify_token)):
    with get_db() as db:
        row = db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Not found")
    return dict(row)


# ── Resolve an event ──────────────────────────────────────────────────────────
@app.patch("/api/events/{event_id}/resolve")
def resolve_event(event_id: int, _auth = Depends(verify_token)):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute("UPDATE events SET resolved=1, resolved_at=? WHERE id=?", (now, event_id))
    return {"ok": True}


# ── Snapshot fetch ────────────────────────────────────────────────────────────
@app.get("/api/snapshots/{snap_id}")
def get_snapshot(snap_id: str, _auth = Depends(verify_token)):
    with get_db() as db:
        row = db.execute("SELECT data FROM snapshots WHERE id=?", (snap_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Snapshot not found")
    return Response(content=bytes(row["data"]), media_type="image/jpeg")


# ── Stats summary ─────────────────────────────────────────────────────────────
@app.get("/api/stats")
def get_stats(_auth = Depends(verify_token)):
    with get_db() as db:
        total     = db.execute("SELECT COUNT(*) FROM events WHERE resolved=0").fetchone()[0]
        escalate  = db.execute("SELECT COUNT(*) FROM events WHERE fw_level='ESCALATE' AND resolved=0").fetchone()[0]
        challenge = db.execute("SELECT COUNT(*) FROM events WHERE fw_level='CHALLENGE' AND resolved=0").fetchone()[0]
        observe   = db.execute("SELECT COUNT(*) FROM events WHERE fw_level='OBSERVE' AND resolved=0").fetchone()[0]
        cameras   = db.execute("SELECT COUNT(DISTINCT camera_id) FROM events WHERE resolved=0").fetchone()[0]
    return {
        "open_total":     total,
        "escalate":       escalate,
        "challenge":      challenge,
        "observe":        observe,
        "active_cameras": cameras,
    }
