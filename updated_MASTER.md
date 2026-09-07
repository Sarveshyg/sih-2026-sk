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

---

# 30. AUTHORITY ALERT & ESCALATION SYSTEM
# `ALERT-ESCALATION`

This is a **core decision-support feature** and should be included in the prototype if implemented cleanly.

The purpose is to ensure that an AI detection does **not automatically become a disaster declaration**.

Instead:

```text
AI DETECTION
     ↓
AUTOMATED TRIAGE
     ↓
TIER 1 AUTHORITY
     ↓
HUMAN VERIFICATION
     │
     ├── GREEN → CLOSE / MONITOR
     │
     └── RED
          ↓
      TIER 2 AUTHORITY
          ↓
      HUMAN VERIFICATION
          │
          ├── GREEN → CLOSE / MONITOR
          │
          └── RED
               ↓
           TIER 3 / NATIONAL
               ↓
          NATIONAL RESPONSE
```

## Important principle

The AI is a **decision-support and prioritization system**, not the final authority.

The system should say:

> "AI detected a potentially significant event and recommends verification."

It should NOT say:

> "AI has declared an emergency."

Human authorities remain responsible for verification and escalation.

---

# 31. Three-Tier Authority Model

For the prototype, use generic authority names rather than claiming a specific real-world government workflow unless the relevant authority structure has been officially validated.

## Tier 1 — Local / First Verification

Example conceptual role:

```text
District / Local Disaster Management Authority
        OR
Local emergency response authority
```

### Responsibility

Tier 1 receives the initial AI-generated alert.

They verify:

- Is the event actually occurring?
- Is it a false positive?
- Is it natural or industrial?
- Is there visible smoke/fire?
- Is infrastructure at risk?
- Is immediate intervention required?

### Available actions

```text
GREEN — Verified / No escalation required
RED   — Confirmed / Requires escalation
```

Optional:

```text
YELLOW — Needs more information
```

For the prototype, GREEN and RED are sufficient.

---

# 32. Tier 2 — Regional / State Verification

Tier 2 receives an event only when Tier 1 marks it **RED**.

Example conceptual role:

```text
State / Regional Disaster Management Authority
```

Tier 2 sees the complete case history:

```text
Original FIRMS detection
AI classification
AI confidence
Risk score
OSM facility
Satellite context
Tier 1 decision
Tier 1 comments
Historical activity
Timeline
```

Tier 2 performs a second-level verification.

### Actions

```text
GREEN
    ↓
De-escalate / continue monitoring

RED
    ↓
Escalate to Tier 3
```

---

# 33. Tier 3 — National Authority

Tier 3 receives cases escalated by Tier 2.

Example conceptual role:

```text
National Disaster Management / Central Authority
```

The Tier 3 dashboard should show:

```text
CRITICAL ESCALATION

Event:
Industrial Fire

Location:
[Map]

AI Confidence:
94.2%

Risk:
87 / 100 — CRITICAL

Tier 1:
RED — Confirmed

Tier 2:
RED — Confirmed

Evidence:
✓ FIRMS thermal anomaly
✓ Persistent activity
✓ Industrial facility proximity
✓ Satellite context
✓ Historical deviation
```

The prototype can then display:

```text
NATIONAL RESPONSE REQUIRED
```

Again, this is a **prototype decision-support state**, not an actual automated government alert.

---

# 34. Alert Lifecycle

Every alert should have a state.

Recommended state machine:

```text
DETECTED
    ↓
AI_TRIAGED
    ↓
TIER_1_PENDING
    │
    ├── GREEN → CLOSED
    │
    └── RED
         ↓
    TIER_2_PENDING
         │
         ├── GREEN → MONITORING
         │
         └── RED
              ↓
        TIER_3_ESCALATED
              ↓
        NATIONAL_REVIEW
```

Optional states:

```text
ACKNOWLEDGED
UNDER_REVIEW
NEEDS_MORE_INFORMATION
FALSE_POSITIVE
RESOLVED
```

---

# 35. Alert Severity vs Escalation Level

