# FleetWatch AI — Build Playbook

**The straightforward, in-order guide.** Follow the phases top to bottom. Don't start a phase until the previous one's "Done when" box is checked. The golden rule: **prove each link works before adding the next.**

---

## What you already have

Files built across our sessions (keep them together in a project folder):

| File | What it is |
|---|---|
| `backend/main.py` | Your cloud backend: receives alerts + clips, calls Roboflow, sends Teams alerts |
| `detection_reasoning.py` | Two-tier AI: Roboflow detection + OpenRouter reasoning (American, not Gemini) |
| `visual_metadata.star` | Parses AXIS Scene Metadata into clean, enriched object events |
| `fixedit_visual_config.toml` | FixedIT config that feeds Scene Metadata + Roboflow into the parser |
| `alert_logic.star` | Severity classifier (HIGH / LOW / IGNORE) |

The two-tier idea to hold in your head the whole way through: **detection is free on the camera; judgment is the product.** Spend your effort on the decision/fusion logic, not on re-inventing object detection.

---

## Phase 0 — Foundations (before you touch anything)

**Goal:** a secured camera and all the accounts you'll need.

**Secure the camera first** (never build on an unlocked device):
1. Update AXIS OS to the latest LTS firmware.
2. Set a unique, strong admin password.
3. HTTPS only; disable the plain-HTTP virtual host.
4. Keep SSH and anonymous access disabled.
5. Firewall: set **Default Policy = DROP**, then add Allow rules for only 443 (HTTPS, from your admin IP) and 554 (RTSP, from your backend IP). **Use "Test rules" before "Apply rules"** so you don't lock yourself out.
6. Confirm the secure-element keystore is selected (FIPS 140-3 Level 3).

**Create accounts:**
7. Roboflow (object-detection workspace).
8. OpenRouter (one API key for many American AI models).
9. A cloud host for the backend — Render or Railway (free tier to start).
10. Microsoft Teams workspace + a channel for HIGH alerts, with an incoming webhook URL.

**Pick your pilot:** ONE camera, ONE site, ONE use case (e.g. "person at the perimeter after 8pm"). Resist the urge to do more.

> **Done when:** camera is hardened, you can log into all four accounts, and you have a Teams webhook URL saved in a password manager.

---

## Phase 1 — Prove the alert spine (fake data, no camera, no AI)

**Goal:** a fake HIGH event makes a real alert card appear in Teams. This is the hardest and most important 20%.

1. Deploy `backend/main.py` to Render/Railway.
2. Put your secrets in environment variables (never in code): `TEAMS_WEBHOOK_URL`, `API_TOKEN`.
3. Using Postman or `curl`, POST a fake HIGH alert to `/api/alerts`.
4. Watch the card appear in your Teams channel.

> **Done when:** you send a fake alert and a formatted card shows up in Teams. Celebrate — the whole notification nervous system now works.

---

## Phase 2 — Add the decision brain (still fake data)

**Goal:** the severity logic correctly sorts events.

1. Take `alert_logic.star` and feed it a fake detection (e.g. a "person" at "perimeter" at "2am").
2. Confirm it returns HIGH with a clean description.
3. Feed it a daytime sidewalk person — confirm it returns LOW and stays quiet.
4. Tune the thresholds until its judgment matches yours.

> **Done when:** the brain reliably outputs HIGH / LOW / IGNORE for the cases you care about.

---

## Phase 3 — Connect one real camera (video + metadata)

**Goal:** real detections flow from the camera into your system.

**Video clips (push architecture):**
1. Install and mount an SD card; enable recording/retention.
2. Apps → AXIS Object Analytics → create a scenario (Human/Vehicle), set include areas and lines. (Remember: a human's detection point is the **feet**, a vehicle's is the **center** — draw zones accordingly.)
3. System → Events → add a recording rule (prebuffer 3–5s, postbuffer 15–20s, SD card).
4. System → Events → Recipients → add an HTTPS recipient pointing at your backend's `/api/clips?camera_id=...&token=...`.
5. Add a rule: on the AOA scenario, "Send video clip through HTTPS" to that recipient.

**Scene Metadata (the perception stream):**
6. System → MQTT → connect the camera's MQTT client to a local broker.
7. Create an Analytics MQTT publisher for data source `com.axis.analytics_scene_description.v0.beta#1` (frame-by-frame) to topic `fleetwatch/scene/cam01`.
8. **Capture one real message** with `mosquitto_sub -t 'fleetwatch/scene/#' -v` and confirm the field names.

**FixedIT parser:**
9. Install the FixedIT Data Agent ACAP on the camera.
10. Upload `fixedit_visual_config.toml` and `visual_metadata.star`.
11. Tune the `ZONES`, `FOCUS_X/Y`, and `MIN_SCORE` at the top of the `.star` file to your scene.

> **Done when:** you walk in front of the camera and see (a) a clip arrive at your backend, and (b) enriched `visual_object` events on the `fleetwatch/visual/...` topic with zone, dwell, and direction filled in.

