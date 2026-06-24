"""
FleetWatch AI - detection + reasoning module
=============================================
Two-tier AI per the Build Playbook:

  TIER 1 (detection, runs often, ~free):
    - People / vehicles are already detected FREE on the camera's DLPU via
      AXIS Object Analytics. You do NOT call this module for those.
    - This module detects the CUSTOM hazards AOA can't see: hard-hat-off,
      no-vest, fire, smoke, open-gate, etc.
    - Detection provider is PLUGGABLE: Roboflow (default, per playbook) or
      Robovision. Swap with the DETECTION_PROVIDER env var - no code change.

  TIER 2 (reasoning, runs rarely, ~pennies):
    - An American vision-language model via OpenRouter writes one
      operator-ready sentence. Only called on HIGH events. Never Gemini.

Setup
-----
    pip install requests
    (Roboflow path also uses: pip install inference-sdk)

Environment variables (never hard-code keys):
    DETECTION_PROVIDER   = "roboflow" (default) | "robovision"

    # Roboflow
    ROBOFLOW_API_KEY     = your Roboflow key
    ROBOFLOW_MODEL_ID    = "fleetwatch-detect/1"
    ROBOFLOW_API_URL     = "https://detect.roboflow.com" | "http://localhost:9001"

    # Robovision
    ROBOVISION_API_KEY   = your Robovision key
    ROBOVISION_ENDPOINT  = your Robovision inference endpoint URL

    # Reasoning
    OPENROUTER_API_KEY   = your OpenRouter key
    REASONING_MODEL      = an American, vision-capable model slug
"""

import os
import base64
import requests

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
DETECTION_PROVIDER = os.environ.get("DETECTION_PROVIDER", "roboflow").lower()

ROBOFLOW_API_KEY  = os.environ.get("ROBOFLOW_API_KEY", "")
ROBOFLOW_MODEL_ID = os.environ.get("ROBOFLOW_MODEL_ID", "fleetwatch-detect/1")
ROBOFLOW_API_URL  = os.environ.get("ROBOFLOW_API_URL", "https://detect.roboflow.com")

ROBOVISION_API_KEY  = os.environ.get("ROBOVISION_API_KEY", "")
ROBOVISION_ENDPOINT = os.environ.get("ROBOVISION_ENDPOINT", "")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"

# Primary + fallback are BOTH American models. Change freely - no other code
# changes. OpenRouter tries the fallbacks if the primary is down.
REASONING_MODEL     = os.environ.get("REASONING_MODEL", "meta-llama/llama-4-scout")
REASONING_FALLBACKS = ["openai/gpt-4.1-mini"]

# Tune to your tolerance for noise vs missed events. Keep in sync with
# alert_logic.star on the camera.
MIN_CONFIDENCE       = 0.55
HIGH_SEVERITY_LABELS = {"hard-hat-off", "no-vest", "fire", "smoke",
                        "open-gate", "intruder", "weapon"}


# --------------------------------------------------------------------------
# TIER 1 - custom object detection (pluggable provider)
# --------------------------------------------------------------------------
def _detect_roboflow(image):
    """Roboflow hosted/edge inference. `image` = path, URL, ndarray, or PIL."""
    from inference_sdk import InferenceHTTPClient
    client = InferenceHTTPClient(api_url=ROBOFLOW_API_URL, api_key=ROBOFLOW_API_KEY)
    result = client.infer(image, model_id=ROBOFLOW_MODEL_ID)
    out = []
    for p in result.get("predictions", []):
        out.append({
            "label": p["class"],
            "confidence": round(float(p["confidence"]), 3),
            "x": p["x"], "y": p["y"], "w": p["width"], "h": p["height"],
        })
    return out