Do NOT confuse these two concepts.

## Risk level

Determined by the system:

```text
LOW
MODERATE
HIGH
CRITICAL
```

## Authority level

Determined by workflow:

```text
TIER 1
TIER 2
TIER 3
```

Example:

```text
AI Risk:
CRITICAL

Current Authority:
TIER 1 — PENDING VERIFICATION
```

This means:

> The AI considers the event serious, but Tier 1 still has to verify it.

---

# 36. Alert Creation Logic

When a FIRMS event arrives:

```text
FIRMS EVENT
     ↓
AI CLASSIFICATION
     ↓
RISK SCORE
     ↓
AUTOMATED TRIAGE
```

The system determines whether the event should enter the authority workflow.

Example:

```text
Industrial Fire
Confidence = 94%
Risk = 87
        ↓
CREATE ALERT
        ↓
TIER 1
```

For a low-confidence event:

```text
Unknown
Confidence = 42%
Risk = 18
        ↓
NO ESCALATION
        ↓
MONITOR
```

This prevents authorities from receiving thousands of insignificant alerts.

---

# 37. Recommended Triage Logic

Prototype example:

```text
IF risk_score >= 75:
    create Tier 1 alert

ELIF risk_score >= 50:
    create monitoring alert

ELSE:
    store event only
```

The thresholds are **prototype parameters**, not official emergency thresholds.

For industrial facilities:

```text
High-risk industrial event
        ↓
Tier 1 verification
```

For a potentially spreading wildfire:

```text
Wildfire + high risk + spatial spread
        ↓
Tier 1 verification
```

---

# 38. Human Verification Interface

Authorities should NOT have to open the AI/ML system internals.

Give them a simple case-review interface.

Example:

```text
┌──────────────────────────────────────────────┐
│ ALERT #IND-92841                             │
├──────────────────────────────────────────────┤
│                                              │
│ 🚨 POTENTIAL INDUSTRIAL FIRE                 │
│                                              │
│ AI Confidence:       94.2%                   │
│ Risk Score:          87/100                  │
│                                              │
│ Facility:            Petrochemical Complex   │
│ Distance:            76 m                    │
│ FRP:                 184 MW                  │
│ Persistence:         HIGH                    │
│                                              │
│ ───────── AI EVIDENCE ─────────              │
│ ✓ High thermal intensity                     │
│ ✓ Industrial facility nearby                 │
│ ✓ Persistent activity                        │
│ ✓ Abnormal compared to baseline              │
│                                              │
│ [ VIEW SATELLITE ] [ VIEW HISTORY ]          │
│                                              │
│ ───────── VERIFICATION ─────────             │
│                                              │
│ Comments: [____________________________]      │
│                                              │
│ [ GREEN — VERIFIED ] [ RED — ESCALATE ]      │
└──────────────────────────────────────────────┘
```

---

# 39. GREEN Decision

If Tier 1 selects GREEN:

```text
TIER 1
   ↓
GREEN
   ↓
ALERT RESOLVED / MONITORING
```

Store:

```text
authority
timestamp
decision
comments
```

Example:

```json
{
  "tier": 1,
  "decision": "green",
  "authority": "Tier 1",
  "comments": "Verified as routine industrial thermal activity.",
  "timestamp": "2026-09-06T15:20:00Z"
}
```

The event remains in the historical database.

---

# 40. RED Decision

If Tier 1 selects RED:

```text
TIER 1
   ↓
RED
   ↓
TIER 2
```

The system should automatically create:

```text
Tier 2 Alert
```

and preserve the Tier 1 decision.

The Tier 2 reviewer sees:

```text
Tier 1:
RED

Reason:
Confirmed abnormal thermal activity

Comment:
"Visible smoke reported by local verification team."
```

---

# 41. Tier 2 GREEN

```text
Tier 1 RED
     ↓
Tier 2 REVIEW
     ↓
GREEN
     ↓
DE-ESCALATE
```

Status:

```text
RESOLVED_AFTER_TIER_2
```

---

# 42. Tier 2 RED