---

## Phase 4 — Add your own AI (custom detection + reasoning)

**Goal:** real clips analyzed by a model you own.

**Train the detector (Roboflow):**
1. Create an Object Detection project. **Only label what AOA can't see** — hard-hat-off, no-vest, fire, smoke, open-gate. (People/vehicles stay free on the camera.)
2. Upload 100–300 images with real variety: day, night, IR, rain, angles from your trailers.
3. Annotate (use Auto Label / Label Assist to speed it up).
4. Generate a version: resize to 640, add brightness/blur/noise augmentation.
5. Train (YOLO26 for edge, or NAS to auto-pick). Grab your `project/version` model ID.
6. Deploy: hosted API to start; on-device (Roboflow Inference in Docker) later for low cost/latency.

**Wire the reasoning layer (OpenRouter):**
7. Set env vars for `detection_reasoning.py`: `ROBOFLOW_API_KEY`, `ROBOFLOW_MODEL_ID`, `OPENROUTER_API_KEY`, `REASONING_MODEL`.
8. Pick an American, vision-capable model on openrouter.ai/models (start on a free one; swap to a cheap paid one for production). Never pick a `google/` model.
9. Connect `detection_reasoning.py` into the backend so a clip → Roboflow detection → severity → (only if HIGH) one-sentence VLM description → Teams.

> **Done when:** a real event triggers a real Teams alert that includes an AI-written description, end to end, on one camera.

---

## Phase 5 — Add ears (audio)

**Goal:** the system can hear, not just see.

1. Pair an Axis network microphone to the camera (the P1475-LE has no built-in mic).
2. Install an audio-analytics ACAP on the edge:
   - **AXIS Audio Analytics** (often free) — glass break, scream, shout, speech, SPL/volume spikes.
   - Optional paid: **JALUD SED** or **Sound Intelligence** — gunshot, aggression, drone.
3. Keep audio as **metadata only — do not record audio** (cheaper, and avoids two-party-consent legal issues; confirm with counsel before ever recording).
4. Route the audio events into FixedIT the same way as visual, publishing to an audio topic (e.g. `fleetwatch/audio/cam01`).

> **Done when:** an audio event (e.g. a clap simulating glass break) appears on your audio topic alongside the visual events.

---

## Phase 6 — Fusion + anomaly detection (the real moat)

**Goal:** smart alerts that don't cry wolf.

**Stage 1 — Fusion rules (start here):**
1. Build a stage that subscribes to BOTH `fleetwatch/visual/...` and `fleetwatch/audio/...`.
2. Write multimodal rules that require agreement: glass-break sound **+** person at window within 10s = HIGH; aggression sound **+** two people in close fast contact = HIGH. One signal alone = log only.

**Stage 2 — Scene baselines (next):**
3. Store every event as a structured feature vector (objects, sounds, SPL, time, zone, outcome).
4. Per camera + time-of-day, learn the normal range (mean + std dev) of object counts, SPL, event frequency, dwell.
5. Flag readings several standard deviations outside that scene's normal band.

**Stage 3 — ML anomaly (later, only after you have labeled data):**
6. Once you have months of labeled events, train an autoencoder / isolation forest on the per-scene vectors.

**The feedback loop that makes it all improve:**
7. Add a one-click "false alarm / real threat" button to every alert.
8. Every operator decision labels that event vector — that growing labeled dataset is the thing competitors can't copy.

> **Done when:** a single-signal noise event is correctly suppressed, and a corroborated audio+visual event correctly fires HIGH.

---

## Phase 7 — Product & business

**Goal:** turn the pipeline into something you can sell.

1. Store all events in PostgreSQL (unlocks search, reporting, fleet analytics, natural-language search later).
2. Build the operator dashboard in your Navy theme: event queue, severity badges, clip review, the false-alarm button.
3. Licensing: issue one signed token (JWT) per camera, validated by the backend; the active-camera count is your invoice.
4. Pricing — flat, undercutting both competitors:
   - *Detect* tier ($15–19): edge detection + filtered alerts, unlimited events.
   - *Command* tier ($35–45): + VLM reasoning, fusion, dashboard, deterrence.
5. Scale: repeat Phases 3–5 per new camera/site; the rules and models are reusable.

> **Done when:** a customer can see their alerts in your dashboard, you can bill per camera, and adding a new camera is a repeatable checklist.

---

## Always-on (ongoing, not a phase)

- **Security:** patch firmware, rotate credentials, watch logs for failed logins / config changes.
- **False-positive review:** weekly, look at what fired wrong and tune rules/zones.
- **Retraining:** feed labeled events back into Roboflow and your baselines monthly.
- **Power awareness (for solar trailers):** add normal / conserve / critical-battery modes that throttle AI as the battery drains.

---

## The one rule, again

Each phase produces something you can test on its own. If a phase breaks, the problem is *in that phase*, not buried in five new things. Build slow, prove each link, and the whole chain stays debuggable.
