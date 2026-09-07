# THERMOS — Thermal Hazard Intelligence & Response System

> **Smart India Hackathon 2026 — Problem Statement 26162**
>
> **Project:** AI-Based Detection and Classification of Industrial Fires and Persistent Thermal Sources Using NASA FIRMS, OSM & Satellite Data
>
> **Team:** Sarvesh (`AI-CORE`), Anway (`BACKEND-API`), Yash (`GIS-OSM`), Arham (`AI-MODEL`), Sejal (`FRONTEND-GIS`), Samiksha (`UI-INTEGRATION`)

---

## 1. System Overview

**THERMOS** is an AI-powered geospatial thermal intelligence platform designed to bridge satellite thermal anomaly observations from NASA FIRMS with industrial facility context (OSM, WRI, GEM), environmental land-cover indices (NDVI, NDBI), and temporal persistence analysis.

Instead of displaying raw hotspots, THERMOS performs multi-evidence fusion to answer operational intelligence questions:
1. **Detection:** Where is the thermal anomaly located?
2. **Attribution:** Is it near an industrial facility, power plant, refinery, or forest canopy?
3. **Behavioral Intelligence:** How has this location/facility behaved historically?
4. **Classification & Risk:** Is today's thermal behavior normal or an acute industrial hazard?

---

## 2. End-to-End System Architecture

```text
               ┌────────────────────────────────────────┐
               │    NASA FIRMS (VIIRS 375m / MODIS)     │
               └───────────────────┬────────────────────┘
                                   │ Thermal Anomalies
                                   ▼
               ┌────────────────────────────────────────┐
               │   Spatial & Temporal Enrichment        │
               │   • OSM / WRI / GEM Facilities         │
               │   • Haversine & BallTree Distance      │
               │   • Land-Cover Context (NDVI / NDBI)  │
               │   • Temporal Persistence (24h/7d)      │
               └───────────────────┬────────────────────┘
                                   │ Enriched Event Features
                                   ▼
               ┌────────────────────────────────────────┐
               │     ML / AI Classification Engine      │
               │   • Machine-Readable Classifiers      │
               │   • Risk Evaluation Score (0 - 100)    │
               │   • Grounded Evidence Explanations     │
               └───────────────────┬────────────────────┘
                                   │ Prediction & Risk Outputs
                                   ▼
               ┌────────────────────────────────────────┐
               │     FastAPI Integration Backend        │
               │   • /api/events & /api/events/{id}     │
               │   • /api/facilities & /api/facilities/{id}
               │   • /api/analytics & /api/predict      │
               └───────────────────┬────────────────────┘
                                   │ REST JSON APIs
                                   ▼
               ┌────────────────────────────────────────┐
               │     React + Leaflet GIS Dashboard      │
               │   • Interactive Thermal Hotspot Map    │
               │   • Priority Event Intelligence Panel  │
               │   • Regional Alerts & Simulation Mode  │
               └────────────────────────────────────────┘
```

---

## 3. Project Structure