```text
Tier 1 RED
     ↓
Tier 2 RED
     ↓
TIER 3
```

The national-level case should contain the full chain:

```text
FIRMS
 ↓
AI
 ↓
Risk
 ↓
Tier 1 RED
 ↓
Tier 2 RED
 ↓
Tier 3
```

This creates a complete **audit trail**.

---

# 43. Alert Database Model

Add an `alerts` table.

Recommended fields:

```text
alerts
------
id
event_id
severity
risk_score
current_tier
status
created_at
updated_at
```

Add an `alert_actions` table:

```text
alert_actions
-------------
id
alert_id
tier
decision
authority_name
comments
timestamp
```

This allows you to reconstruct the complete history.

---

# 44. Alert API

Anway should add these endpoints.

```text
GET  /api/alerts
GET  /api/alerts/{alert_id}

POST /api/alerts/{alert_id}/verify

GET  /api/alerts/{alert_id}/history
```

## Verification request

```json
{
  "tier": 1,
  "decision": "red",
  "comments": "Confirmed abnormal fire activity."
}
```

Backend automatically determines the next state.

Example:

```text
Tier 1 RED
    ↓
current_tier = 2
status = TIER_2_PENDING
```

Then:

```text
Tier 2 RED
    ↓
current_tier = 3
status = TIER_3_ESCALATED
```

---

# 45. Frontend Alert Views

Sejal should add:

## Alert Center

```text
┌────────────────────────────────────────────────┐
│ ALERT CENTER                                   │
├────────────────────────────────────────────────┤
│                                                │
│ 🔴 8 CRITICAL                                  │
│ 🟠 14 HIGH                                     │
│ 🟡 23 MODERATE                                 │
│                                                │
├────────────────────────────────────────────────┤
│ #92841  Industrial Fire      T1 PENDING       │
│ #92840  Wildfire             T2 PENDING       │
│ #92832  Gas Flare            RESOLVED         │
│ #92821  Thermal Source       T3 ESCALATED     │
└────────────────────────────────────────────────┘
```

---

# 46. Map Integration

Alerts should also appear on the map.

Example:

```text
🔴 = Tier 1 pending
🟠 = Tier 2 pending
🟣 = Tier 3 escalated
🟢 = verified/resolved
```

Clicking the marker opens the case.

This connects:

```text
GIS
+
AI
+
Alert workflow
```

into one interface.

---

# 47. Notification Concept

For the prototype, show an in-app notification system.

Example:

```text
🚨 NEW ALERT

Potential Industrial Fire
Petrochemical Complex

Risk: 87/100

Tier 1 verification required.
```

When escalated:

```text
⬆ ALERT ESCALATED

Alert #92841

Tier 1 → RED
Escalated to Tier 2.
```

Then:

```text
⬆ NATIONAL ESCALATION

Alert #92841

Tier 1 → RED
Tier 2 → RED

Tier 3 / National Review Required.
```

For the prototype, do NOT claim that real government SMS/email systems are connected unless they actually are.

---

# 48. Role Changes

## SARVESH — `AI-CORE`

Add:

- Automated triage
- Risk threshold logic
- AI confidence
- Explanation for alert creation

Sarvesh decides:

```text
Should this event enter the alert workflow?
```

---

## ARHAM — `AI-MODEL`

Add:

- Risk/anomaly modeling
- Historical baseline
- Severity features
- False-positive analysis

Arham helps determine:

```text
How unusual / severe is the event?
```

---

## ANWAY — `BACKEND-API`

Add:

```text
alerts table
alert_actions table

GET /api/alerts
GET /api/alerts/{id}
POST /api/alerts/{id}/verify
GET /api/alerts/{id}/history
```

Anway owns the state machine.

---

## YASH — `GIS-OSM`

Add:

- Alert location
- Facility context
- Administrative/geographic context where available
- Map geometry required for alert visualization

Yash answers:

> Where is the event and what infrastructure is affected?

---

## SEJAL — `FRONTEND-GIS`

Add:

