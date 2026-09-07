# SIH 2026 — Problem Statement 26162
# MASTER.md — Team Execution & Collaboration Plan

> **Project:** AI-Based Detection and Classification of Industrial Fires and Persistent Thermal Sources Using NASA FIRMS, OSM & Satellite Data
>
> **Prototype deadline:** 8 September 2026
>
> **Team:** Sarvesh, Anway, Yash, Arham, Sejal, Samiksha

---

# 1. Mission

We are building a prototype of an **AI-powered geospatial thermal intelligence platform**.

The system should take satellite thermal anomalies from **NASA FIRMS**, enrich them with **OpenStreetMap (OSM) industrial infrastructure**, environmental/land-cover context and temporal behavior, and produce:

1. **Thermal anomaly detection**
2. **Classification**
   - Industrial Fire
   - Persistent Industrial Thermal Source
   - Gas Flare
   - Wildfire / Natural Fire
   - Agricultural Fire
   - Unknown
3. **AI confidence**
4. **Risk score**
5. **Persistence / abnormality analysis**
6. **GIS visualization**
7. **Facility-level historical intelligence**

## Core demo story

```text
NASA FIRMS
    ↓
Thermal Anomaly
    ↓
Spatial + Temporal Enrichment
    ↓
OSM / Land-cover / Satellite Context
    ↓
AI Classification
    ↓
Risk + Anomaly Score
    ↓
GIS Dashboard
    ↓
Decision Support
```

Our goal is NOT to build a production system in two days.

Our goal is to build a **credible, polished, end-to-end prototype that clearly demonstrates the SIH problem solution**.

---

# 2. Team Structure

| Member | Primary Role | Task Name |
|---|---|---|
| **Sarvesh** | AI/ML Lead + Technical Lead | `AI-CORE` |
| **Arham** | AI/ML Engineer + Data Science | `AI-MODEL` |
| **Anway** | Backend Engineer | `BACKEND-API` |
| **Yash** | GIS / OSM / Geospatial Engineer | `GIS-OSM` |
| **Sejal** | Frontend Engineer | `FRONTEND-GIS` |
| **Samiksha** | UI/UX + Integration + Presentation | `UI-INTEGRATION` |

These are **primary ownership areas**, not isolated silos.

Everyone is expected to help integration when their primary module is working.

---

# 3. Golden Rules

## Rule 1 — Never wait unnecessarily

If another person's work is not ready, use **mock data** that follows the agreed interface.

Example:

```text
Real FIRMS data not ready
        ↓
Use mock FIRMS JSON
        ↓
Build ML / backend / frontend
        ↓
Replace mock data later
```

Do NOT spend 5 hours waiting for another person.

---

## Rule 2 — Interfaces come before implementations

Before coding, agree on:

- JSON structures
- API endpoints
- database fields
- filenames
- GeoJSON format
- model input/output

Once an interface is agreed upon, another person can build against it.

---

## Rule 3 — One owner per component

Each component has one primary owner.

Other members can contribute, but the owner is responsible for making sure the component works.

---

## Rule 4 — Do not modify another person's area without telling them

If you need to change another person's code:

1. Tell them.
2. Explain why.
3. Coordinate the change.
4. Avoid overwriting their work.

---

## Rule 5 — Working prototype > perfect architecture

We have a very short deadline.

Do NOT waste time on:

- Microservices
- Kubernetes
- Complex authentication
- Advanced DevOps
- Over-engineered neural networks
- Mobile applications
- Unnecessary features

A working end-to-end prototype is the priority.

---

# 4. Repository Structure

Use the following structure:

```text
sih-26162/
│
├── frontend/
│   ├── src/
│   ├── public/
│   └── ...
│
├── backend/
│   ├── app/
│   ├── routes/
│   ├── models/
│   └── ...
│
├── ml/
│   ├── data/
│   ├── notebooks/
│   ├── models/
│   ├── features/
│   └── inference/
│
├── gis/
│   ├── osm/
│   ├── geojson/
│   ├── processing/
│   └── scripts/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── demo/
│
├── docs/
│   ├── architecture/
│   ├── presentation/
│   └── screenshots/
│
├── README.md
└── MASTER.md
```

---

# 5. Collaboration Architecture

The project should be treated as several modules connected by contracts.