def _detect_robovision(image_bytes):
    """
    Robovision inference via REST. Robovision deployments expose a model
    endpoint that accepts an image and returns detections. The exact schema
    depends on YOUR deployed model, so confirm ROBOVISION_ENDPOINT and the
    response shape in your Robovision workspace before production.
    """
    if not ROBOVISION_ENDPOINT:
        raise RuntimeError("ROBOVISION_ENDPOINT not set")
    resp = requests.post(
        ROBOVISION_ENDPOINT,
        headers={"Authorization": f"Bearer {ROBOVISION_API_KEY}"},
        files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    out = []
    # Normalize common Robovision shapes -> our standard dict.
    for p in data.get("predictions", data.get("detections", [])):
        out.append({
            "label": p.get("label", p.get("class", "object")),
            "confidence": round(float(p.get("confidence", p.get("score", 0.0))), 3),
            "x": p.get("x", 0), "y": p.get("y", 0),
            "w": p.get("width", p.get("w", 0)), "h": p.get("height", p.get("h", 0)),
        })
    return out


def detect_objects(image, image_bytes=None):
    """Dispatch to the configured detection provider."""
    if DETECTION_PROVIDER == "robovision":
        if image_bytes is None and isinstance(image, str):
            with open(image, "rb") as f:
                image_bytes = f.read()
        return _detect_robovision(image_bytes)
    return _detect_roboflow(image)


# --------------------------------------------------------------------------
# Severity gate (mirrors alert_logic.star on the camera)
# --------------------------------------------------------------------------
def classify_severity(detections, zone="general", hour_of_day=12):
    """Returns HIGH / LOW / IGNORE for a frame's detections."""
    best = "IGNORE"
    for d in detections:
        if d["confidence"] < MIN_CONFIDENCE:
            continue
        label = d["label"]
        if label in HIGH_SEVERITY_LABELS:
            return "HIGH"
        if zone in ("restricted", "perimeter") or hour_of_day >= 20 or hour_of_day < 6:
            best = "HIGH"
        elif best != "HIGH":
            best = "LOW"
    return best


# --------------------------------------------------------------------------
# TIER 2 - reasoning / description (OpenRouter, American VLM)
# --------------------------------------------------------------------------
def describe_scene(image_bytes, detections, site_name="site"):
    """One operator-ready sentence. Call ONLY on HIGH events."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    labels = ", ".join(sorted({d["label"] for d in detections})) or "activity"
    prompt = (
        f"You are a security analyst. In ONE short, factual sentence, describe "
        f"what is happening in this {site_name} camera image. "
        f"Detected objects: {labels}. No preamble, no speculation."
    )
    payload = {
        "model": REASONING_MODEL,
        "models": REASONING_FALLBACKS,
        "max_tokens": 80,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
    }
    resp = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}",
                 "Content-Type": "application/json"},
        json=payload, timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# --------------------------------------------------------------------------
# Orchestrator - the full per-frame pipeline
# --------------------------------------------------------------------------
def process_frame(image_path, image_bytes, site_name="site",
                  camera_id="cam", zone="general", hour_of_day=12):
    """Detect -> score -> (only if HIGH) describe. Returns an event dict."""
    detections = detect_objects(image_path, image_bytes=image_bytes)
    severity = classify_severity(detections, zone=zone, hour_of_day=hour_of_day)

    description = None
    if severity == "HIGH" and detections:
        try:
            description = describe_scene(image_bytes, detections, site_name)
        except Exception as e:
            description = (f"HIGH event at {site_name} "
                           f"({', '.join(d['label'] for d in detections)})")
            print(f"[reasoning] VLM call failed, used fallback text: {e}")

    return {
        "camera_id": camera_id,
        "site_name": site_name,
        "severity": severity,
        "detections": detections,
        "description": description,
        "zone": zone,
        "provider": DETECTION_PROVIDER,
    }


if __name__ == "__main__":
    with open("test_frame.jpg", "rb") as f:
        raw = f.read()
    event = process_frame("test_frame.jpg", raw, site_name="Yard A",
                          camera_id="P3268-LVE-CAM01", zone="perimeter", hour_of_day=2)
    print(event)