- Alert Center
- Alert status badges
- Verification screen
- Escalation timeline
- Map alert markers
- Tier indicators

---

## SAMIKSHA — `UI-INTEGRATION`

Add:

- Authority workflow UX
- Alert demo scenarios
- Escalation presentation
- End-to-end testing
- Demo script

She should ensure the judges can understand the workflow immediately.

---

# 49. Best Demo for This Feature

This should be one of your main presentation moments.

Start with a forest fire.

```text
FIRMS detects thermal anomaly
        ↓
AI:
WILDFIRE — 96%
        ↓
Risk:
82/100 HIGH
        ↓
ALERT CREATED
        ↓
TIER 1
```

Show the Tier 1 authority screen.

Then click:

```text
🔴 RED — CONFIRMED
```

Immediately:

```text
ALERT ESCALATED

Tier 1 → RED
Tier 2 verification required
```

Then switch to Tier 2.

Show the same case with additional evidence.

Click:

```text
🔴 RED — CONFIRMED
```

Then:

```text
NATIONAL ESCALATION

Tier 1: RED
Tier 2: RED
Tier 3: PENDING
```

This is a **very strong visual demonstration**.

---

# 50. Important Safety / Governance Position

The presentation should explicitly state:

> **"The system does not replace human authorities. AI performs detection, classification, prioritization and evidence aggregation. Every escalation decision remains subject to human verification."**

This is important because an automated disaster-alert system making irreversible decisions would be difficult to justify.

Your architecture therefore becomes:

```text
             AI
              ↓
       DETECT + CLASSIFY
              ↓
        PRIORITIZE
              ↓
       HUMAN VERIFICATION
              ↓
          ESCALATE
              ↓
       HUMAN VERIFICATION
              ↓
          ESCALATE
```

This gives you **human-in-the-loop AI**, explainability, accountability and an auditable escalation chain.

---

# 51. Updated Prototype Priority

Because of the September 8 deadline:

## P0 — MUST HAVE

```text
✓ FIRMS detection
✓ GIS map
✓ OSM industrial context
✓ AI classification
✓ Risk score
✓ Tier 1 alert
✓ GREEN / RED verification
✓ Tier 2 escalation
✓ Tier 3 escalation
✓ Alert history
✓ End-to-end demo
```

## P1 — SHOULD HAVE

```text
✓ Historical facility baseline
✓ Satellite imagery
✓ AI explanations
✓ Alert notifications
✓ Analytics dashboard
```

## P2 — NICE TO HAVE

```text
○ Real SMS/email integration
○ Advanced deep-learning fusion
○ Real authority authentication
○ Mobile application
○ Automated external dispatch
○ Complex role-based access control
```

**P2 features must not delay the P0 workflow.**

---

# 52. Updated End-to-End Product

The complete system is now:

```text
                    NASA FIRMS
                        ↓
                 THERMAL EVENT
                        ↓
             ┌──────────────────┐
             │ Context Engine   │
             │                  │
             │ OSM              │
             │ Satellite        │
             │ Land Cover       │
             │ Temporal History │
             └────────┬─────────┘
                      ↓
                  AI ENGINE
                      ↓
              Classification
                      +
                  Risk Score
                      +
                Anomaly Score
                      ↓
              AUTOMATED TRIAGE
                      ↓
              ┌───────────────┐
              │  Tier 1       │
              │  Verification │
              └───────┬───────┘
                      │
               GREEN / RED
                 │       │
                 │       ↓
                 │    Tier 2
                 │       │
                 │   GREEN / RED
                 │       │
                 │       ↓
                 │    Tier 3
                 │       │
                 ↓       ↓
              MONITOR   NATIONAL
                       RESPONSE
                      ↓
                 AUDIT TRAIL
                      ↓
                 GIS DASHBOARD
```

This makes the product much more than:

> **"AI detects fires."**

It becomes:

> **"An AI-assisted geospatial disaster intelligence and human-in-the-loop escalation platform."**

---

# 53. AUTHENTICATION & ROLE-BASED ACCESS CONTROL
# `AUTH-RBAC`