```text
                         ┌──────────────────┐
                         │   NASA FIRMS     │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  DATA PIPELINE   │
                         │   AI-CORE        │
                         └────────┬─────────┘
                                  │
                 ┌────────────────┼────────────────┐
                 │                │                │
                 ▼                ▼                ▼
          FIRMS Features      OSM Context     Temporal Data
                 │                │                │
                 └────────────────┼────────────────┘
                                  ▼
                         ┌──────────────────┐
                         │    AI-MODEL      │
                         │     ML Engine    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   BACKEND-API    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ FRONTEND-GIS     │
                         │ Interactive Map  │
                         └──────────────────┘
                                  ▲
                                  │
                         ┌──────────────────┐
                         │    GIS-OSM       │
                         │ Facilities/Geo   │
                         └──────────────────┘

                         UI-INTEGRATION
                  coordinates all components
```

---

# 6. MASTER DATA CONTRACT

All members must use these structures.

## 6.1 Thermal Event

```json
{
  "id": "FIRMS_001",
  "latitude": 19.076,
  "longitude": 72.877,
  "frp": 124.5,
  "brightness_temperature": 341.2,
  "confidence": 87,
  "timestamp": "2026-09-06T10:30:00Z",
  "satellite": "VIIRS"
}
```

### Required fields

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Unique event ID |
| `latitude` | float | Latitude |
| `longitude` | float | Longitude |
| `frp` | float | Fire Radiative Power |
| `brightness_temperature` | float | Thermal intensity |
| `confidence` | float/int | FIRMS confidence |
| `timestamp` | ISO datetime | Acquisition time |
| `satellite` | string | VIIRS/MODIS/etc. |

---

# 7. Enriched Event Contract

After GIS + feature engineering:

```json
{
  "id": "FIRMS_001",
  "latitude": 19.076,
  "longitude": 72.877,

  "frp": 124.5,
  "brightness_temperature": 341.2,
  "confidence": 87,

  "timestamp": "2026-09-06T10:30:00Z",

  "nearest_facility_id": "FAC_001",
  "nearest_facility_name": "Example Refinery",
  "facility_type": "refinery",
  "distance_to_facility_m": 76.4,

  "persistence_score": 0.84,
  "detections_24h": 5,
  "detections_7d": 18,

  "ndvi": 0.12,
  "ndbi": 0.68
}
```

Some fields may initially be unavailable.

Do NOT block the prototype because one optional feature is missing.

---

# 8. AI Prediction Contract

The ML module MUST expose a simple prediction interface.

Conceptually:

```python
predict(event) -> prediction
```

Expected output:

```json
{
  "event_id": "FIRMS_001",
  "classification": "industrial_fire",
  "confidence": 0.942,
  "risk_score": 87,
  "risk_level": "critical",
  "explanation": [
    "High FRP",
    "Located near industrial facility",
    "Persistent thermal activity",
    "Low vegetation context"
  ]
}
```

### Classification labels

Use these exact machine-readable values:

```text
industrial_fire
persistent_industrial_source
gas_flare
wildfire
agricultural_fire
unknown
```

Frontend can convert these into display names.

---

# 9. API Contract

Backend should expose:

```text
GET  /api/events
GET  /api/events/{event_id}

GET  /api/facilities
GET  /api/facilities/{facility_id}

GET  /api/analytics

POST /api/predict
```

## GET /api/events

Returns:

```json
[
  {
    "id": "FIRMS_001",
    "latitude": 19.076,
    "longitude": 72.877,
    "classification": "industrial_fire",
    "confidence": 0.942,
    "risk_score": 87,
    "risk_level": "critical"
  }
]
```

---

## GET /api/events/{event_id}

Returns complete event details:

```json
{
  "event": {},
  "prediction": {},
  "facility": {},
  "temporal": {}
}
```

---

## GET /api/facilities

Returns:

```json
[
  {
    "id": "FAC_001",
    "name": "Example Refinery",
    "type": "refinery",
    "latitude": 19.078,
    "longitude": 72.880
  }
]
```

---

## GET /api/analytics

Returns:

```json
{
  "total_events": 247,
  "industrial_events": 32,
  "critical_events": 8,
  "persistent_sources": 14
}
```

---

## POST /api/predict

Input:

```json
{
  "event_id": "FIRMS_001"
}
```

Output:

```json
{
  "classification": "industrial_fire",
  "confidence": 0.942,
  "risk_score": 87,
  "risk_level": "critical"
}
```

---

# 10. PERSON 1 — SARVESH
# `AI-CORE`

## Role

**AI/ML Lead + Technical Lead**

Sarvesh owns the overall AI pipeline and coordinates technical integration.

## Responsibilities

### A. FIRMS data understanding

