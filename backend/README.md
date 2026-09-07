# THERMOS — Backend API Service

> **SIH 2026 Problem Statement 26162**
>
> **Role:** `BACKEND-API` (Anway)
>
> **Technology:** Python 3.11+ / FastAPI / SQLAlchemy / SQLite (prototype) / PostgreSQL + PostGIS (production ready)

---

## Overview

The `BACKEND-API` service acts as the central integration layer and database authority for **THERMOS** (Thermal Hazard Intelligence & Response System). It bridges data from NASA FIRMS, OpenStreetMap (OSM) GIS processing, and AI/ML classification models, exposing clean, high-performance RESTful APIs to the frontend GIS dashboard.

---

## Architecture & Responsibilities

```text
NASA FIRMS / GIS / AI Models
             ↓
        BACKEND API (FastAPI)
             ↓
     Frontend GIS Dashboard
```

### Key Capabilities:
- **Thermal Event Intelligence:** Ingests and stores thermal anomaly records, returning enriched details (FRP, brightness temperature, satellite metadata, facility proximity, temporal persistence).
- **Industrial Facility Registry:** Manages plant boundaries, facility types (refineries, petrochemical, steel plants, power plants, mines, etc.), coordinates, and baseline historical activity.
- **AI Prediction Pipeline Interface:** Integrates with Sarvesh and Arham's ML inference models, generating predictions with confidence scores, risk evaluations (0–100), severity levels (`low`, `moderate`, `high`, `critical`), and explainable evidence chains.
- **Dashboard Analytics Engine:** Computes real-time aggregation of thermal hazards and persistent anomalies.
- **Robust Mock-First Fallback:** Ships with curated demo datasets for 4 primary SIH presentation scenarios.

---

## Implemented API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `GET` | `/api/events` | List all thermal events (supports `classification`, `risk_level`, `facility_id` filtering) |
| `GET` | `/api/events/{event_id}` | Retrieve complete 4-tier event intelligence (`event`, `prediction`, `facility`, `temporal`) |
| `GET` | `/api/facilities` | List all industrial facilities for GIS map overlays |
| `GET` | `/api/facilities/{facility_id}` | Detailed facility intelligence with historical activity & baseline deviation |
| `GET` | `/api/analytics` | Dashboard summary cards statistics (`total_events`, `industrial_events`, `critical_events`, `persistent_sources`) |
| `POST` | `/api/predict` | Request AI prediction & risk score for an event (`{"event_id": "FIRMS_001"}`) |

Interactive OpenAPI documentation is automatically served at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## Directory Structure

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── thermal_event.py
│   │   ├── facility.py
│   │   └── prediction.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── thermal_event.py
│   │   ├── facility.py
│   │   ├── prediction.py
│   │   └── analytics.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── events.py
│   │   ├── facilities.py
│   │   ├── analytics.py
│   │   └── prediction.py
│   └── services/
│       ├── __init__.py
│       ├── event_service.py
│       ├── facility_service.py
│       ├── prediction_service.py
│       └── analytics_service.py
├── data/
│   └── demo/
│       ├── events.json
│       ├── facilities.json
│       ├── predictions.json
│       └── analytics.json
├── scripts/
│   └── seed_demo.py
├── tests/
│   ├── __init__.py
│   └── test_api.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup & Running Locally

### 1. Create and activate a Python virtual environment

```bash
cd backend

# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Default configuration (`sqlite:///./thermos.db`) allows immediate plug-and-play operation. To use PostgreSQL / PostGIS, set `DATABASE_URL` in `.env`:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/thermos_db
```

### 4. Seed Demo Data

To manually populate or reset the database with the SIH demo scenarios:

```bash
python scripts/seed_demo.py
```

*(Note: The server also auto-seeds on initial launch if empty.)*

### 5. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

---

## Running Automated Tests

To execute the full API test suite:

```bash
pytest
```

---

## Machine-Readable Classification Labels

All predictions output exact machine-readable labels as specified in `updated_MASTER.md`:
- `industrial_fire`
- `persistent_industrial_source`
- `gas_flare`
- `wildfire`
- `agricultural_fire`
- `unknown`

---

## Integration Notes for Teammates

### For Sejal (`FRONTEND-GIS`) & Samiksha (`UI-INTEGRATION`)
- Set API base URL to `http://localhost:8000`.
- Call `GET /api/events` to populate map markers for active hotspots.
- Call `GET /api/facilities` to render industrial facility boundaries.
- On user click of a hotspot, call `GET /api/events/{id}` to populate the side panel with AI explanation, facility proximity, and temporal surge stats.
- Call `GET /api/analytics` for top header cards.

### For Sarvesh (`AI-CORE`) & Arham (`AI-MODEL`)
- Connect model inference to `PredictionService._run_inference_rules(event)` in `app/services/prediction_service.py` by swapping with `predict(event)`.
- Input fields provided from DB: `frp`, `brightness_temperature`, `confidence`, `distance_to_facility_m`, `persistence_score`, `detections_24h`, `ndvi`, `ndbi`, `facility_type`.

### For Yash (`GIS-OSM`)
- Facility data from OSM can be formatted using `backend/data/demo/facilities.json` structure and loaded into the `facilities` DB table.