The platform must have **two login categories** with different permissions.

```text
                         LOGIN
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
       VIEWER LOGIN              AUTHORITY LOGIN
              │                         │
              ▼                         ▼
        READ-ONLY ACCESS          TIER-SPECIFIC ACCESS
                                        │
                              ┌─────────┼─────────┐
                              ▼         ▼         ▼
                            TIER 1    TIER 2    TIER 3
```

The purpose is to ensure that normal users can monitor information without being able to interfere with the official alert workflow.

---

# 54. LOGIN TYPE 1 — VIEWER

## Role

```text
VIEWER
```

This is the normal user / observer account.

A viewer can access the public monitoring side of the platform.

### Viewer can:

```text
✓ View the GIS map
✓ View FIRMS thermal events
✓ View industrial facilities
✓ View classifications
✓ View AI confidence
✓ View risk scores
✓ View historical activity
✓ View analytics
✓ View resolved alerts
✓ View general alert status
```

### Viewer cannot:

```text
✗ Verify an alert
✗ Mark an alert GREEN
✗ Mark an alert RED
✗ Escalate an alert
✗ Modify authority decisions
✗ Access authority-only information
✗ Change the alert workflow
```

The viewer is strictly **read-only**.

---

# 55. LOGIN TYPE 2 — AUTHORITY

## Role

```text
AUTHORITY
```

Authority users have an assigned tier:

```text
TIER 1
TIER 2
TIER 3
```

The login system must know:

```text
user
    ↓
role = authority
    ↓
tier = 1 / 2 / 3
```

Authority permissions are determined by the user's tier.

---

# 56. AUTHORITY TIER 1

## Purpose

Tier 1 is responsible for **first-level verification**.

Tier 1 receives newly generated alerts that require human verification.

### Tier 1 can:

```text
✓ View Tier 1 pending alerts
✓ Open event details
✓ View FIRMS evidence
✓ View AI classification
✓ View confidence
✓ View risk score
✓ View satellite/context information
✓ View OSM facility information
✓ View historical activity
✓ Add verification comments
✓ Mark GREEN
✓ Mark RED
```

### Tier 1 cannot:

```text
✗ Directly approve Tier 2 cases
✗ Modify Tier 2 decisions
✗ Modify Tier 3 decisions
✗ Change AI predictions
✗ Change historical FIRMS data
```

---

# 57. TIER 1 DECISION

Tier 1 receives:

```text
NEW ALERT
     ↓
TIER 1 REVIEW
```

The authority sees all evidence and chooses:

```text
GREEN
```

or:

```text
RED
```

### GREEN

```text
Tier 1
  ↓
GREEN
  ↓
Alert resolved / monitoring
```

### RED

```text
Tier 1
  ↓
RED
  ↓
Tier 2 queue
```

The system automatically changes:

```text
current_tier = 2
status = TIER_2_PENDING
```

Tier 1 does not manually forward the case.

---

# 58. AUTHORITY TIER 2

## Purpose

Tier 2 performs **second-level verification** for alerts escalated by Tier 1.

Tier 2 sees the complete history.

```text
FIRMS
 ↓
AI
 ↓
Risk
 ↓
Tier 1 decision
 ↓
Tier 2 review
```

### Tier 2 can:

```text
✓ View Tier 2 pending alerts
✓ View all event evidence
✓ View Tier 1 decision
✓ View Tier 1 comments
✓ View AI analysis
✓ View facility information
✓ View historical activity
✓ Add comments
✓ Mark GREEN
✓ Mark RED
```

### Tier 2 cannot:

```text
✗ Modify Tier 1's original decision
✗ Modify FIRMS data
✗ Modify AI prediction
✗ Modify Tier 3 decisions
```

---

# 59. TIER 2 DECISION

### GREEN

```text
Tier 1 RED
     ↓
Tier 2 REVIEW
     ↓
GREEN
     ↓
DE-ESCALATE
```

The system records:

```text
TIER_2_VERIFIED
```

The alert can move into monitoring/resolved state.

### RED