- Understand NASA FIRMS fields
- Define the thermal-event schema
- Help validate FIRMS data
- Decide which FIRMS fields enter the model

### B. Feature engineering

Primary features:

```text
FRP
Brightness Temperature
Confidence
Distance to Industry
Distance to Forest
Distance to Agriculture
Persistence
Detections in 24h
Detections in 7d
Facility Type
NDVI
NDBI
```

### C. AI architecture

Design the first working classifier.

Preferred prototype:

```text
FIRMS + GIS + temporal features
            ↓
        XGBoost
            ↓
classification
confidence
```

Do NOT begin with an unnecessarily complex CNN.

### D. Risk scoring

Implement:

```text
risk_score = 0–100
```

Based on:

- thermal intensity
- industrial proximity
- persistence
- abnormality
- facility criticality

### E. Explainability

Every prediction should provide reasons.

Example:

```text
High FRP
+
Industrial proximity
+
High persistence
+
Low vegetation
=
Industrial Fire
```

## Deliverables

```text
ml/features/
ml/models/
ml/inference/
ml/predict.py
```

Most important function:

```python
predict(event)
```

## Depends on

- FIRMS data from AI-CORE/data work
- OSM features from GIS-OSM

## Can work immediately using

```text
data/demo/mock_events.csv
```

---

# 11. PERSON 2 — ARHAM
# `AI-MODEL`

## Role

**AI/ML Engineer + Data Science**

Arham works with Sarvesh, but should own separate ML work rather than duplicating it.

## Responsibilities

### A. Training dataset

Create an initial labeled dataset.

Possible classes:

```text
industrial_fire
persistent_industrial_source
gas_flare
wildfire
agricultural_fire
unknown
```

### B. Baseline model

Train:

```text
XGBoost
Random Forest
Logistic Regression
```

Compare quickly.

Choose the model that performs best while remaining simple.

### C. Model evaluation

Generate:

```text
Accuracy
Precision
Recall
F1
Confusion Matrix
```

Do not fabricate metrics.

If using a prototype/demo dataset, clearly document that it is a prototype dataset.

### D. Feature importance

Produce:

```text
Top features

1. Distance to facility
2. Persistence
3. FRP
4. Facility type
5. Brightness temperature
...
```

This is useful for the presentation.

### E. Anomaly detection

Develop the facility baseline concept:

```text
historical activity
        ↓
normal baseline
        ↓
current activity
        ↓
deviation
```

Example:

```text
Normal: 2 events/day
Current: 14 events/day
Deviation: +566%
```

## Deliverables

```text
ml/notebooks/
ml/models/
ml/evaluation/
ml/anomaly/
```

Outputs:

```text
trained model
metrics
feature importance
anomaly score
```

## Collaboration with Sarvesh

Sarvesh owns the overall AI pipeline.

Arham owns:

- training/evaluation
- anomaly detection
- model comparison

Sarvesh owns:

- feature pipeline
- inference integration
- risk scoring
- final model integration

They should NOT build two unrelated ML systems.

---

# 12. PERSON 3 — ANWAY
# `BACKEND-API`

## Role

**Backend Engineer**

## Responsibilities

Build the FastAPI service.

### API

Implement:

```text
GET /api/events
GET /api/events/{id}

GET /api/facilities
GET /api/facilities/{id}

GET /api/analytics

POST /api/predict
```

### Database

Preferred:

```text
PostgreSQL + PostGIS
```

If PostGIS setup becomes a blocker, use PostgreSQL/SQLite temporarily for the prototype.

### Tables

At minimum:

```text
thermal_events
facilities
predictions
```

### Thermal Events

```text
id
latitude
longitude
frp
brightness_temperature
confidence
timestamp
satellite
facility_id
```

### Facilities

```text
id
name
type
latitude
longitude
geometry
```

### Predictions

```text
event_id
classification
confidence
risk_score
risk_level
created_at
```

## Mock-first strategy

Before the real ML model exists:

```text
GET /api/events
        ↓
mock JSON
```

Before the real database exists:

```text
backend
   ↓
mock_events.json
```

Later replace the implementation.

The API contract should remain unchanged.

## Deliverables

```text
backend/
```

and a working API that the frontend can call.

---

# 13. PERSON 4 — YASH
# `GIS-OSM`

## Role

**GIS / OSM / Geospatial Engineer**

## Responsibilities

### A. OSM industrial facilities

Collect relevant facilities such as:

```text
refineries
chemical plants
power plants
steel plants
mines
LNG facilities
industrial areas
storage facilities
```

