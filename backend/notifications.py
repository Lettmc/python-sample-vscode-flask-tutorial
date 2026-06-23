"""
FleetWatch AI — Multi-Channel Notification Router
=================================================
Routes high-severity events to any combination of:
  teams   — Microsoft Teams incoming webhook (existing)
  slack   — Slack incoming webhook or Bot API
  sms     — Twilio SMS
  voice   — Twilio automated voice call
  vms     — Generic VMS webhook (Milestone, Genetec, Avigilon, Hanwha)
  emergency — 911 dispatch via RapidSOS (requires signed contract)

Env vars
--------
  NOTIFICATION_CHANNELS       comma-sep: teams,slack,sms,voice,vms   (default: teams)
  TEAMS_WEBHOOK_URL           existing Teams webhook
  SLACK_WEBHOOK_URL           Slack incoming webhook URL
  SLACK_BOT_TOKEN             Slack Bot OAuth token (xoxb-...)
  SLACK_ALERT_CHANNEL         default #fleetwatch-alerts
  TWILIO_ACCOUNT_SID          Twilio SID
  TWILIO_AUTH_TOKEN           Twilio auth token
  TWILIO_FROM_NUMBER          Twilio phone number (+12135551234)
  ALERT_PHONE_NUMBERS         comma-sep E.164 numbers (+12135551234,+19085559876)
  VMS_WEBHOOK_URL             VMS alarm webhook endpoint
  RAPIDSOS_API_KEY            RapidSOS Bearer token (requires contract)
  RAPIDSOS_ORG_ID             RapidSOS org identifier
  FW_CLOUD_URL                used to construct snapshot URLs for Teams/Slack cards
"""

import os
import json
import logging
import requests

log = logging.getLogger("notifications")