```text
Tier 1 RED
     ↓
Tier 2 RED
     ↓
Tier 3
```

The backend automatically creates the Tier 3 escalation.

```text
current_tier = 3
status = TIER_3_PENDING
```

---

# 60. AUTHORITY TIER 3 — NATIONAL

## Purpose

Tier 3 handles cases that have been confirmed/escalated through the previous authority levels.

Tier 3 is the highest level in the prototype workflow.

### Tier 3 can:

```text
✓ View Tier 3 escalations
✓ View complete alert history
✓ View Tier 1 decision
✓ View Tier 2 decision
✓ View all evidence
✓ View AI analysis
✓ View risk/anomaly information
✓ Add national-level comments
✓ Mark case as reviewed
✓ Mark final disposition
```

For the prototype, Tier 3 can use:

```text
REVIEWED
```

or a final disposition such as:

```text
CONFIRMED
DISMISSED
RESOLVED
```

Do not claim that this automatically dispatches real national emergency resources unless such integrations actually exist.

---

# 61. AUTHORITY PERMISSION MATRIX

| Capability | Viewer | Tier 1 | Tier 2 | Tier 3 |
|---|---:|---:|---:|---:|
| View map | ✓ | ✓ | ✓ | ✓ |
| View FIRMS events | ✓ | ✓ | ✓ | ✓ |
| View AI classification | ✓ | ✓ | ✓ | ✓ |
| View risk score | ✓ | ✓ | ✓ | ✓ |
| View facility information | ✓ | ✓ | ✓ | ✓ |
| View history | ✓ | ✓ | ✓ | ✓ |
| View alerts | ✓ | ✓ | ✓ | ✓ |
| Verify Tier 1 | ✗ | ✓ | ✗ | ✗ |
| Verify Tier 2 | ✗ | ✗ | ✓ | ✗ |
| Review Tier 3 | ✗ | ✗ | ✗ | ✓ |
| GREEN decision | ✗ | ✓ | ✓ | appropriate final disposition |
| RED decision | ✗ | ✓ | ✓ | N/A |
| Escalate | ✗ | automatic | automatic | N/A |
| Modify AI prediction | ✗ | ✗ | ✗ | ✗ |
| Modify FIRMS data | ✗ | ✗ | ✗ | ✗ |
| View audit history | limited | ✓ | ✓ | ✓ |

**Important:** Escalation should be performed by the **backend state machine**, not manually by an authority user.

---

# 62. LOGIN / AUTHENTICATION FLOW

The login page should provide:

```text
┌───────────────────────────────────────────┐
│          THERMAL INTELLIGENCE             │
│                                           │
│ Email / Username                          │
│ [____________________________]            │
│                                           │
│ Password                                  │
│ [____________________________]            │
│                                           │
│              [ LOGIN ]                    │
│                                           │
└───────────────────────────────────────────┘
```

The system determines the user's role after authentication.

Example:

```text
user
 ↓
authentication
 ↓
JWT
 ↓
role
 ↓
permissions
```

The UI then changes according to the role.

---

# 63. VIEWER DASHBOARD

After viewer login:

```text
┌─────────────────────────────────────────────┐
│ THERMAL INTELLIGENCE          Viewer        │
├─────────────────────────────────────────────┤
│                                             │
│ Dashboard                                   │
│ Thermal Map                                 │
│ Events                                      │
│ Facilities                                  │
│ Analytics                                   │
│                                             │
│ Alert status: READ ONLY                     │
│                                             │
└─────────────────────────────────────────────┘
```

No verification buttons should be shown.

For example, the viewer can see:

```text
Alert #92841

Industrial Fire
Risk: 87/100
Status: Tier 2 Pending
```

But cannot see:

```text
[ GREEN ]
[ RED ]
```

---

# 64. AUTHORITY DASHBOARD

After authority login:

```text
┌─────────────────────────────────────────────┐
│ THERMAL INTELLIGENCE          Tier 1        │
├─────────────────────────────────────────────┤
│                                             │
│ Dashboard                                   │
│ Thermal Map                                 │
│ My Pending Alerts                           │
│ Alert History                               │
│ Facilities                                  │
│                                             │
│ 🔴 5 Pending Verification                  │
└─────────────────────────────────────────────┘
```

