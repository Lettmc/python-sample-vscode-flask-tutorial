"""
FleetWatch AI - Reasoning Council
=================================
A multi-model "council" that turns one camera event into a single, high-trust
operator verdict. Cloud-based (needs internet); the camera (via FixedIT) pushes
events here and gets back a judged result.

The council has FOUR specialised seats plus a deterministic gatekeeper. Each
seat is a DIFFERENT model chosen for what it's best at, and every seat can be
turned off with one env flag (data-residency / cost control).

  GATEKEEPER  (rule-based, free, instant)
      classify_severity() in detection_reasoning.py decides which events are
      even worth spending model tokens on. IGNORE never reaches the council.

  EYES        (Gemini, multimodal)
      Looks at the actual frame and says what is visually present. This is the
      capability ElectricEye leans on. Vision-first.

  ANALYST     (Llama, deep reasoning)
      Reasons over the structured metadata + the EYES description to score
      threat and intent. Text reasoning, cheap, strong.

  AGENT       (Hermes, agentic)
      Decides the RESPONSE: notify / talk-down / PTZ / escalate / dismiss.
      Hermes is tuned for tool-use and decisive action.

  NARRATOR    (synthesis)
      Fuses everything into ONE operator-ready sentence + a recommended action.

Everything routes through OpenRouter (one key, many models) so swapping a seat
is a slug change. Gemini can optionally use a direct Google key instead.

Env vars
--------
    OPENROUTER_API_KEY        single key for all seats via OpenRouter

    COUNCIL_EYES_MODEL        default google/gemini-2.0-flash-001
    COUNCIL_ANALYST_MODEL     default meta-llama/llama-4-maverick
    COUNCIL_AGENT_MODEL       default nousresearch/hermes-3-llama-3.1-70b
    COUNCIL_NARRATOR_MODEL    default openai/gpt-4.1-mini

    COUNCIL_EYES_ENABLED      "1"/"0"  (per-seat kill switch)
    COUNCIL_ANALYST_ENABLED   "1"/"0"
    COUNCIL_AGENT_ENABLED     "1"/"0"
    COUNCIL_NARRATOR_ENABLED  "1"/"0"

    GEMINI_DIRECT_KEY         optional: use Google's API directly for EYES
"""

import os
import json
import time
import base64
import requests

OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# ── Seat configuration (model + on/off) ──────────────────────────────────────
SEATS = {
    "eyes": {
        "model":   os.environ.get("COUNCIL_EYES_MODEL", "google/gemini-2.0-flash-001"),
        "enabled": os.environ.get("COUNCIL_EYES_ENABLED", "1") == "1",
    },
    "analyst": {
        "model":   os.environ.get("COUNCIL_ANALYST_MODEL", "meta-llama/llama-4-maverick"),
        "enabled": os.environ.get("COUNCIL_ANALYST_ENABLED", "1") == "1",
    },
    "agent": {
        "model":   os.environ.get("COUNCIL_AGENT_MODEL", "nousresearch/hermes-3-llama-3.1-70b"),
        "enabled": os.environ.get("COUNCIL_AGENT_ENABLED", "1") == "1",
    },
    "narrator": {
        "model":   os.environ.get("COUNCIL_NARRATOR_MODEL", "openai/gpt-4.1-mini"),
        "enabled": os.environ.get("COUNCIL_NARRATOR_ENABLED", "1") == "1",
    },
}

GEMINI_DIRECT_KEY = os.environ.get("GEMINI_DIRECT_KEY", "")

ALLOWED_ACTIONS = ["dismiss", "notify", "talk-down", "ptz-track", "escalate"]