TEAMS_WEBHOOK_URL    = os.environ.get("TEAMS_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL    = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_BOT_TOKEN      = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_ALERT_CHANNEL  = os.environ.get("SLACK_ALERT_CHANNEL", "#fleetwatch-alerts")
TWILIO_ACCOUNT_SID   = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN    = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER   = os.environ.get("TWILIO_FROM_NUMBER", "")
ALERT_PHONE_NUMBERS  = [n.strip() for n in
                        os.environ.get("ALERT_PHONE_NUMBERS", "").split(",") if n.strip()]
VMS_WEBHOOK_URL      = os.environ.get("VMS_WEBHOOK_URL", "")
RAPIDSOS_API_KEY     = os.environ.get("RAPIDSOS_API_KEY", "")
RAPIDSOS_ORG_ID      = os.environ.get("RAPIDSOS_ORG_ID", "")
FW_CLOUD_URL         = os.environ.get("FW_CLOUD_URL", "")
NOTIFICATION_CHANNELS = [c.strip() for c in
                          os.environ.get("NOTIFICATION_CHANNELS", "teams").split(",")
                          if c.strip()]


# ── Orchestrator ──────────────────────────────────────────────────────────────
def notify_all(event: dict, force_channels=None) -> dict:
    """Route an event to all configured channels. Returns per-channel results."""
    channels = force_channels or NOTIFICATION_CHANNELS
    results = {}
    for ch in channels:
        try:
            if   ch == "teams":     results["teams"]     = _teams(event)
            elif ch == "slack":     results["slack"]     = _slack(event)
            elif ch == "sms":       results["sms"]       = _sms(event)
            elif ch == "voice":     results["voice"]     = _voice(event)
            elif ch == "vms":       results["vms"]       = _vms_webhook(event)
            elif ch == "emergency": results["emergency"] = _rapidsos(event)
            else:
                results[ch] = {"skipped": f"unknown channel: {ch}"}
        except Exception as exc:
            log.error("notification channel %s failed: %s", ch, exc)
            results[ch] = {"error": str(exc)}
    return results


def get_channel_status() -> dict:
    """Returns which channels are configured (safe — no secrets exposed)."""
    return {
        "teams":     bool(TEAMS_WEBHOOK_URL),
        "slack":     bool(SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN),
        "sms":       bool(TWILIO_ACCOUNT_SID and ALERT_PHONE_NUMBERS),
        "voice":     bool(TWILIO_ACCOUNT_SID and ALERT_PHONE_NUMBERS),
        "vms":       bool(VMS_WEBHOOK_URL),
        "emergency": bool(RAPIDSOS_API_KEY),
        "channels":  NOTIFICATION_CHANNELS,
    }


# ── Teams ─────────────────────────────────────────────────────────────────────
def _teams(event: dict) -> dict:
    if not TEAMS_WEBHOOK_URL:
        return {"skipped": "TEAMS_WEBHOOK_URL not set"}
    sev   = event.get("severity", "LOW")
    color = {"HIGH": "FF0000", "LOW": "F97316"}.get(sev, "3B82F6")
    snap_url = _snapshot_url(event)
    sections = [{
        "activityTitle":    f"🚨 FleetWatch AI — {event.get('operator_level','ALERT')} ({sev})",
        "activitySubtitle": (f"{event.get('site','?')} · Camera: {event.get('camera_id','?')} "
                             f"· Zone: {event.get('zone','?')}"),
        "text": event.get("narrative") or event.get("visual_description") or "Security event detected.",
        "facts": [
            {"name": "Threat Score",  "value": f"{event.get('threat_score',0)}/100"},
            {"name": "AI Action",     "value": event.get("recommended_action", "—")},
            {"name": "Class",         "value": event.get("detected_class", "—")},
            {"name": "Seats Used",    "value": ", ".join(event.get("seats_used", []) or [])},
            {"name": "Time",          "value": event.get("received_at", "—")},
        ],
    }]
    if snap_url:
        sections.append({"images": [{"image": snap_url}]})
    card = {
        "@type": "MessageCard", "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": f"FleetWatch {sev} — {event.get('camera_id','?')}",
        "sections": sections,
        "potentialAction": [{
            "@type": "OpenUri", "name": "Open FleetWatch",
            "targets": [{"os": "default", "uri": FW_CLOUD_URL or "#"}]
        }]
    }
    r = requests.post(TEAMS_WEBHOOK_URL, json=card, timeout=12)
    return {"status": r.status_code}


# ── Slack ─────────────────────────────────────────────────────────────────────
def _slack(event: dict) -> dict:
    if not (SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL):
        return {"skipped": "no Slack config"}
    sev    = event.get("severity", "LOW")
    emoji  = {"HIGH": ":rotating_light:", "LOW": ":warning:"}.get(sev, ":bell:")
    color  = {"HIGH": "#ef4444", "LOW": "#f97316"}.get(sev, "#3b82f6")
    text   = event.get("narrative") or event.get("visual_description") or "Security event."
    snap_url = _snapshot_url(event)

    blocks = [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"{emoji} FleetWatch AI — {event.get('operator_level','ALERT')}"}},
        {"type": "section",
         "text": {"type": "mrkdwn", "text": text}},
        {"type": "section",
         "fields": [
             {"type": "mrkdwn", "text": f"*Camera:*\n{event.get('camera_id','?')}"},
             {"type": "mrkdwn", "text": f"*Zone:*\n{event.get('zone','?')}"},
             {"type": "mrkdwn", "text": f"*Threat Score:*\n{event.get('threat_score',0)}/100"},
             {"type": "mrkdwn", "text": f"*Action:*\n{event.get('recommended_action','?')}"},
         ]},
    ]
    if snap_url:
        blocks.append({
            "type": "image",
            "image_url": snap_url,
            "alt_text": f"Snapshot from {event.get('camera_id','camera')}",
        })
    actions = [
        {"type": "button", "text": {"type": "plain_text", "text": "Resolve"},
         "style": "primary", "value": f"resolve_{event.get('id','')}"},
        {"type": "button", "text": {"type": "plain_text", "text": "False Alarm"},
         "value": f"false_alarm_{event.get('id','')}"},
    ]
    if FW_CLOUD_URL:
        actions.insert(0, {
            "type": "button", "text": {"type": "plain_text", "text": "View in FleetWatch"},
            "url": FW_CLOUD_URL
        })
    blocks.append({"type": "actions", "elements": actions})

    payload = {
        "channel": SLACK_ALERT_CHANNEL,
        "username": "FleetWatch AI",
        "icon_emoji": ":eye:",
        "attachments": [{"color": color, "blocks": blocks}],
    }

    if SLACK_BOT_TOKEN:
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                     "Content-Type": "application/json"},
            json=payload, timeout=12,
        )
        return {"status": r.status_code, "ok": r.json().get("ok")}
    else:
        simple = {
            "text": f"{emoji} *FleetWatch {sev}* | {event.get('camera_id','?')} | {text[:200]}",
        }
        r = requests.post(SLACK_WEBHOOK_URL, json=simple, timeout=12)
        return {"status": r.status_code}