### B. Geospatial processing

For each FIRMS event calculate:

```text
nearest facility
distance to facility
facility type
inside/outside industrial area
```

### C. GeoJSON

Provide frontend-ready:

```text
facilities.geojson
events.geojson
```

### D. Spatial layers

Prepare:

```text
Industrial facilities
Thermal hotspots
Risk zones
Optional land-cover context
```

### E. OSM → Backend

Provide facility data to Anway.

Preferred format:

```json
{
  "id": "FAC_001",
  "name": "Example Refinery",
  "type": "refinery",
  "latitude": 19.078,
  "longitude": 72.880
}
```

## Deliverables

```text
gis/osm/
gis/geojson/
gis/processing/
```

Primary output:

```text
facilities.geojson
```

and enriched event data.

## Can work independently

Yash does NOT need the final backend.

He can use:

```text
mock FIRMS events
```

to test spatial matching.

---

# 14. PERSON 5 — SEJAL
# `FRONTEND-GIS`

## Role

**Frontend Engineer**

## Stack

Preferred:

```text
React
TypeScript
MapLibre GL / Leaflet
```

## Responsibilities

Build:

### Screen 1 — Dashboard

Cards:

```text
Total Events
Industrial Events
Critical Events
Persistent Sources
```

### Screen 2 — GIS Map

Layers:

```text
FIRMS hotspots
Industrial facilities
Risk
Optional satellite layer
```

### Screen 3 — Event Details

Show:

```text
Classification
Confidence
FRP
Brightness Temperature
Facility
Distance
Persistence
Risk
```

### Screen 4 — AI Analysis

Show:

```text
Industrial Fire
94.2%

Risk: 87/100

Why?

✓ High FRP
✓ Industrial proximity
✓ Persistent
✓ Low vegetation
```

### Screen 5 — Facility Intelligence

Show:

```text
Facility
Historical activity
Normal baseline
Current activity
Deviation
Risk
```

## Mock-first development

Sejal should NOT wait for Anway.

Start with:

```typescript
const mockEvent = {...}
const mockFacility = {...}
```

Build the complete UI.

Later replace:

```typescript
mock data
```

with:

```typescript
fetch("/api/events")
```

## Deliverables

```text
frontend/
```

Fully navigable prototype.

---

# 15. PERSON 6 — SAMIKSHA
# `UI-INTEGRATION`

## Role

**UI/UX + Integration + Presentation Lead**

This is a technical role, not just a PPT role.

## Responsibilities

### A. UI/UX

Work with Sejal on:

- visual hierarchy
- colors
- typography
- cards
- map styling
- event severity indicators
- responsive layout

### B. System integration

Track:

```text
FIRMS → AI
OSM → GIS
AI → Backend
GIS → Backend
Backend → Frontend
```

Identify broken interfaces.

### C. Demo data

Prepare guaranteed demo scenarios:

```text
Scenario 1 — Industrial Fire
Scenario 2 — Wildfire
Scenario 3 — Persistent Thermal Source
Scenario 4 — Abnormal Facility Activity
```

### D. Presentation

Prepare:

1. Problem
2. Existing limitation
3. Proposed solution
4. Architecture
5. AI methodology
6. GIS interface
7. Demo
8. Impact
9. Future scope

### E. Demo script

Ensure the demo works even if live data fails.

## Deliverables

```text
docs/presentation/
docs/architecture/
data/demo/
```

---

# 16. What Each Person Can Do Without Waiting

This is critical.

| Person | Does NOT need to wait for |
|---|---|
| Sarvesh | Final FIRMS pipeline |
| Arham | Final FIRMS pipeline |
| Anway | Final database |
| Yash | Final backend |
| Sejal | Final backend |
| Samiksha | Final product |

Everyone begins with **mock data + agreed interfaces**.

---

# 17. Mock Data Strategy

Create:

```text
data/demo/
├── events.json
├── facilities.json
├── predictions.json
└── analytics.json
```

These files allow the entire team to work immediately.

## Example event

```json
{
  "id": "DEMO_001",
  "latitude": 19.076,
  "longitude": 72.877,
  "frp": 184,
  "brightness_temperature": 412,
  "confidence": 94,
  "timestamp": "2026-09-06T14:32:00Z"
}
```

## Example prediction

```json
{
  "event_id": "DEMO_001",
  "classification": "industrial_fire",
  "confidence": 0.942,
  "risk_score": 87,
  "risk_level": "critical"
}
```