# ── Low-level OpenRouter call ─────────────────────────────────────────────────
def _openrouter(model, messages, max_tokens=300, json_mode=False):
    payload = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    resp = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}",
                 "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _image_content(image_bytes):
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return {"type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}


# ── SEAT 1: EYES (vision) ─────────────────────────────────────────────────────
def seat_eyes(image_bytes, detections, site_name):
    labels = ", ".join(sorted({d["label"] for d in detections})) or "activity"
    prompt = (
        f"You are the visual analyst for a security system at {site_name}. "
        f"Sensors flagged: {labels}. In 1-2 factual sentences, describe ONLY "
        f"what is visually present in this frame. No speculation."
    )
    content = [{"type": "text", "text": prompt}, _image_content(image_bytes)]
    return _openrouter(SEATS["eyes"]["model"],
                       [{"role": "user", "content": content}], max_tokens=150)


# ── SEAT 2: ANALYST (threat reasoning) ───────────────────────────────────────
def seat_analyst(event_context, eyes_description):
    prompt = (
        "You are a security threat analyst. Given the structured event data and "
        "the visual description, return STRICT JSON with keys: "
        '"threat_score" (0-100 int), "intent" (short phrase), "reasoning" '
        "(one sentence). Be conservative; routine activity scores low.\n\n"
        f"EVENT DATA:\n{json.dumps(event_context, indent=2)}\n\n"
        f"VISUAL DESCRIPTION:\n{eyes_description}"
    )
    raw = _openrouter(SEATS["analyst"]["model"],
                      [{"role": "user", "content": prompt}],
                      max_tokens=200, json_mode=True)
    try:
        return json.loads(raw)
    except Exception:
        return {"threat_score": 50, "intent": "unknown",
                "reasoning": raw[:200]}


# ── SEAT 3: AGENT (action decision) ──────────────────────────────────────────
def seat_agent(event_context, analyst_result):
    prompt = (
        "You are the response agent for a security operations system. Choose ONE "
        f"action from this exact list: {ALLOWED_ACTIONS}. Return STRICT JSON with "
        'keys: "action" (one of the list), "confidence" (0-100 int), '
        '"justification" (one sentence). Reserve "escalate"/"talk-down" for '
        "genuine threats; use "
        '"dismiss" for clear false alarms.\n\n'
        f"EVENT:\n{json.dumps(event_context)}\n\n"
        f"ANALYST:\n{json.dumps(analyst_result)}"
    )
    raw = _openrouter(SEATS["agent"]["model"],
                      [{"role": "user", "content": prompt}],
                      max_tokens=160, json_mode=True)
    try:
        result = json.loads(raw)
        if result.get("action") not in ALLOWED_ACTIONS:
            result["action"] = "notify"
        return result
    except Exception:
        return {"action": "notify", "confidence": 50, "justification": raw[:200]}


# ── SEAT 4: NARRATOR (final synthesis) ───────────────────────────────────────
def seat_narrator(eyes_description, analyst_result, agent_result, site_name):
    prompt = (
        f"Write ONE crisp operator alert sentence for {site_name}, combining the "
        "visual facts and the threat assessment. No preamble. Then on a new line "
        'write "ACTION: <action>".\n\n'
        f"VISUAL: {eyes_description}\n"
        f"ANALYSIS: {json.dumps(analyst_result)}\n"
        f"DECISION: {json.dumps(agent_result)}"
    )
    return _openrouter(SEATS["narrator"]["model"],
                       [{"role": "user", "content": prompt}], max_tokens=120)


# ── Severity fusion: rule gate + analyst threat score ────────────────────────
def fuse_severity(rule_severity, threat_score):
    """Combine the deterministic rule verdict with the analyst's score."""
    if rule_severity == "HIGH" or threat_score >= 70:
        return "HIGH", "ESCALATE"
    if rule_severity == "LOW" or threat_score >= 35:
        return "LOW", "CHALLENGE"
    return "IGNORE", "OBSERVE"


# ── Orchestrator ─────────────────────────────────────────────────────────────
def convene(image_bytes, detections, event_context, rule_severity="LOW",
            site_name="site"):
    """
    Run the full council on one event. Returns a verdict dict. Each seat is
    optional; if a seat is disabled or errors, the council degrades gracefully.
    """
    t0 = time.time()
    verdict = {
        "site": site_name,
        "rule_severity": rule_severity,
        "seats_used": [],
        "errors": {},
        "latency_ms": {},
    }

    # SEAT 1 - EYES
    eyes_desc = ""
    if SEATS["eyes"]["enabled"] and image_bytes:
        try:
            s = time.time()
            eyes_desc = seat_eyes(image_bytes, detections, site_name)
            verdict["latency_ms"]["eyes"] = int((time.time() - s) * 1000)
            verdict["seats_used"].append("eyes")
        except Exception as e:
            verdict["errors"]["eyes"] = str(e)
    verdict["visual_description"] = eyes_desc

    # SEAT 2 - ANALYST
    analyst = {"threat_score": 50, "intent": "unknown", "reasoning": ""}
    if SEATS["analyst"]["enabled"]:
        try:
            s = time.time()
            analyst = seat_analyst(event_context, eyes_desc)
            verdict["latency_ms"]["analyst"] = int((time.time() - s) * 1000)
            verdict["seats_used"].append("analyst")
        except Exception as e:
            verdict["errors"]["analyst"] = str(e)
    verdict["analyst"] = analyst

    # Fuse severity now (so AGENT/NARRATOR see the final call)
    threat_score = int(analyst.get("threat_score", 50))
    severity, operator_level = fuse_severity(rule_severity, threat_score)
    verdict["severity"] = severity
    verdict["operator_level"] = operator_level
    verdict["threat_score"] = threat_score

    # SEAT 3 - AGENT
    agent = {"action": "notify", "confidence": 50, "justification": ""}
    if SEATS["agent"]["enabled"] and severity != "IGNORE":
        try:
            s = time.time()
            agent = seat_agent(event_context, analyst)
            verdict["latency_ms"]["agent"] = int((time.time() - s) * 1000)
            verdict["seats_used"].append("agent")
        except Exception as e:
            verdict["errors"]["agent"] = str(e)
    verdict["agent"] = agent
    verdict["recommended_action"] = agent.get("action", "notify")

    # SEAT 4 - NARRATOR
    narrative = eyes_desc or "Security event detected."
    if SEATS["narrator"]["enabled"] and severity != "IGNORE":
        try:
            s = time.time()
            narrative = seat_narrator(eyes_desc, analyst, agent, site_name)
            verdict["latency_ms"]["narrator"] = int((time.time() - s) * 1000)
            verdict["seats_used"].append("narrator")
        except Exception as e:
            verdict["errors"]["narrator"] = str(e)
    verdict["narrative"] = narrative

    verdict["total_latency_ms"] = int((time.time() - t0) * 1000)
    return verdict


# ── Multi-Candidate Descriptions ─────────────────────────────────────────────
_CANDIDATE_PERSPECTIVES = [
    {
        "model":   "google/gemini-2.0-flash-001",
        "persona": "You are a security analyst reviewing camera footage. Write ONE factual sentence "
                   "describing the threat or suspicious activity visible in this image. "
                   "Be specific about objects, actions, and positions.",
    },
    {
        "model":   "meta-llama/llama-4-maverick",
        "persona": "You are a court-ready forensic analyst. Write ONE precise legal-quality sentence "
                   "describing exactly what is visible in this security camera image. "
                   "Focus on observable facts only.",
    },
    {
        "model":   "openai/gpt-4.1-mini",
        "persona": "You are a 911 dispatcher writing a CAD entry. In ONE urgent, clear sentence "
                   "describe the threat for emergency responders. Include object type, "
                   "person description, and location in frame.",
    },
]


def _candidate_call(model, persona, image_bytes, labels, event_context, site_name):
    prompt = (
        f"{persona} Site: {site_name}. Detected: {labels}. "
        f"Context: {json.dumps(event_context, default=str)}"
    )
    content = [{"type": "text", "text": prompt}]
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        content.append({"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    return _openrouter(model, [{"role": "user", "content": content}], max_tokens=100)


def generate_candidates(image_bytes, detections, event_context,
                        site_name="site", n=3) -> tuple:
    """
    Generate N AI description candidates from different model perspectives.
    The Narrator seat then selects the best fit.

    Returns: (best_text: str | None, candidates: list[dict])
    """
    labels = ", ".join(sorted({d["label"] for d in detections})) or "unspecified activity"
    perspectives = _CANDIDATE_PERSPECTIVES[:n]
    candidates = []
    for p in perspectives:
        try:
            text = _candidate_call(
                p["model"], p["persona"], image_bytes, labels, event_context, site_name
            )
            candidates.append({
                "model":       p["model"].split("/")[-1],
                "full_model":  p["model"],
                "persona":     p["persona"][:60] + "…",
                "text":        text,
                "error":       None,
            })
        except Exception as e:
            candidates.append({
                "model":      p["model"].split("/")[-1],
                "full_model": p["model"],
                "persona":    p["persona"][:60] + "…",
                "text":       None,
                "error":      str(e),
            })

    valid = [c for c in candidates if c["text"]]
    if not valid:
        return None, candidates
    if len(valid) == 1:
        return valid[0]["text"], candidates

    # Narrator picks the best
    selection_prompt = (
        f"You are choosing the BEST security alert description for an operator at {site_name}.\n"
        f"Context: {json.dumps(event_context, default=str)}\n\n"
        f"Candidates:\n"
        + "\n".join(f"{i+1}. {c['text']}" for i, c in enumerate(valid))
        + "\n\nReply with ONLY the number (1, 2, or 3) of the most accurate, "
          "clear, and actionable description."
    )
    try:
        raw   = _openrouter(SEATS["narrator"]["model"],
                            [{"role": "user", "content": selection_prompt}],
                            max_tokens=5).strip()
        idx   = int(raw.split()[0]) - 1
        best  = valid[max(0, min(idx, len(valid) - 1))]["text"]
        candidates[idx]["selected"] = True
    except Exception:
        best  = valid[0]["text"]
        if valid:
            candidates[0]["selected"] = True

    return best, candidates


if __name__ == "__main__":
    # Smoke test (no real image / keys needed to see the structure).
    demo_ctx = {"camera_id": "P3268-LVE-01", "zone": "perimeter",
                "hour_of_day": 2, "class": "person", "dwell_sec": 45}
    print(json.dumps(convene(b"", [{"label": "intruder", "confidence": 0.9}],
                             demo_ctx, rule_severity="HIGH",
                             site_name="Home Test Lab"), indent=2))