# ── Twilio SMS ─────────────────────────────────────────────────────────────────
def _sms(event: dict) -> list:
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
                TWILIO_FROM_NUMBER, ALERT_PHONE_NUMBERS]):
        return [{"skipped": "Twilio not fully configured"}]
    sev  = event.get("severity", "LOW")
    body = (
        f"[FleetWatch {sev}] {event.get('operator_level','')} "
        f"at {event.get('site','?')} | "
        f"Cam:{event.get('camera_id','?')} Zone:{event.get('zone','?')} "
        f"Score:{event.get('threat_score',0)}/100 | "
        f"{(event.get('narrative') or '')[:120]}"
    )
    results = []
    for number in ALERT_PHONE_NUMBERS:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={"From": TWILIO_FROM_NUMBER, "To": number, "Body": body},
            timeout=15,
        )
        results.append({"to": number, "status": r.status_code,
                        "sid": r.json().get("sid")})
    return results


# ── Twilio Voice Call ─────────────────────────────────────────────────────────
def _voice(event: dict) -> list:
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
                TWILIO_FROM_NUMBER, ALERT_PHONE_NUMBERS]):
        return [{"skipped": "Twilio not fully configured"}]
    sev      = event.get("severity", "LOW")
    site     = event.get("site", "your site")
    cam      = event.get("camera_id", "unknown camera")
    zone     = event.get("zone", "unknown zone")
    score    = event.get("threat_score", 0)
    action   = event.get("recommended_action", "review")
    narr     = (event.get("narrative") or "A security event has been detected.")[:250]
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        '<Say voice="Polly.Joanna" language="en-US">'
        f'  Fleet Watch Alert. {sev} severity event at {site}. '
        f'  Camera {cam}, zone {zone}. '
        f'  Threat score: {score} out of 100. '
        f'  Recommended action: {action}. '
        f'  {narr} '
        '  Press 1 to acknowledge. Press 9 to request emergency dispatch.'
        '</Say>'
        '<Gather numDigits="1" timeout="10">'
        '  <Say voice="Polly.Joanna">Press 1 to acknowledge or 9 for emergency dispatch.</Say>'
        '</Gather>'
        '<Say voice="Polly.Joanna">No response received. Alert logged. Goodbye.</Say>'
        '</Response>'
    )
    results = []
    for number in ALERT_PHONE_NUMBERS:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls.json",
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={"From": TWILIO_FROM_NUMBER, "To": number, "Twiml": twiml},
            timeout=20,
        )
        results.append({"to": number, "status": r.status_code,
                        "sid": r.json().get("sid")})
    return results