The authority sees a dedicated:

```text
MY PENDING ALERTS
```

section.

---

# 65. AUTHORITY ALERT SCREEN

Example:

```text
┌──────────────────────────────────────────────┐
│ ALERT #92841                                 │
│ TIER 1 VERIFICATION REQUIRED                 │
├──────────────────────────────────────────────┤
│                                              │
│ Classification: INDUSTRIAL FIRE             │
│ AI Confidence: 94.2%                         │
│ Risk: 87/100 — CRITICAL                      │
│                                              │
│ Facility: XYZ Petrochemical Complex          │
│ Distance: 76m                                │
│ FRP: 184 MW                                  │
│                                              │
│ ─────────── AI EVIDENCE ───────────          │
│ ✓ High thermal intensity                     │
│ ✓ Industrial facility nearby                 │
│ ✓ Persistent activity                        │
│ ✓ Abnormal facility baseline                 │
│                                              │
│ ───────── VERIFICATION ──────────            │
│                                              │
│ Comments                                     │
│ [______________________________________]     │
│                                              │
│ [ GREEN — VERIFIED ] [ RED — ESCALATE ]      │
└──────────────────────────────────────────────┘
```

---

# 66. ALERT AUDIT TRAIL

Every authority action must be recorded.

Example:

```text
ALERT #92841

14:32  FIRMS detected thermal anomaly
14:33  AI classified as Industrial Fire
14:33  Risk calculated: 87/100

15:02  Tier 1 opened case
15:08  Tier 1 → RED
       Comment: Confirmed abnormal activity

15:08  System escalated to Tier 2

16:11  Tier 2 opened case
16:18  Tier 2 → RED
       Comment: Secondary verification confirmed

16:18  System escalated to Tier 3

PENDING NATIONAL REVIEW
```

This is extremely useful for demonstrating **accountability and traceability**.

---

# 67. AUTHENTICATION DATABASE MODEL

For the prototype:

```text
users
-----
id
username
password_hash
role
tier
created_at
```

Possible values:

```text
role:
viewer
authority
```

For authority:

```text
tier:
1
2
3
```

For viewer:

```text
tier:
NULL
```

Example:

```json
{
  "username": "tier1_demo",
  "role": "authority",
  "tier": 1
}
```

---

# 68. SECURITY REQUIREMENTS

Passwords must **never be stored as plaintext**.

Use:

```text
password
   ↓
Argon2 / bcrypt
   ↓
password_hash
```

Authentication should use:

```text
JWT access token
```

The frontend should not decide whether a user has permission to perform an action.

For example, hiding the RED button is NOT security.

The backend must enforce:

```text
POST /api/alerts/{id}/verify
        ↓
authenticate JWT
        ↓
check role
        ↓
check authority tier
        ↓
check alert's current tier
        ↓
allow / reject
```

---

# 69. AUTHORIZATION EXAMPLES

## Example 1

Tier 1 tries to modify a Tier 2 case:

```text
Tier 1
 ↓
Tier 2 alert
 ↓
403 FORBIDDEN
```

---

## Example 2

Viewer tries to verify:

```text
Viewer
 ↓
POST /api/alerts/92841/verify
 ↓
403 FORBIDDEN
```

---

## Example 3

Tier 2 tries to verify Tier 1:

```text
Tier 2
 ↓
Tier 1 alert
 ↓
403 FORBIDDEN
```

---

## Example 4

Tier 1 verifies Tier 1:

```text
Tier 1
 ↓
Tier 1 pending alert
 ↓
GREEN / RED
 ↓
200 OK
```

---

# 70. Backend Authorization Logic

Conceptually:

```python
if user.role != "authority":
    deny()

if user.tier != alert.current_tier:
    deny()

if alert.status != "PENDING":
    deny()

allow_verification()
```

Then:

