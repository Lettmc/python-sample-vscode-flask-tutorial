# FleetWatch AI — Master Knowledge Base
**Compiled from:** ElectricEye Push Architecture Guide, Axis Developer Reference (Mike Lett / June 2026), OpSignal UI Screenshots, Axis ACAP/AOA/VAPIX/Scene Metadata documentation  
**Last updated:** June 2026

---

## TABLE OF CONTENTS

1. [What FleetWatch AI Is](#1-what-fleetwatch-ai-is)
2. [OpSignal — Full Platform Intelligence](#2-opsignal--full-platform-intelligence)
3. [ElectricEye Push Architecture](#3-electriceye-push-architecture)
4. [AXIS Object Analytics (AOA) — Full Reference](#4-axis-object-analytics-aoa--full-reference)
5. [AXIS Scene Metadata — Full Reference](#5-axis-scene-metadata--full-reference)
6. [VAPIX API — Full Reference](#6-vapix-api--full-reference)
7. [ACAP SDK — Full API Reference](#7-acap-sdk--full-api-reference)
8. [DLPU / Computer Vision / AI at the Edge](#8-dlpu--computer-vision--ai-at-the-edge)
9. [Axis GitHub Repositories](#9-axis-github-repositories)
10. [ACAP Ideas — Future Apps to Build](#10-acap-ideas--future-apps-to-build)
11. [FleetWatch AI — Current ACAP Spec](#11-fleetwatch-ai--current-acap-spec)
12. [Event Taxonomy & Priority Model](#12-event-taxonomy--priority-model)
13. [Payload Schema Reference](#13-payload-schema-reference)
14. [AOA Counting Metadata Schemas (XML + JSON)](#14-aoa-counting-metadata-schemas-xml--json)
15. [Integration Platforms](#15-integration-platforms)

---

## 1. What FleetWatch AI Is

FleetWatch AI is a premium Axis ACAP (Camera Application Platform) that runs directly on Axis cameras. It provides:

- AI-powered scene intelligence with natural language descriptions
- 3-level event escalation model: **Observe → Challenge → Escalate**
- On-camera video clip capture and push delivery over HTTPS (no VPN, no port forwarding)
- Premium "Rolex of ACAPs" UI built with vanilla HTML/CSS/JS
- Multi-camera incident reel capability
- Camera health monitoring
- ONVIF-compatible event streams
- Push architecture: camera sends data outbound to cloud, no inbound rules needed

**Target verticals:** Hospitality, casino, retail, luxury venues, transportation hubs, corporate campuses, healthcare.

---

## 2. OpSignal — Full Platform Intelligence

OpSignal is the reference AI-powered security monitoring platform that FleetWatch should model and exceed. All intelligence gathered from live UI screenshots.

### 2.1 Navigation Structure

```
Left sidebar:
- Alerts Dashboard       (primary alerting surface)
- All Activity           (historical audit log)
- Exports                (data export)
- Administration         (expandable submenu)
- Support
```

### 2.2 Alerts Dashboard

**Header area:**
- Title: "Alerts Dashboard — View and take action on important location alerts."
- Location selector: "Viewing All Locations" (dropdown)
- Monitoring Status card: "ACTIVE" with animated waveform
- Alerts Last 24 Hours: count with change indicator ("No Change")

**Sensor Status widget (right column):**
- Shows: X Online / X Warning / X Offline
- "View Details" link opens Sensor Status modal
- Color coding: green = online, yellow = warning, red = offline

**Map widget:**
- Mapbox integration
- Red pin markers for camera locations
- Zoom in/out controls

**Alert List:**
- Header: "Alert List [N]" with count badge
- "Bulk Edit" button
- Each card shows:
  - Thumbnail with "Video (N)" badge showing clip count
  - Event title (linked)
  - Date (MM/DD/YYYY)
  - Clock icon + Time (HH:MM AM/PM CDT)
  - Location pin icon + Location name
  - Zone icon + Zone name
  - Event Type tags (colored badges)
  - Priority badge (Critical/High/Moderate)
  - "View Details" button

**Filter bar:**
- All Dates (calendar icon)
- Priority dropdown: Any Priority / Moderate Priority and Above / High Priority and Above / Critical Priority
- All Event Types dropdown

### 2.3 Alert Event Detail

**Tab navigation:** Event Details | Notifications [N] | Event History

**Video Evidence panel (left):**
- "Sensor Evidence (1/2)" with prev/next navigation
- Full video player with controls: play/pause, mute, timestamp, fullscreen
- Timeline scrubber with event markers
- "Aidant Actions" overlay button on video

**Right panel fields (all editable):**
- Priority (tag + Edit button)
- Title (text + Edit)
- Description (paragraph + Edit)
- Time (HH:MM AM CDT)
- Date (M/D/YYYY)
- Location (text)
- Zone (text)
- Sensors (comma-separated sensor names)
- Status (Open/Resolved + Resolve button)
- Notifications (count + View button)
- Event Type (tag + Edit)

**Action buttons (top right):** Export | Resolve Alert

### 2.4 Sensor Status Modal

```
Sensors Status
Please Contact Support if any sensors require attention.

Online  [N]    Warnings  [N]    Offline  [N]

Per-sensor entries:
  [Sensor Name (optional)]
  Type: Camera
  Location: [Location Name]
  Zone: Zone N
  Status: Online (green) / Offline (red)
  Offline duration: "Offline for X days Y hours Z minutes" (red text)
  Last response: "Last responded at H:MM pm" (green text)

[Close] button
```

**Live sensor data from screenshots:**
- F2107 Re — Camera, Zone 2, **Online**, Last responded at 9:19 pm
- F4108 — Camera, Zone 2, **Offline** for 66 days 9 hours 28 minutes
- F4108 Dome Sensor — Camera, Zone 2, **Offline** for 68 days 7 hours 22 minutes
- (unnamed) — Camera, Zone 2, **Offline** for 68 days 7 hours 22 minutes

**Counts shown:** 1 Online, 0 Warnings, 11 Offline

### 2.5 Date Filter UI

Calendar date range picker:
- Left panel: quick presets (All time / Last month / Last week / Last year / This month / This week / This year / Today / Yesterday)
- Right panel: dual-month calendar (June 2026 + July 2026)
- Date inputs: MM/DD/YYYY — MM/DD/YYYY
- Buttons: Reset | Cancel | Apply (blue)

### 2.6 All Activity Page

**Description:** "Historical record of all events for audit logs. Select events below to view details."

**Advanced Search:**
- Full-text search: "Search Activity by Title or Description"
- Date range picker
- Filters:
  - All Locations, Zones, and Sensors (dropdown)
  - All Event Types (dropdown)
  - Moderate Priority and Above (dropdown)
  - Any Alert Status (dropdown)

**Table columns:** Priority | Event Title and Description | Timestamp | Location | Event Type | Event Status | Actions

**Actions per row:** Export | View

**Pagination:** Previous | Page numbers | Next

**Export button:** "Export N Results" (top right of table)

### 2.7 Real Event Examples (from screenshots)

| Title | Date | Time | Priority | Location | Type | Status |
|---|---|---|---|---|---|---|
| Unauthorized Person with Rifle in Lobby and Room | 04/08/2026 | 10:40 AM CDT | Critical | Axis Experience Center / Zone 1 | Security | Open |
| Camera Tampering with Yellow Object | 03/24/2026 | 6:37 PM CDT | Moderate | Axis Experience Center / Zone 1 | Security | — |
| Unusual Floor Maneuvers in Lobby | 03/24/2026 | 4:44 PM CDT | Moderate | Axis Experience Center / Zone 1 | Safety, Security | — |
| Suspicious Person Attempts Unauthorized Access at Secure Door | 05/29/2026 | 9:47 PM CDT | Moderate | Axis Experience Center | Security | Resolved |
| Person Loitering Near Parked Bicycle by Secured Entrance | 04/09/2026 | 7:43 PM CDT | Moderate | Axis Experience Center | Security | Resolved |
| Player Argues at Blackjack Table | 04/09/2026 | 5:23 PM CDT | Moderate | Axis Experience Center | Security, Operations | Resolved |
| Unresponsive Person on Floor in Lobby | 04/09/2026 | 2:38 PM CDT | Moderate | Axis Experience Center | Safety, Security | Resolved |

**AI Description example (Critical Priority event):**
> "A person carrying what appeared to be a rifle entered the lobby and then proceeded into a room. The individual briefly surveyed the surroundings before exiting the area."

### 2.8 Sensors Used (from screenshots)

- Q3546 Le Dome (dome camera)
- Q1972 LE Thermal (thermal camera)
- F2107 Re
- F4108
- F4108 Dome Sensor
- **Location:** Axis Experience Center, 17 Cowboys Way, Frisco, TX 75034
- **Zones:** Zone 1, Zone 2

### 2.9 Key Platform Observations for FleetWatch

1. **AI descriptions are scene-narrative, not label-dumps** — full sentences describing what happened, what the person did, what happened next
2. **Multi-sensor events** — single alert can reference multiple sensors (dome + thermal)
3. **Video has multiple evidence clips** — "Sensor Evidence (1/2)" shows multiple clips per event
4. **Status is binary** — Open or Resolved, with explicit "Resolve Alert" action
5. **Event types are multi-tagged** — Security AND Safety can both apply
6. **Offline cameras are flagged with duration** — not just "offline" but "offline for 68 days 7 hours"
7. **Zero notifications on real events** — the "Notifications 0" suggests notification routing isn't always configured
8. **Export is everywhere** — at alert level and table level
9. **Mapbox for geolocation** — real map pin, not icon
10. **Bulk Edit available** — for mass status changes

---

## 3. ElectricEye Push Architecture

This is the reference architecture FleetWatch should implement for cloud delivery.

### 3.1 Architecture Flow

```
AOA detects person/vehicle
        ↓
Camera records clip locally to SD card (prebuffer 3-5s, postbuffer 15-20s)
        ↓
Camera pushes clip outbound over HTTPS
        ↓
ElectricEye / FleetWatch backend receives clip for AI analysis
```

### 3.2 Setup Steps (for camera configuration docs)

**Step 1 — SD Card:** 64GB+, high endurance / surveillance-rated

**Step 2 — Verify Storage:**
`System → Storage` — SD card mounted, retention enabled, "As long as possible"

**Step 3 — Enable AOA:**
`Apps → AXIS Object Analytics` — Create scenario, human + vehicle detection, tune zones/sensitivity/duration filters

**Step 4 — Recording Rule:**
`System → Events → Rules → Add Rule`
- Condition: Object Analytics → Scenario 1
- Action: Record video
- Prebuffer: 3–5s, Postbuffer: 15–20s, Storage: SD Card

**Step 5 — HTTPS Recipient:**
`System → Events → Recipients → Add Recipient`
- Name: FleetWatch (or ElectricEye)
- Type: HTTPS
- URL: `https://YOUR-ENDPOINT/functions/v1/axis-webhook?token=YOUR_TOKEN&camera_id=Camera01`

**Step 6 — HTTPS Clip Upload Rule:**
`System → Events → Rules → Add Rule`
- Condition: Object Analytics → Scenario 1
- Action: Send video clip through HTTPS
- Recipient: FleetWatch
- Prebuffer: 3–5s, Postbuffer: 15–20s, Clip length: ~20s, H.264, SD Card

**Step 7 — Validate:** Trigger event, confirm AOA fires, clip records, upload succeeds, backend receives.

### 3.3 Key Advantages

- No inbound ports required
- No VPN required
- No VMS dependency
- No additional hardware required
- Minimal bandwidth usage
- Works over cellular routers
- Ideal for trailers, construction sites, remote/mobile deployments

### 3.4 Troubleshooting Checklist

- No clips received → check SD card mounted, recording rule enabled, HTTPS URL correct, outbound internet, "Send video clip through HTTPS" selected
- AOA not appearing → check AXIS OS version, AOA installed, camera model supports it
- Upload test fails → check HTTPS URL, internet, firewall allows outbound HTTPS

---

## 4. AXIS Object Analytics (AOA) — Full Reference

### 4.1 Primary Documentation

| Resource | URL |
|---|---|
| AOA Developer Overview | https://developer.axis.com/analytics/axis-object-analytics/ |
| AOA VAPIX API Reference | https://developer.axis.com/vapix/applications/axis-object-analytics-api/ |
| AOA Counting Data Guide | https://developer.axis.com/analytics/axis-object-analytics/how-to-guides/axis-object-analytics-counting-data/ |
| AOA User Manual | https://help.axis.com/en-us/axis-object-analytics |
| AOA Product Page | https://www.axis.com/products/axis-object-analytics |

### 4.2 AOA API Endpoint

```
POST http://<camera-ip>/local/objectanalytics/control.cgi
Content-Type: application/json
```

### 4.3 Standard Request Structure

```json
{
  "apiVersion": "1.2",
  "context": "optional-string-echoed-in-response",
  "method": "<methodName>",
  "params": {}
}
```

### 4.4 AOA API Methods

| Method | Description |
|---|---|
| `getConfigurationCapabilities` | Returns min/max/default values for all configurable parameters |
| `getConfiguration` | Returns current application configuration |
| `setConfiguration` | Applies a complete configuration to the camera |
| `getSupportedVersions` | Returns list of supported API versions |
| `sendAlarmEvent` | Forces a scenario into alarm state for 3 seconds |
| `getAccumulatedCounts` | Retrieves counts from a Crossline Counting scenario |
| `resetAccumulatedCounts` | Resets accumulated counts |
| `resetPassthrough` | Resets passthrough counter |
| `getOccupancy` | Retrieves current occupancy for Occupancy in Area scenario |

### 4.5 AOA Scenario Types

| Type | Description |
|---|---|
| `motion` | Detect moving objects in a defined include area |
| `fence` | Detect objects crossing a virtual fence (directional) |
| `crosslinecounting` | Count objects crossing a defined line (directional) |
| `occupancyInArea` | Count objects present within an area (includes stationary) |

### 4.6 AOA Detectable Object Classes

```
human | car | bus | truck | bike | otherVehicle
```

### 4.7 AOA Scenario Filter Types

| Filter | Parameter |
|---|---|
| Size Percentage | `sizePercentage` |
| Size Perspective | `sizePerspective` |
| Short-lived Objects | `timeShortLivedLimit` |
| Swaying Objects | `distanceSwayingObject` |
| Speed | `speed` |
| Exclude Area | `excludeArea` |

### 4.8 AOA PTZ Preset Values

| Value | Meaning |
|---|---|
| -2 | Always tracking except when camera is moving |
| -1 | Track on all preset positions |
| 1 | Track on home position |
| 2+ | Track on specific presets only |

### 4.9 AOA Error Codes

| Code | Meaning |
|---|---|
| 1000 | Internal application error |
| 2000 | Requested API version not supported |
| 2002 | Incoherent configuration (e.g., mismatched ID) |
| 2003 | Mandatory parameter missing |
| 2004 | Invalid parameter |
| 2005 | Requested CGI method not supported |

### 4.10 AOA User Manual — All Scenario Types

**Area Scenarios:**
| Scenario | Description |
|---|---|
| Object in area | Detect objects entering/present in a defined area |
| Time in area | Detect objects that remain in area longer than set time |
| Occupancy in area | Count objects in area including stationary ones |
| PPE monitoring (BETA) | Detect personal protective equipment (hard hats, vests) |
| Motion in area | Detect motion within a defined area |

**Line Crossing Scenarios:**
| Scenario | Description |
|---|---|
| Line crossing | Detect when object crosses a virtual line |
| Crossline counting | Count objects crossing a line (directional) |
| Tailgating detection | Detect when one object closely follows another crossing a line |
| Motion line crossing | Detect motion crossing a virtual line |

### 4.11 setConfiguration — Create Object in Area Scenario Example

```json
{
  "apiVersion": "1.2",
  "context": "my context",
  "method": "setConfiguration",
  "params": {
    "devices": [{"id": 1, "type": "camera", "rotation": 0}],
    "scenarios": [{
      "id": 1,
      "name": "My Scenario",
      "type": "motion",
      "devices": [{"id": 1}],
      "triggers": [{"includeArea": {"vertices": [[-0.9,-0.9],[-0.9,0.9],[0.9,0.9],[0.9,-0.9]]}}]
    }]
  }
}
```

### 4.12 Event Topic Pattern

```
axis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario1
axis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario2
```
ScenarioN number matches the configured scenario number in AOA.

---

## 5. AXIS Scene Metadata — Full Reference

### 5.1 Primary Documentation

| Resource | URL |
|---|---|
| Scene Metadata Developer Docs | https://developer.axis.com/analytics/axis-scene-metadata/ |
| Scene Metadata Getting Started | https://developer.axis.com/analytics/axis-scene-metadata/getting-started/ |
| Enable Object Snapshots Guide | https://developer.axis.com/analytics/axis-scene-metadata/how-to-guides/object-snapshot-start/ |
| Scene Metadata Product Page | https://www.axis.com/products/axis-scene-metadata |

### 5.2 Key Facts

- Integrated into AXIS OS — cannot be downloaded separately
- Available as of **AXIS OS 10.6** on AI-powered cameras
- From **AXIS OS 11.9**: ACAP applications can consume Scene Metadata via Message Broker API

### 5.3 Data Sources / Topics

| Topic | Description | Access Method |
|---|---|---|
| Frame-by-frame object tracking | Real-time tracking with bounding boxes | RTSP, ACAP SDK, MQTT |
| Consolidated object information | Summary per object when it leaves scene | ACAP SDK, MQTT |
| Object snapshots | JPEG image of tracked objects | MQTT |

### 5.4 Transport Protocols

- **RTSP** — ONVIF-conformant XML stream
- **MQTT** — JSON payload via AXIS OS MQTT client
- **ACAP SDK** — Message Broker API subscription
- **Device Data Hub API** — New central data sharing (ARTPEC-7/8/9, CV25)

### 5.5 Visualization Tools

- **Built-in:** Camera web interface → Analytics > Metadata visualization
- **AXIS Metadata Monitor:** Windows 10/11 app (download from product page)
  - Visualizes Fusion Tracker RTSP output
  - Requires: Windows 10/11 + Axis device with Scene Metadata support
  - Connect via IP, select "Video content" / analytics metadata stream

---

## 6. VAPIX API — Full Reference

### 6.1 Primary Documentation

| Resource | URL |
|---|---|
| VAPIX Full Library | https://developer.axis.com/vapix/ |
| VAPIX Applications Index | https://developer.axis.com/vapix/applications/ |
| VAPIX Metadata API | https://developer.axis.com/vapix/metadata-api |
| VAPIX Audio API | https://developer.axis.com/vapix/audio-api |
| VAPIX Device Service API | https://developer.axis.com/vapix/device-service-api |
| VAPIX System API | https://developer.axis.com/vapix/system-api |
| VAPIX AOA API | https://developer.axis.com/vapix/applications/axis-object-analytics-api/ |
| VAPIX Application API | https://developer.axis.com/vapix/applications/application-api/ |

### 6.2 VAPIX Application APIs

| API | Description |
|---|---|
| Application API | Upload, control, and manage ACAP applications and license keys |
| AXIS Application Configuration API | Configure applications developed by Axis |
| AXIS Object Analytics API | Configure AOA scenarios, get counts, occupancy |
| License Plate Verifier API | LPR configuration and results |
| People Counter API | Counting persons |
| P8815-2 3D People Counter API | 3D people counting |
| Queue Monitor API | Queue analytics |
| Demographic Identifier API | Age/gender analytics |
| Occupancy Data | Occupancy analytics |
| Video Motion Detection 4 API | VMD configuration |

### 6.3 Key VAPIX Calls

**Check if ACAP app is installed:**
```
GET http://<camera>/axis-cgi/applications/list.cgi
```

**Upload ACAP application:**
```bash
curl --request POST \
  --anyauth \
  --user "<username>:<password>" \
  --form 'file=@<application.eap>;type=application/octet-stream' \
  "http://<camera>/axis-cgi/applications/upload.cgi"
```

**VAPIX Event Service WSDL:**
- Event: `http://www.axis.com/vapix/ws/event1/EventService.wsdl`
- Action: `http://www.axis.com/vapix/ws/action1/ActionService.wsdl`

---

## 7. ACAP SDK — Full API Reference

### 7.1 Primary Documentation

| Resource | URL |
|---|---|
| ACAP Version 12 Docs (current) | https://developer.axis.com/acap/ |
| ACAP Supported APIs Reference | https://developer.axis.com/acap/reference/supported-apis/ |
| ACAP API Compatibility Guide | https://developer.axis.com/acap/reference/supported-apis/api-compatibility-guide/ |
| ACAP Product Page | https://www.axis.com/for-developers/acap |

### 7.2 ACAP SDK Key Facts

- Open development framework for building apps that run directly on Axis network devices
- Supports: cameras, intercoms, speakers, radars
- SDK available free via Docker Hub (Ubuntu-based container)
- Supports C/C++ native applications
- ACAP v12 (Native SDK) is current; ACAP v3 still available
- Docker Hub SDK image includes: tools, API header/library files, packaging tools

### 7.3 ACAP Supported APIs — Full Compatibility Matrix

| API | Chip Compatibility | Purpose |
|---|---|---|
| Edge Storage API | ARTPEC-6/7/8/9, CV25, i.MX 6SoloX | Save/retrieve data on SD card or NAS |
| Event API | ARTPEC-6/7/8/9, CV25, i.MX 6SoloX | Send and receive events |
| License Key API | ARTPEC-6/7/8/9, CV25, i.MX 6SoloX | Validate application license keys |
| Machine Learning API (Larod) | ARTPEC-7/8/9, CV25 | Run ML models, image preprocessing |
| Message Broker API | ARTPEC-7/8/9, CV25 | Subscribe to metadata topics in AXIS OS |
| Device Data Hub API | ARTPEC-7/8/9, CV25 | Share data between apps and external interfaces |
| Axoverlay 2 API | ARTPEC-7/8/9 | Draw overlays in video streams (new) |
| Axoverlay API (Legacy) | ARTPEC-6/7/8/9 | Draw overlays with Cairo support (legacy) |
| Bounding Box API | ARTPEC-7/8/9, CV25 | Simple box drawing on scene |
| Parameter API | ARTPEC-6/7/8/9, CV25, i.MX 6SoloX | Read/write app parameters from manifest.json |
| Serial Port API | ARTPEC-7/8/9 | Control external serial port |
| Video Capture API (VDO) | ARTPEC-6/7/8/9, CV25 | Video/image stream capture and configuration |
| Pipewire | ARTPEC-6/7/8/9, CV25, i.MX 6SoloX | Audio/video stream multimedia framework |
| Cairo | ARTPEC-6/7/8/9 | 2D vector graphics rendering |
| OpenCL | ARTPEC-7/8/9 | GPU-accelerated parallel computing |
| FastCGI | ARTPEC-6/7/8/9, CV25, i.MX 6SoloX | HTTP request handling via web server |
| OpenSSL | ARTPEC-6/7/8/9, CV25, i.MX 6SoloX | Cryptography and secure communication |
| Jansson | ARTPEC-6/7/8/9, CV25, i.MX 6SoloX | JSON encode/decode |
| Curl | ARTPEC-6/7/8/9, CV25, i.MX 6SoloX | Data transfer with URLs |
| VAPIX access for ACAP | All | Call VAPIX from within ACAP app via loopback |
| HIDRAW access for ACAP | D3110 (from AXIS OS 11.11) | Raw access to HID devices |

### 7.4 ACAP Native SDK Example Applications

| Example | Description |
|---|---|
| `hello-world` | Simple hello world C application |
| `vdostream` | Capture frames from VDO service; access buffer contents and frame metadata |
| `audio-capture` | Capture audio |
| `audio-playback` | Play audio |
| `object-detection` | Object detection with bounding boxes on video stream |
| `object-detection-cv25` | Object detection on AXIS CV25; crop/save detected objects as JPEG |
| `object-detection-yolov5` | YOLOv5 object detection with bounding boxes |
| `tensorflow-to-larod` | Model conversion, quantization, image formats, custom models |
| `tensorflow-to-larod-artpec8` | Same as above for ARTPEC-8 devices |
| `tensorflow-to-larod-artpec9` | Same as above for ARTPEC-9 devices |
| `tensorflow-to-larod-cv25` | Same as above for CV25 devices |
| `vdo-larod` | Load TF model to Larod, fetch YUV frames via VDO, run inference |
| `using-opencv` | Build, bundle, and use OpenCV in an ACAP application |
| `utility-libraries` | Build, bundle, and use external libraries |
| `axoverlay` | Draw boxes and text as overlays in a stream |
| `bounding-box` | Draw burnt-in bounding boxes on video sources |
| `vdo-opencl-filtering` | Capture frames + GPU-accelerated Sobel filtering with OpenCL |
| `curl-openssl` | Use cURL + OpenSSL to retrieve files securely from external server |
| `web-server` | HTTP request handling with reverse proxy in ACAP |
| `web-server-using-fastcgi` | Handle HTTP requests via FastCGI |
| `axevent` | Subscribe to and send Axis events |
| `axparameter` | Manage application parameters (add/remove/set/get/callback) |
| `remote-debug-example` | Remote debug an ACAP application |
| `container-example` | Use containers in native ACAP application |
| `axserialport` | Use the serial port API |
| `axstorage` | Use available storage devices (SD card/NAS) |
| `licensekey` | Check license key status |
| `message-broker` | Use Message Broker API (consume Scene Metadata) |
| `reproducible-package` | Create a reproducible application package |
| `shell-script-example` | Hello world shell script application |
| `vapix` | Retrieve VAPIX credentials over D-Bus and make VAPIX calls |

### 7.5 Message Broker API — Scene Metadata Topics

Subscribe to these topics in AXIS OS (from AXIS OS 11.9):
- Frame-by-frame tracking topics (Fusion Tracker)
- Consolidated object information topics (Track Consolidation)
- Object snapshot topics

### 7.6 Device Data Hub API

- New central place for sharing data between platform applications, ACAP apps, and external interfaces
- Supported on ARTPEC-7/8/9 and Ambarella CV25

---

## 8. DLPU / Computer Vision / AI at the Edge

### 8.1 Primary Documentation

| Resource | URL |
|---|---|
| Computer Vision Developer Docs | https://developer.axis.com/computer-vision |
| Metadata & Analytics Overview | https://developer.axis.com/analytics/ |
| ACAP CV SDK Examples | https://github.com/AxisCommunications/acap-computer-vision-sdk-examples |

### 8.2 DLPU Key Facts

- Available on **ARTPEC-7, ARTPEC-8, ARTPEC-9, Ambarella CV25** chips
- Runs custom TensorFlow/YOLOv5 models at the edge
- Use cases: object detection, behavior analysis, traffic/retail analytics
- Benefits: low latency, reduced bandwidth (metadata only), no cloud dependency

### 8.3 Computer Vision Capabilities

| Capability | Description |
|---|---|
| Object & People Detection | Identify objects, people, vehicles directly on camera |
| Behavior Analysis | Recognize unusual activities, trigger events |
| Traffic & Retail Analytics | Track movement patterns |
| Custom Model Deployment | Train and deploy your own deep learning models |

### 8.4 Machine Learning API (Larod)

- Unified C API for running ML models and image preprocessing
- Arbitrates access to ML hardware across multiple ACAP apps
- Used with: `vdo-larod`, `object-detection`, `tensorflow-to-larod-artpec8/9` examples

---

## 9. Axis GitHub Repositories

**Organization:** https://github.com/AxisCommunications (51+ repositories)  
**Contact:** developer-offering@axis.com

### 9.1 Key Repositories

| Repository | Description | URL |
|---|---|---|
| `acap-native-sdk-examples` | Example code for ACAP Native SDK APIs | https://github.com/AxisCommunications/acap-native-sdk-examples |
| `acap-computer-vision-sdk-examples` | ACAP Computer Vision solution examples | https://github.com/AxisCommunications/acap-computer-vision-sdk-examples |
| `acap3-examples` | ACAP version 3 example code | https://github.com/AxisCommunications/acap3-examples |
| `acap-integration-examples-aws` | Axis devices + Amazon Web Services integration | https://github.com/AxisCommunications/acap-integration-examples-aws |
| `acap-integration-examples-gcp` | Axis devices + Google Cloud Platform integration | https://github.com/AxisCommunications/acap-integration-examples-gcp |
| `signed-video-framework` | Framework for signing and validating videos | https://github.com/AxisCommunications/signed-video-framework |
| `media-stream-library-js` | JavaScript library for media streams (Node.js + browser) | https://github.com/AxisCommunications/media-stream-library-js |
| `docker-acap` | Add Docker daemon to container-capable Axis device | https://github.com/AxisCommunications/docker-acap |
| `docker-compose-acap` | Add Docker + docker-compose to Axis device | https://github.com/AxisCommunications/docker-compose-acap |
| `tutorial-axis-object-analytics-to-grafana` | AOA counting data → AWS IoT → Amazon Timestream → Grafana | https://github.com/AxisCommunications/tutorial-axis-object-analytics-to-grafana |

---

## 10. ACAP Ideas — Future Apps to Build

Based on everything indexed, here are high-value ACAP concepts for future development:

### 10.1 Security / Access Control
| ACAP Name | Concept | AOA Trigger |
|---|---|---|
| **TailgateGuard** | Detect tailgating at controlled access doors | Tailgating detection scenario |
| **AfterHoursAlert** | Detect any human presence during closed hours | Motion in area (time-gated) |
| **PerimeterWatch** | Virtual fence alerts with clip upload | Fence crossing scenario |
| **PPE Monitor** | Detect workers without hard hats / vests | PPE monitoring (BETA) |
| **LingerWatch** | Alert when person dwells beyond X minutes | Time in area scenario |

### 10.2 Operations / Analytics
| ACAP Name | Concept | AOA Trigger |
|---|---|---|
| **QueueIntel** | Measure queue depth and wait times | Occupancy in area |
| **TrafficFlow** | Count and classify vehicles by direction | Crossline counting |
| **OccupancyDash** | Real-time room/zone occupancy display | Occupancy in area |
| **PeakHours** | Build traffic heatmaps by hour/day | Crossline counting accumulated |
| **LotSentinel** | Parking lot occupancy + vehicle type | Object in area + classification |

### 10.3 Safety
| ACAP Name | Concept | AOA Trigger |
|---|---|---|
| **FallDetect** | Detect person on ground, motionless | Custom model / time in area |
| **EvacuationCount** | Count persons exiting in emergency | Directional crossline counting |
| **CrowdDensity** | Alert when crowd exceeds occupancy limit | Occupancy in area threshold |
| **SlipAndFall** | Detect sudden ground-level events | Custom model via Larod |
| **AbandonedObject** | Detect objects left behind for X minutes | Object in area + time filter |

### 10.4 Retail / Hospitality
| ACAP Name | Concept | AOA Trigger |
|---|---|---|
| **GreetAlert** | Notify staff when customer enters zone | Object in area near entrance |
| **TableService** | Detect unattended tables for too long | Occupancy in area, no humans |
| **CheckoutMonitor** | Count customers at POS lanes | Occupancy in area per lane |
| **StockingAlert** | Detect employee in restricted zone | Motion in area + time of day |

### 10.5 Advanced / AI-Enhanced
| ACAP Name | Concept | Key Technology |
|---|---|---|
| **WeaponWatch** | Detect handheld objects of concern | Custom YOLOv5 model via Larod |
| **BehaviorScore** | Score scene abnormality 0–100 | Scene Metadata + LLM inference |
| **IncidentReel** | Auto-compile multi-camera incident clips | Edge Storage + HTTPS push |
| **ThermalFusion** | Correlate thermal + optical detections | Multi-sensor Scene Metadata |
| **LPR+Intent** | License plate + behavioral risk scoring | LPR API + AOA + custom model |

### 10.6 Integration ACAPs
| ACAP Name | Concept | Integration |
|---|---|---|
| **MQTTBridge** | Push all AOA events to custom MQTT broker | MQTT + Event API |
| **GrafanaPush** | Send counting data to Grafana via InfluxDB | Crossline counting + HTTP |
| **SlackSentinel** | Send alert clips to Slack channel | HTTPS + Slack webhook |
| **WebhookRelay** | Generic webhook forwarder for any AOA event | Event API + Curl |
| **SignedEvidence** | Sign video clips for chain-of-custody | Signed Video Framework |

---

## 11. FleetWatch AI — Current ACAP Spec

### 11.1 Identity

- **Name:** FleetWatch AI
- **Philosophy:** Premium "Rolex of ACAPs" — hospitality-grade, tactile, zero noise
- **Runtime:** Axis ACAP (FixedIT) on ARTPEC-7/8/9 or CV25 cameras
- **UI type:** Vanilla HTML/CSS/JS custom UI (no React, no bundlers, offline-safe)

### 11.2 3-Level Event Model

```
OBSERVE   — Something notable in frame. No immediate action required.
             Example: person loitering, vehicle idling, group gathering

CHALLENGE — Requires attention or verification. Guard or staff should check.
             Example: person in restricted zone, tailgating, unusual behavior

ESCALATE  — Immediate security response required.
             Example: weapon visible, person on ground, perimeter breach
```

### 11.3 Custom UI Navigation Sections

```
Dashboard          — Live feed + event summary + system status
Live View          — Direct camera stream with AOA overlays
Alerts             — Filterable event queue (Observe / Challenge / Escalate)
AI Description     — NLP scene summary, current + recent
Group Behavior     — Multi-person interaction analysis
Camera Health      — Sensor status, offline duration, SD card health
ONVIF              — Stream status, metadata topics, integration status
Admin              — Configuration, recipients, rules management
```

### 11.4 FleetWatch FixedIT File Structure

```
index.html                    — Custom UI root (HTML/CSS/JS)
fleetwatch.conf               — FixedIT inputs/processors/outputs config
fleetwatch_logic.star         — Starlark Observe/Challenge/Escalate rules
helpers/
  upload.sh                   — HTTPS clip push helper
  health_check.sh             — Sensor health check
```

### 11.5 Scene Intelligence Requirements

- Natural language description of scene (full sentences, not labels)
- Detect: persons, vehicles, groups, objects of concern
- Describe: entry, exit, dwell time, object carried, behavior pattern
- Flag: abnormal posture, rapid movement, unusual grouping, perimeter breach
- Multi-sensor: correlate dome + thermal detections

### 11.6 Camera Health Display

Per sensor:
- Name / model
- Zone
- Online / Offline / Warning status (color coded)
- Offline duration: "Offline X days Y hours Z minutes"
- Last response timestamp
- SD card health / storage remaining

### 11.7 Backend Payload Schema

```json
{
  "camera_id": "FrontLobby01",
  "location": "Axis Experience Center",
  "zone": "Zone 1",
  "timestamp": "2026-04-08T10:40:00-05:00",
  "event_type": ["Security"],
  "priority": "Escalate",
  "ai_title": "Unauthorized Person with Rifle in Lobby and Room",
  "ai_description": "A person carrying what appeared to be a rifle entered the lobby and then proceeded into a room. The individual briefly surveyed the surroundings before exiting the area.",
  "fleetwatch_level": "ESCALATE",
  "sensors": ["Q3546 Le Dome", "Q1972 LE Thermal"],
  "clips": [
    {"clip_id": "clip_001", "url": "...", "duration_sec": 20, "prebuffer_sec": 5},
    {"clip_id": "clip_002", "url": "...", "duration_sec": 20, "prebuffer_sec": 5}
  ],
  "aoa_trigger": "motion",
  "objects_detected": ["human"],
  "status": "Open"
}
```

---

## 12. Event Taxonomy & Priority Model

### 12.1 OpSignal Priority Levels (reference)

| Level | Badge | Use Case |
|---|---|---|
| Critical Priority | Red + up arrow | Weapon, immediate threat, life safety |
| High Priority | Orange + up arrow | Perimeter breach, access violation |
| Moderate Priority | Yellow/orange arrow | Loitering, unusual behavior, ops issue |

### 12.2 FleetWatch 3-Level Mapping

| FleetWatch | OpSignal Equivalent | Color |
|---|---|---|
| ESCALATE | Critical Priority | Red |
| CHALLENGE | High / Moderate Priority | Orange |
| OBSERVE | Low / Informational | Blue/Gray |

### 12.3 Event Type Tags (from OpSignal)

- Security
- Safety
- Operations
- (multiple tags per event allowed)

### 12.4 Alert Status Values

- Open (requires action)
- Resolved (closed out)

---

## 13. Payload Schema Reference

### 13.1 getAccumulatedCounts Response Fields

| Field | Description |
|---|---|
| `resetTime` | ISO 8601 — when counting started or was last reset |
| `timeStamp` | ISO 8601 — when count was read |
| `total` | Total objects of any category |
| `car` / `bus` / `bike` / `human` / `truck` / `otherVehicle` | Category counts |

---

## 14. AOA Counting Metadata Schemas (XML + JSON)

### 14.1 Crossline Counting — XML (RTSP/RTP ONVIF Stream)

```xml
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">
  <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">
    <wsnt:NotificationMessage
        xmlns:tnsaxis="http://www.axis.com/2009/event/topics"
        xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2">
      <wsnt:Topic>
        tnsaxis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario1
      </wsnt:Topic>
      <wsnt:Message>
        <tt:Message UtcTime="2023-01-16T12:46:07.800792Z">
          <tt:Data>
            <tt:SimpleItem Name="scenario" Value="Scenario 1" />
            <tt:SimpleItem Name="resetTime" Value="2023-01-15T23:00:00Z" />
            <tt:SimpleItem Name="total" Value="19723" />
            <tt:SimpleItem Name="totalCar" Value="18345" />
            <tt:SimpleItem Name="totalTruck" Value="1258" />
            <tt:SimpleItem Name="totalBus" Value="120" />
            <tt:SimpleItem Name="totalBike" Value="0" />
            <tt:SimpleItem Name="totalOtherVehicle" Value="0" />
            <tt:SimpleItem Name="reason" Value="car" />
          </tt:Data>
        </tt:Message>
      </wsnt:Message>
    </wsnt:NotificationMessage>
  </tt:Event>
</tt:MetadataStream>
```

### 14.2 Crossline Counting — JSON (MQTT)

```json
{
  "topic": "axis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario1",
  "timestamp": 1670518346712,
  "serial": "ACCC8EF1E944",
  "message": {
    "source": {},
    "key": {},
    "data": {
      "scenario": "Scenario 1",
      "resetTime": "2022-12-06T22:01:25Z",
      "total": "20960",
      "totalCar": "18103",
      "totalTruck": "2857",
      "totalBus": "0",
      "totalBike": "0",
      "totalOtherVehicle": "0",
      "totalHuman": "0",
      "reason": "car"
    }
  }
}
```

### 14.3 Occupancy in Area — XML (RTSP/RTP ONVIF Stream)

```xml
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">
  <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">
    <wsnt:NotificationMessage>
      <wsnt:Topic>
        tnsaxis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario1
      </wsnt:Topic>
      <wsnt:Message>
        <tt:Message UtcTime="2023-05-29T08:37:58.199601Z">
          <tt:Data>
            <tt:SimpleItem Name="scenario" Value="Scenario 1" />
            <tt:SimpleItem Name="total" Value="5" />
            <tt:SimpleItem Name="human" Value="0" />
            <tt:SimpleItem Name="car" Value="3" />
            <tt:SimpleItem Name="bus" Value="1" />
            <tt:SimpleItem Name="truck" Value="1" />
            <tt:SimpleItem Name="bike" Value="0" />
            <tt:SimpleItem Name="otherVehicle" Value="0" />
          </tt:Data>
        </tt:Message>
      </wsnt:Message>
    </wsnt:NotificationMessage>
  </tt:Event>
</tt:MetadataStream>
```

### 14.4 Occupancy in Area — JSON (MQTT)

```json
{
  "topic": "axis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario1",
  "timestamp": 1685349977783,
  "message": {
    "source": {},
    "key": {},
    "data": {
      "scenario": "Scenario 1",
      "total": "21",
      "car": "21",
      "bus": "0",
      "truck": "0",
      "bike": "0",
      "human": "0",
      "otherVehicle": "0"
    }
  }
}
```

---

## 15. Integration Platforms

| Platform | Integration Type |
|---|---|
| AXIS Camera Station | Native event triggers and recording rules |
| Milestone XProtect | AOA integration guide (PDF available) |
| Genetec Security Center | AOA integration guide (PDF available) |
| AWS IoT Core + Amazon Timestream + Grafana | Counting data pipeline |
| MQTT brokers | Any standard MQTT broker supported |
| ElectricEye | Push architecture (HTTPS clip upload) |
| FleetWatch AI backend | Push architecture (HTTPS clip upload) |

### 15.1 MQTT AOA Data Flow

```
Camera (AOA Event) → MQTT Publish → MQTT Broker → Subscriber App
```

### 15.2 RTSP AOA Data Flow

```
Camera (RTSP Stream) → Subscribe to metadata stream → Parse ONVIF XML
```

### 15.3 HTTPS Push Data Flow (FleetWatch / ElectricEye)

```
AOA Event → SD Card Recording → HTTPS POST to backend → AI analysis → Alert dashboard
```

---

## Developer Resources Quick Reference

| Resource | URL |
|---|---|
| Axis Developer Main Portal | https://www.axis.com/for-developers |
| Developer Documentation | https://developer.axis.com |
| Axis GitHub | https://github.com/AxisCommunications |
| ACAP Service Portal (License Keys) | Via My Axis account |
| AXIS Virtual Loan Tool | https://www.axis.com/for-developers (Virtual Loan Tool section) |
| Developer Contact | developer-offering@axis.com |

---

*Knowledge base compiled June 2026 from: ElectricEye Push Architecture Guide, Axis Developer Reference (Mike Lett), OpSignal platform UI screenshots, Axis ACAP/AOA/VAPIX/Scene Metadata documentation.*