# ── Generic VMS Webhook ────────────────────────────────────────────────────────
def _vms_webhook(event: dict) -> dict:
    """
    Sends a FleetWatch alarm event to any VMS that accepts webhook notifications.
    Tested shapes:
      Milestone XProtect — Analytics Events API  (port 9090 by default)
      Genetec Security Center — REST API  (requires GenetecConnect plugin)
      Avigilon Control Center — ACV Alarm API  (via MIP Plugin)
      Hanwha Wisenet WAVE / VMS — HTTP Event
    The VMS_WEBHOOK_URL must point to the alarm receiver endpoint.
    """
    if not VMS_WEBHOOK_URL:
        return {"skipped": "VMS_WEBHOOK_URL not set"}
    payload = {
        "source": "FleetWatch AI",
        "event_type": "security_alert",
        "severity":           event.get("severity"),
        "operator_level":     event.get("operator_level"),
        "camera_id":          event.get("camera_id"),
        "zone":               event.get("zone"),
        "site":               event.get("site"),
        "threat_score":       event.get("threat_score"),
        "narrative":          event.get("narrative"),
        "visual_description": event.get("visual_description"),
        "detected_class":     event.get("detected_class"),
        "recommended_action": event.get("recommended_action"),
        "bounding_boxes":     event.get("bounding_boxes", []),
        "seats_used":         event.get("seats_used", []),
        "snapshot_url":       _snapshot_url(event),
        "timestamp":          event.get("received_at"),
        "event_id":           event.get("id"),
    }
    r = requests.post(VMS_WEBHOOK_URL, json=payload, timeout=15)
    return {"status": r.status_code}


# ── RapidSOS Emergency Dispatch (911) ─────────────────────────────────────────
def _rapidsos(event: dict) -> dict:
    """
    Initiates a CAD (Computer-Aided Dispatch) message to the PSAP (911 center)
    serving the site's geographic location via the RapidSOS Emergency Data Platform.

    REQUIRES a signed agreement with RapidSOS (rapidsos.com).
    This is a real 911 trigger — only call for genuine emergencies.
    During testing, set RAPIDSOS_SANDBOX=1 to hit their sandbox environment.
    """
    if not RAPIDSOS_API_KEY:
        return {"skipped": "RapidSOS not configured — requires signed contract at rapidsos.com"}
    sandbox = os.environ.get("RAPIDSOS_SANDBOX", "0") == "1"
    base    = "https://sandbox-api.rapidsos.com" if sandbox else "https://api.rapidsos.com"
    headers = {
        "Authorization": f"Bearer {RAPIDSOS_API_KEY}",
        "Content-Type":  "application/json",
        "X-RapidSOS-Org": RAPIDSOS_ORG_ID,
    }
    payload = {
        "incident": {
            "type":     "security",
            "priority": "high" if event.get("severity") == "HIGH" else "medium",
            "location": {
                "name":      event.get("site", "Unknown"),
                "camera_id": event.get("camera_id"),
                "zone":      event.get("zone"),
            },
            "description": (
                event.get("narrative") or
                f"Security alert detected by FleetWatch AI at {event.get('site')}. "
                f"Camera {event.get('camera_id')}, zone {event.get('zone')}. "
                f"Threat score: {event.get('threat_score',0)}/100."
            ),
            "caller": {
                "organization": "FleetWatch AI",
                "contact":      event.get("site"),
            },
            "additional_data": {
                "threat_score":    event.get("threat_score"),
                "detected_class":  event.get("detected_class"),
                "ai_action":       event.get("recommended_action"),
                "bounding_boxes":  event.get("bounding_boxes", []),
                "snapshot_url":    _snapshot_url(event),
            },
        }
    }
    r = requests.post(f"{base}/v1/incidents", headers=headers, json=payload, timeout=20)
    return {
        "status":   r.status_code,
        "sandbox":  sandbox,
        "response": r.json() if r.ok else r.text[:300],
    }


# ── Helpers ────────────────────────────────────────────────────────────────────
def _snapshot_url(event: dict) -> str:
    snap_id = event.get("snapshot_id")
    token   = os.environ.get("FW_CLOUD_TOKEN", "")
    if snap_id and FW_CLOUD_URL:
        return f"{FW_CLOUD_URL}/api/snapshots/{snap_id}?token={token}"
    return ""