```text
sih-2026-sk/
├── backend/                  # FastAPI integration backend service
│   ├── app/
│   │   ├── main.py           # FastAPI application entry point & auto-seeder
│   │   ├── config.py         # Application configuration & CORS settings
│   │   ├── database.py       # SQLAlchemy engine & session manager
│   │   ├── models/           # SQLAlchemy ORM models (ThermalEvent, Facility, Prediction)
│   │   ├── schemas/          # Pydantic V2 validation schemas
│   │   ├── routes/           # REST API routes (/api/events, /api/facilities, /api/analytics, /api/predict)
│   │   └── services/         # Business logic layer & ML pipeline connector
│   ├── data/demo/            # Canonical demo JSON datasets
│   ├── scripts/seed_demo.py  # Standalone database seeder script
│   ├── tests/test_api.py     # Backend Pytest test suite
│   ├── requirements.txt      # Backend Python dependencies
│   └── README.md             # Backend setup documentation
│
├── ml/                       # Modular Machine Learning pipeline package
│   ├── predict.py            # Main entrypoint: predict(event_dict)
│   ├── inference/pipeline.py # High-level inference pipeline
│   ├── features/             # Feature extraction & normalization
│   ├── models/               # Classifiers, Risk Scorer, Anomaly Engine
│   ├── explainability/       # Grounded evidence explanation generator
│   └── schemas.py            # Pydantic data schemas
│
├── Trained Model/            # Offline training experiments & artifacts
│   ├── pipeline.py           # BallTree spatial join & model training pipeline
│   └── artifacts_output/     # Trained XGBoost models (.joblib), CSVs & evaluation charts
│
├── frontend/                 # React + TypeScript + Vite GIS Dashboard
│   ├── src/
│   │   ├── App.tsx           # Dashboard, Leaflet Map, Event Intelligence & Regional Alerts
│   │   └── App.css           # Styling & theme variables
│   ├── package.json          # Node dependencies & scripts
│   └── README.md             # Frontend documentation
│
├── MASTER.md                 # Original project execution contract
├── updated_MASTER.md         # Updated team interface specifications
├── .env.example              # Environment variables template
├── .gitignore                # Version control ignore rules
└── README.md                 # Main repository documentation
```

---

## 4. Machine-Readable Classification Contract

All ML models and Backend APIs conform to these canonical machine-readable labels:

| Label | Description |
|---|---|
| `industrial_fire` | Acute thermal hazard at or near industrial infrastructure |
| `persistent_industrial_source` | Stable, recurring industrial heat signature with high persistence score |
| `gas_flare` | Controlled flare stack operations at refineries or petrochemical plants |
| `wildfire` | Natural vegetation fire in forest / wildland areas |
| `agricultural_fire` | Seasonal crop residue / stubble burning |
| `unknown` | Low-context thermal anomaly requiring further inspection |

---

## 5. Quick Start Guide

### 1. Start the Backend API

```bash
# Navigate to backend directory
cd backend

# Activate Python virtual environment (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database seeder (Optional - main.py auto-seeds if DB is empty)
python scripts/seed_demo.py

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- **API Server:** `http://localhost:8000`
- **Interactive Swagger Docs:** `http://localhost:8000/docs`
- **ReDoc Documentation:** `http://localhost:8000/redoc`

### 2. Start the Frontend GIS Dashboard

```bash
# Open a new terminal and navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```
- **GIS Dashboard UI:** `http://localhost:5173`

---

## 6. Running Tests

### Backend Automated Test Suite
```bash
# From backend directory
.venv\Scripts\pytest.exe backend/tests
```
*Result:* **10/10 passed**

### Frontend Production Build Test
```bash
# From frontend directory
npm run build
```
*Result:* **Built cleanly with 0 TypeScript/Vite errors**

---

## 7. Supported Presentation Demo Scenarios

1. **Scenario 1 — Industrial Fire (Centerpiece):** Hotspot `FIRMS_001` at Dahej Petrochemical Complex (`FAC_001`), FRP 184.5 MW, 76.4m distance. Classified as `industrial_fire`, Risk Score 87/100 (CRITICAL).
2. **Scenario 2 — Wildfire (Comparison):** Hotspot `FIRMS_002` in Gir Forest edge (NDVI 0.74, >6km from industry). Classified as `wildfire`, Risk Score 62/100 (HIGH).
3. **Scenario 3 — Persistent Industrial Source:** Hotspot `FIRMS_003` at Jamnagar Refinery (`FAC_002`), high persistence score (0.92). Classified as `persistent_industrial_source`, Risk Score 35/100 (MODERATE).
4. **Scenario 4 — Abnormal Facility Activity:** Hotspot `FIRMS_004` at Hazira Steel Plant (`FAC_003`), 14 detections in 24h vs baseline 2. Classified as `industrial_fire`, Risk Score 92/100 (CRITICAL).