```python
if decision == "green":
    resolve_or_monitor(alert)

elif decision == "red":
    escalate_to_next_tier(alert)
```

The **backend owns the state transition**.

The frontend only sends the decision.

---

# 71. Demo Accounts

For the prototype, create clearly labeled demo accounts.

```text
VIEWER
username: viewer_demo

TIER 1
username: tier1_demo

TIER 2
username: tier2_demo

TIER 3
username: tier3_demo
```

Use secure demo passwords stored outside the repository or in environment variables.

Do NOT commit real credentials.

---

# 72. Demo Authentication Flow

The presentation should demonstrate all four perspectives.

## Step 1 — Viewer

Login:

```text
viewer_demo
```

Show:

```text
GIS Map
Events
AI analysis
Risk
```

Then show:

> Viewer cannot modify the alert.

---

## Step 2 — Tier 1

Login:

```text
tier1_demo
```

Show:

```text
5 alerts pending verification
```

Open an alert.

Click:

```text
RED
```

---

## Step 3 — Tier 2

Login:

```text
tier2_demo
```

The same alert now appears:

```text
Tier 2 Verification Required
```

Show the complete Tier 1 history.

Click:

```text
RED
```

---

## Step 4 — Tier 3

Login:

```text
tier3_demo
```

Show:

```text
NATIONAL ESCALATION
```

The entire chain is visible:

```text
FIRMS
 ↓
AI
 ↓
Tier 1 RED
 ↓
Tier 2 RED
 ↓
Tier 3
```

This is a very strong demonstration of the complete workflow.

---

# 73. Updated Responsibility Allocation

## SARVESH — `AI-CORE`

Add:

```text
AI triage
risk scoring
classification
AI explanation
alert creation criteria
```

---

## ARHAM — `AI-MODEL`

Add:

```text
anomaly detection
severity modeling
historical baseline
model evaluation
false-positive analysis
```

---

## ANWAY — `BACKEND-API`

**Owns the authentication and authorization backend.**

Add:

```text
users table
JWT authentication
password hashing
RBAC middleware
alert state machine
authority verification APIs
audit trail
```

Endpoints:

```text
POST /api/auth/login

GET  /api/me

GET  /api/alerts
GET  /api/alerts/{id}

POST /api/alerts/{id}/verify
GET  /api/alerts/{id}/history
```

---

## YASH — `GIS-OSM`

Add:

```text
facility location
administrative context
alert geometry
facility impact context
```

---

## SEJAL — `FRONTEND-GIS`

Add:

```text
login page
viewer dashboard
authority dashboard
role-based navigation
alert verification UI
tier indicators
alert history
```

---

## SAMIKSHA — `UI-INTEGRATION`

Add:

```text
authentication UX
authority workflow UX
demo accounts
escalation scenarios
end-to-end authentication testing
presentation flow
```

---

# 74. Updated Product Flow

The final product is now:

```text
                     USER LOGIN
                         │
              ┌──────────┴──────────┐
              │                     │
           VIEWER                AUTHORITY
              │                     │
        READ-ONLY               TIER 1/2/3
              │                     │
              └──────────┬──────────┘
                         │
                         ▼
                  GIS DASHBOARD
                         │
                         ▼
                   FIRMS EVENT
                         │
                         ▼
                 AI CLASSIFICATION
                         │
                         ▼
                   RISK ANALYSIS
                         │
                         ▼
                 ALERT TRIAGE
                         │
                         ▼
                 ┌───────────────┐
                 │    TIER 1     │
                 │  Verification │
                 └───────┬───────┘
                         │
                   GREEN / RED
                         │
                    RED ONLY
                         ▼
                 ┌───────────────┐
                 │    TIER 2     │
                 │  Verification │
                 └───────┬───────┘
                         │
                   GREEN / RED
                         │
                    RED ONLY
                         ▼
                 ┌───────────────┐
                 │    TIER 3     │
                 │    NATIONAL   │
                 └───────────────┘
                         │
                         ▼
                    AUDIT TRAIL
```

This should now be considered part of the **core architecture**, not an optional feature.