This lets:

```text
AI → test predictions
Backend → test API
Frontend → test UI
GIS → test spatial visualization
Presentation → test demo
```

WITHOUT waiting for real data.

---

# 18. Git Workflow

## Main branch

```text
main
```

Only merge working code.

## Individual branches

```text
feature/ai-core
feature/ai-model
feature/backend-api
feature/gis-osm
feature/frontend
feature/ui-integration
```

## Commit format

Use simple messages:

```text
feat: add FIRMS parser
feat: add event prediction
feat: add events API
feat: add OSM facility layer
feat: add event details panel
docs: add architecture diagram
fix: correct event coordinates
```

## Before merging

Each member should verify:

```text
□ Code runs
□ No obvious errors
□ Does not break another module
□ README/documentation updated if necessary
```

---

# 19. Integration Interfaces

## Interface A

### FIRMS → AI

Input:

```json
{
  "id": "...",
  "latitude": 0,
  "longitude": 0,
  "frp": 0,
  "brightness_temperature": 0,
  "confidence": 0,
  "timestamp": "...",
  "satellite": "VIIRS"
}
```

---

## Interface B

### GIS → AI

Additional features:

```json
{
  "facility_type": "refinery",
  "distance_to_facility_m": 76,
  "inside_industrial_area": true
}
```

---

## Interface C

### AI → Backend

```json
{
  "classification": "industrial_fire",
  "confidence": 0.942,
  "risk_score": 87,
  "risk_level": "critical",
  "explanation": []
}
```

---

## Interface D

### Backend → Frontend

Frontend should receive already-prepared data.

Frontend should NOT perform ML.

Frontend should NOT calculate complex geospatial logic.

Backend does the processing.

---

# 20. Main Demo Scenario

The team should build around ONE excellent scenario.

## Scenario

A thermal anomaly appears near a petrochemical facility.

### Step 1

NASA FIRMS detects:

```text
FRP: 184 MW
Confidence: 94%
```

### Step 2

OSM finds:

```text
Petrochemical facility
76 m away
```

### Step 3

Temporal engine finds:

```text
4 detections today
Normal = 1–2
```

### Step 4

AI predicts:

```text
Industrial Fire
94.2%
```

### Step 5

Risk engine:

```text
87 / 100
CRITICAL
```

### Step 6

Dashboard displays:

```text
🚨 INDUSTRIAL FIRE

AI Confidence: 94.2%
Risk Score: 87/100

Facility:
Petrochemical Complex

Distance:
76m

Thermal activity:
+566% above baseline
```

### Step 7

Show historical timeline.

This should be the centerpiece of the presentation.

---

# 21. Secondary Demo Scenario

Then demonstrate a wildfire.

```text
FIRMS
 ↓
Forest region
 ↓
High vegetation
 ↓
No nearby industrial facility
 ↓
Spatial spread
 ↓
AI
 ↓
WILDFIRE
```

Then show the comparison:

```text
Industrial Fire          Wildfire

Industry proximity ✓     Industry proximity ✗
Persistent ✓              Spatial spread ✓
Low vegetation ✓          High vegetation ✓
High FRP ✓                High FRP ✓
```

This directly demonstrates the SIH requirement:

> **Segregation of industrial fires from natural fires.**

---

# 22. Timeline

# 6 September — FOUNDATION

## First 60 minutes — ALL MEMBERS

Agree on:

```text
✓ Architecture
✓ Data schema
✓ API schema
✓ Repository
✓ Responsibilities
✓ Demo scenario
```

No one should start major coding before this is understood.

---

## Next 4–6 hours

### Sarvesh

Build:

```text
FIRMS parsing
feature pipeline
risk logic
```

### Arham

Build:

```text
training dataset
baseline model
evaluation
anomaly detection
```

### Anway

Build:

```text
FastAPI
mock APIs
database skeleton
```

### Yash

Build:

```text
OSM extraction
facility GeoJSON
spatial matching
```

### Sejal

Build:

```text
dashboard
map
event details
AI panel
```

### Samiksha

Build:

```text
UI design
demo dataset
architecture diagram
PPT
```

---

# 7 September — INTEGRATION

## Morning

Connect:

```text
FIRMS → ML
OSM → ML
ML → Backend
GIS → Backend
Backend → Frontend
```

## Afternoon

End-to-end test:

```text
click hotspot
 ↓
event details
 ↓
AI prediction
 ↓
risk
 ↓
facility
 ↓
history
```

## Evening

STOP adding major features.

Only:

```text
Bug fixing
UI polish
Demo rehearsal
Performance fixes
Presentation rehearsal
```

---

# 8 September — PRESENTATION

Do NOT introduce major code changes.

Run the demo multiple times before presenting.

Have:

```text
LIVE MODE
```

and:

```text
DEMO/HISTORICAL MODE
```

If NASA/FIRMS or another external service fails, the demonstration should still work.

Be transparent that demo mode uses curated/historical data.

---

# 23. Definition of Done

A module is NOT "done" because the code exists.

It is done when:

### AI

```text
□ Model loads
□ Prediction works
□ Confidence returned
□ Risk score returned
□ Explanation returned
```

### Backend

```text
□ Server starts
□ APIs respond
□ JSON contract correct
□ Frontend can consume it
```

### GIS

```text
□ Facilities available
□ Coordinates correct
□ GeoJSON works
□ Spatial distance works
```

### Frontend

```text
□ Map loads
□ Hotspots appear
□ Facilities appear
□ Clicking event works
□ AI result displayed
□ Risk displayed
```

### UI/Integration

```text
□ Complete flow works
□ Demo scenarios work
□ PPT complete
□ Architecture diagram complete
□ No broken screens
```

---

# 24. Communication Protocol

Create one team group/channel.

Use messages like:

```text
[BLOCKED]
Need OSM facility JSON for backend.

[READY]
AI prediction endpoint ready.

[INTERFACE CHANGE]
Prediction now uses `risk_score` instead of `risk`.

[MERGED]
GIS facility layer merged into main.

[DEMO]
Industrial fire scenario working.
```

Avoid:

```text
"bro it's done"
```

because nobody knows what "done" means.

---

# 25. Daily Checkpoints

Have very short team meetings.

## Morning — 10 minutes

Each person says:

```text
1. What am I doing?
2. What do I need?
3. Am I blocked?
```

## Evening — 15 minutes

Each person says:

```text
1. What works?
2. What doesn't?
3. What will be ready next?
```

No long meetings.

---

# 26. Priority System

Every task gets:

### P0 — MUST HAVE

```text
FIRMS data
GIS map
industrial facilities
classification
risk score
backend
frontend
end-to-end demo
```

### P1 — SHOULD HAVE

```text
persistence
facility baseline
historical charts
satellite context
explainability
```

### P2 — NICE TO HAVE

```text
advanced deep learning
real-time alerts
advanced satellite fusion
user accounts
cloud deployment
```

If time runs out:

**P2 is deleted first.**

---

# 27. What We Are NOT Claiming

Be scientifically honest.

Do NOT claim:

```text
"100% accurate"
"real-time satellite detection everywhere"
"production-ready"
"fully autonomous disaster response"
```

Instead say:

```text
"prototype"
"AI-assisted classification"
"near-real-time where source data is available"
"decision-support system"
"prototype validation"
```

This makes the project more credible.

---

# 28. Final System Architecture for Presentation

Use this diagram:

```text
                    ┌───────────────────┐
                    │    NASA FIRMS     │
                    │ VIIRS / MODIS     │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Thermal Event     │
                    │ Processing        │
                    └─────────┬─────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
    ┌──────────┐        ┌──────────┐       ┌────────────┐
    │   OSM    │        │Satellite │       │ Temporal   │
    │ Industry │        │ Context  │       │ Analysis   │
    └────┬─────┘        └────┬─────┘       └─────┬──────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                    ┌───────────────────┐
                    │ Feature Engineering│
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │     AI ENGINE     │
                    │                   │
                    │ Classification    │
                    │ Anomaly Detection │
                    │ Risk Assessment   │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   FastAPI Backend  │
                    │   PostgreSQL/PostGIS│
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ React GIS Dashboard│
                    │                   │
                    │ Map + Analytics   │
                    │ Alerts + History  │
                    └───────────────────┘
```

---

# 29. Final Team Principle

The six people are NOT six people building six separate projects.

We are building:

```text
                    ONE PRODUCT
                       │
       ┌───────────────┼───────────────┐
       │               │               │
      DATA             AI             GIS
       │               │               │
       └───────────────┼───────────────┘
                       │
                    BACKEND
                       │
                    FRONTEND
                       │
                     DEMO
```

The key is **contracts + mock data + parallel development + early integration**.

If something isn't ready, don't wait.

If an interface changes, communicate it.

If a feature isn't helping the core demo, cut it.

**The target for 8 September is not the most complicated system. It is the most convincing working end-to-end prototype.**
