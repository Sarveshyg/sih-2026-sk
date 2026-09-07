# AI Core — SIH 2026 / Problem 26162

> **Status: Prototype baseline classifier (NOT a trained production ML model).**
> AI provides detection, classification, prioritization and evidence aggregation. Human authorities make final decisions.

---

## 1. Architecture

```
EnrichedEvent (dict / Pydantic)
    ↓ Validation (schemas.py)
    ↓ Feature Engineering (features/engineering.py)
    ↓ Classification (models/classifier.py — BaselineClassifier)
    ↓ Risk Scoring (models/risk.py — RiskScorer, independent)
    ↓ Anomaly (models/anomaly.py)
    ↓ Triage (config thresholds)
    ↓ Explanation (explainability/explanation.py)
    ↓ PredictionOutput
```

Interface-first: `BaseClassifier` can be replaced with XGBoost/RF without touching pipeline or backend.

```
ml/
├── config.py               # prototype thresholds (documented, not government values)
├── schemas.py              # ThermalEvent / EnrichedEvent / PredictionOutput
├── features/engineering.py # deterministic FeatureVector, no future leakage
├── models/
│   ├── classifier.py       # BaselineClassifier (deterministic rules)
│   ├── risk.py             # independent 0-100 scorer
│   └── anomaly.py          # (current-baseline)/baseline
├── data/                   # FIRMS ingestion (firms_*.py + pipeline.py)
├── geospatial/             # enrichment (facility/landcover/temporal/enrichment.py)
├── explainability/explanation.py
├── inference/pipeline.py   # InferencePipeline + predict()
├── predict.py              # top-level alias for backend
├── requirements.txt
└── tests/
    ├── test_pipeline.py
    ├── test_firms_data.py
    └── test_geospatial_enrichment.py
```

---

## 2. Input Schema

### ThermalEvent (MASTER §6.1)

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

### EnrichedEvent (MASTER §7) — all contextual fields are OPTIONAL

```json
{
  "distance_to_facility_m": 76.4,
  "distance_to_industry": 76.4,
  "distance_to_forest_m": 300,
  "distance_to_agriculture_m": 1200,
  "facility_type": "refinery",
  "nearest_facility_id": "FAC_001",
  "persistence_score": 0.84,
  "detections_24h": 5,
  "detections_7d": 18,
  "detections_30d": 40,
  "ndvi": 0.12,
  "ndbi": 0.68,
  "hotspot_cluster_size": 1,
  "facility_baseline": 2,
  "current_activity": 14,
  "inside_industrial_area": true
}
```

Missing fields are handled with neutral defaults — pipeline never crashes.

Aliases supported:
- `distance_to_industry` ↔ `distance_to_facility_m`
- `persistent_industrial_source` ↔ `persistent_industrial_thermal_source`

---

## 3. Feature List

| Group | Features |
|-------|----------|
| Thermal | `frp`, `brightness_temperature`, `firms_confidence`, normalised `frp_norm`/`bt_norm` |
| Spatial | `distance_to_facility_m`, `distance_to_forest_m`, `distance_to_agriculture_m`, `facility_type`, `inside_industrial_area`, `is_flare_facility` |
| Temporal | `persistence_score` (0-1), `detections_24h/7d/30d`, `hotspot_cluster_size` |
| Land-cover | `ndvi` (-1 to 1), `ndbi` (-1 to 1) |
| Anomaly | `(current-baseline)/baseline`, `current/baseline` ratio |

No data leakage: only fields present at prediction time are used; no future observations.

---

## 4. Classification

### Labels (canonical)

```
industrial_fire
persistent_industrial_thermal_source
gas_flare
wildfire
agricultural_fire
unknown
```

`persistent_industrial_source` is accepted as alias and canonicalised.

### BaselineClassifier (prototype)

Deterministic scoring per class — **clearly labelled baseline/prototype, NOT a trained model**:

- High industrial likelihood: close to industrial facility, matching `facility_type`, high FRP, persistence, high NDBI, low NDVI
- Wildfire: close to forest, high NDVI, clustered hotspots, no nearby industry
- Agricultural: agri land nearby, temporary persistence, low industrial proximity
- Gas flare: `refinery`/`oil`/`gas` facility, persistent, suitable FRP band
- Unknown: fallback when all scores <0.8 or no contextual evidence

Returns `classification` + `confidence` (0–1). Confidence is share + gap normalised and blended with FIRMS confidence.

> To replace with a trained model: implement `BaseClassifier.predict(FeatureVector)->(label, confidence)` and inject into `InferencePipeline(classifier=YourModel())`.

---

## 5. Risk Scoring

- Range `0–100` int
- Levels: `LOW` (0-29), `MODERATE` (30-49), `HIGH` (50-74), `CRITICAL` (75-100)
- Independent from classification
- Factors: FRP/BT/FIRMS confidence, industrial proximity + facility criticality, persistence, anomaly ratio, cluster size, classification adjustment (small)

Example:
- `industrial_fire + low FRP + isolated → MODERATE`
- `industrial_fire + very high FRP + persistent + anomaly + near population → CRITICAL`

---

## 6. Triage Logic (prototype, NOT official thresholds)

```python
risk >= 75  →  triage_required=True,  recommended_tier=1  (Tier 1 alert)
risk 50-74  →  triage_required=False, recommended_tier=None (monitoring)
risk < 50   →  triage_required=False, recommended_tier=None (store only)
```

AI **recommends** alert creation; backend owns the state machine and authority workflow. See `ml/config.py:TRIAGE_TIER1_RISK`.

---

## 7. Prediction Output

```json
{
  "event_id": "FIRMS_001",
  "classification": "industrial_fire",
  "confidence": 0.942,
  "risk_score": 87,
  "risk_level": "CRITICAL",
  "recommended_tier": 1,
  "triage_required": true,
  "explanation": [
    "Very high thermal intensity (FRP 184.0 MW)",
    "Thermal anomaly is 76m from an industrial facility — very close proximity",
    "Thermal activity has persisted across multiple detections (high persistence)",
    "Current activity is 7.0x the facility baseline — highly anomalous"
  ],
  "anomaly_ratio": 7.0,
  "persistence_score": 0.84,
  "model_version": "baseline-v0"
}
```

Typed internally as `PredictionOutput` (Pydantic).

---

## 8. How to Run Tests

```bash
pip install -r ml/requirements.txt
pytest ml/tests -v
# or
python -m pytest ml/tests -v
```

Tests cover 6 synthetic scenarios (A–F) plus contract/missing-field/triage checks.

---

## 9. How Backend Can Call the Pipeline

### Option A — dict in / dict out (recommended for FastAPI)

```python
from ml.inference.pipeline import predict

enriched_event = {
    "id": "FIRMS_001",
    "latitude": 19.076,
    "longitude": 72.877,
    "frp": 124.5,
    "brightness_temperature": 341.2,
    "confidence": 87,
    "timestamp": "2026-09-06T10:30:00Z",
    "satellite": "VIIRS",
    "distance_to_facility_m": 76.4,
    "facility_type": "refinery",
    "persistence_score": 0.84,
    "detections_7d": 18,
    "ndvi": 0.12,
    "ndbi": 0.68,
}
result: dict = predict(enriched_event)
# result contains classification, confidence, risk_score, etc.
```

### Option B — singleton pipeline

```python
from ml.inference.pipeline import get_pipeline
from ml.schemas import EnrichedEvent

pipeline = get_pipeline()
event = EnrichedEvent(**enriched_event)  # validated
result = pipeline.predict_typed(event)   # -> PredictionOutput
print(result.model_dump())
```

### Option C — inject a trained model later

```python
from ml.inference.pipeline import InferencePipeline
from ml.models.classifier import BaseClassifier

class MyXGBoostClassifier(BaseClassifier):
    def predict(self, fv): ...

pipeline = InferencePipeline(classifier=MyXGBoostClassifier())
```

No coupling to FastAPI, React, PostGIS, or frontend.

---

## 10. Model Maturity — Honest Statement

- **Current: `Prototype baseline classifier` (`baseline-v0`)**
- No trained XGBoost/RF/CNN is bundled yet
- Rules are hand-crafted from domain heuristics for demo separability
- Arham (`AI-MODEL`) will own: training dataset, XGBoost/RF/LogReg comparison, metrics (accuracy/precision/recall/F1/confusion matrix), feature importance, anomaly modelling
- Do NOT claim “94.2% accurate production AI” — report metrics only after evaluation on a held-out labelled set

---

## 11. Facility Anomaly Example

```
baseline = 2 detections/day
current  = 14 detections/day
anomaly  = (14-2)/2 = 6  →  600% increase
ratio    = 7.0x
```

This strongly boosts both `industrial_fire` evidence and `risk_score`, and appears verbatim in `explanation`.

---

## 12. Integration Contracts

- `ml/schemas.py` is the source of truth for JSON contracts
- GIS (Yash) provides: `distance_to_facility_m`, `facility_type`, `ndvi/ndbi`, `persistence_score`, `detections_*`
- Backend (Anway) calls `predict()` and persists `PredictionOutput`
- Frontend (Sejal) displays `classification`, `confidence`, `risk_score/level`, `explanation`

All modules use `JSON / Pydantic` in → `AI Core` → `JSON / Pydantic` out.

---

## 13. FIRMS Data Ingestion Pipeline

> **The repository does not contain NASA FIRMS data.**
> Users must obtain FIRMS data from NASA and provide the local file.
> All test fixtures are synthetic test data, NOT NASA data.

### 13.1 Supported FIRMS Formats

The loader supports real FIRMS CSV exports (VIIRS 375m/750m, MODIS 1km) including variants:

```
latitude, longitude, bright_ti4, bright_ti5, scan, track,
acq_date, acq_time, satellite, instrument, confidence, version,
bright_t31, frp, daynight
```

Variant handling (case-insensitive, stripped):

| Canonical | Aliases |
|-----------|---------|
| `latitude` | `lat`, `y` |
| `longitude` | `lon`, `long`, `lng`, `x` |
| `frp` | `fire_radiative_power`, `power` |
| `bright_ti4` | `bright_t4`, `ti4` |
| `bright_ti5` | `ti5` |
| `bright_t31` | `t31` |
| `brightness_temperature` | `brightness`, `bt`, `bright_temp` |
| `confidence` | `conf`, `conf_a` |
| `acq_date`/`acq_time` | `date`, `time`, `acq_datetime`, `timestamp`, `datetime` |
| `satellite` | `sat` |
| `instrument` | `sensor` |

Unknown columns are preserved in cleaned event `_raw_extra` but not required for AI Core.

### 13.2 Normalization Rules

**Brightness temperature** — priority `bright_ti4 → bright_ti5 → bright_t31 → brightness_temperature`.
Documented choice: `bright_ti4` (VIIRS I4 ~3.7µm) is primary fire channel per NASA FIRMS docs; MODIS fallback uses `bright_t31`. Source stored in `_bt_source` for audit.

**Confidence** — normalized to `0–100` float:
- VIIRS/MODIS categorical: `l→30`, `n→60`, `h→90` (case-insensitive)
- Numeric `0–100` preserved; `0–1` scaled ×100 (heuristic for alternate exports)
- Out-of-range `>100` or `<0` rejected as invalid (not silently clamped)

**Timestamp** — `acq_date` (`YYYY-MM-DD` or `YYYY/MM/DD`) + `acq_time` (`HHMM` like `1342` = 13:42 UTC, or `HH:MM`) → UTC-aware `YYYY-MM-DDTHH:MM:SSZ`. Also accepts ISO `acq_datetime`/`timestamp` values (`...Z` or `+00:00`). Conversion documented in `ml/data/firms_cleaner.py:_parse_timestamp`.

**Satellite** — derived from `satellite` else `instrument`; normalized upper-case. Examples: `VIIRS` (generic), `NOAA-20`, `NOAA-21`, `MODIS_TERRA` (from `Terra`), `MODIS_AQUA` (from `Aqua`), `MODIS`. Defaults to `VIIRS` if absent (logged, not fatal).

**ID** — deterministic `FIRMS_<8HEX>` = `SHA1(satellite|timestampISO|lat:.5f|lon:.5f)` truncated. Same input → same ID across runs.

### 13.3 Cleaning Rules

- **Coordinates:** reject `lat < -90 or >90`, `lon < -180 or >180`. Globally usable — no India bounding box in generic loader.
- **Numeric:** `frp`/`brightness_temperature`/`confidence` parsed as float; missing/malformed/`NaN`/negative `frp` → invalid row (not replaced with 0). `bt` out-of-range `>1000` or `<100` rejected; `200–600K` considered plausible with warning flag.
- **Timestamp:** malformed `acq_date`/`acq_time` → invalid row.
- Do not fabricate missing values.

### 13.4 Deduplication

Dedup key = `(satellite, timestamp_minute, round(lat,4), round(lon,4))`.

- Same satellite at same minute (~11m cell) = duplicate (common from overlapping FIRMS processing).
- Legitimate repeats at same location but different minutes/hours are **not** deduplicated.
- Nearby distinct fires at ~100m separation remain distinct (different 4-dec cell).
- Documented in `ml/data/pipeline.py:_dedup_key`.

### 13.5 CLI Usage

```bash
# Report only (no output file)
python -m ml.data.pipeline input.csv

# CSV output (default by suffix)
python -m ml.data.pipeline input.csv output.csv

# Explicit format, disable dedup, JSON report
python -m ml.data.pipeline input.csv output.csv --no-dedup --format csv --report-json report.json

# Parquet (requires pyarrow)
python -m ml.data.pipeline input.csv output.parquet --format parquet
# or auto by .parquet suffix:
python -m ml.data.pipeline input.csv output.parquet
```

No internet required.

### 13.6 Output Schema

Processed CSV columns (compatible with `ThermalEvent`):

```
id, latitude, longitude, frp, brightness_temperature, confidence, timestamp, satellite
```

Example:

```json
{
  "id": "FIRMS_57B9E913",
  "latitude": 19.076,
  "longitude": 72.877,
  "frp": 124.5,
  "brightness_temperature": 341.2,
  "confidence": 60.0,
  "timestamp": "2026-09-06T10:30:00Z",
  "satellite": "VIIRS"
}
```

Directly usable:

```python
from ml.data.pipeline import process_firms_file
from ml.inference.pipeline import predict

events, report = process_firms_file("firms.csv")
for ev in events:
    result = predict(ev)  # optional enrichment fields remain optional
```

### 13.7 Data Quality Report

Programmatic `FirmsReport` and CLI pretty print:

```
FIRMS preprocessing report
--------------------------
Input rows:                10542
Valid rows:                10318
Invalid rows:              91
Duplicates removed:        133
Missing FRP:               12
Missing confidence:        5
Missing brightness temp:   74
Unique satellites:         VIIRS, NOAA-20, NOAA-21
Satellite counts:          {'VIIRS': 8000, ...}
Date range:                ['2026-09-01T00:00:00Z', '2026-09-06T23:59:00Z']
Latitude range:            [6.5, 35.2]
Longitude range:           [68.0, 97.4]
Invalid reasons breakdown:
  missing brightness_temperature: 74
  latitude out of range: 2
```

Access via `report.to_dict()` / `report.pretty()` / `--report-json`.

### 13.8 Structure

```
ml/data/
├── __init__.py          # lazy re-export
├── firms_schema.py      # column aliases, BT_PRIORITY, FirmsSchemaError
├── firms_loader.py      # CSV ingestion, variant detection
├── firms_cleaner.py     # validation, normalization, deterministic IDs
└── pipeline.py          # dedup, report, CSV/Parquet write, CLI
```

### 13.9 Limitations

- Does NOT perform OSM enrichment, land-cover, or labeling — those remain P1 tasks (now implemented in §14).
- Parquet output requires optional `pyarrow` (CSV always works).
- Assumes FIRMS CSV is UTF-8 comma/semicolon delimited; complex quoting not supported beyond `csv` stdlib.
- Confidence `0–1` scaling is heuristic; document source if using alternate FIRMS export.
- No automatic FIRMS download — user provides local file.

---

## 14. Geospatial / Contextual Enrichment

```
Clean FIRMS Event (ThermalEvent)
        ↓
Geospatial Enrichment (ml/geospatial)
        ↓
OSM Facilities (local GeoJSON)  →  distance_to_industry, facility_type, inside_industrial_area
Land-cover (local GeoJSON)      →  landcover_class, distance_to_forest/agriculture
Temporal (historical FIRMS)     →  detections_24h/7d/30d, persistence, hotspot_cluster
Facility Baseline               →  facility_baseline, current_activity, activity_anomaly
        ↓
EnrichedEvent
        ↓
Feature Engineering → AI predict()
```

Local-file only: no Overpass/NASA/Sentinel live calls; Yash can drop `industrial_facilities.geojson` without touching AI code.

### 14.1 Supported Input Formats

- **Facilities:** GeoJSON `FeatureCollection` with `Point`/`Polygon`/`MultiPolygon` features. Also accepts `Shapefile`/`GeoPackage` if caller pre-converts to GeoJSON dict (future: add `geopandas` reader). Properties: `industrial`, `landuse`, `power`, `man_made`, `building`, or pre-normalized `facility_type`/`type`. See `ml/geospatial/facility_enrichment.py`.
- **Land-cover:** GeoJSON `Polygon`/`MultiPolygon` with properties `class`/`landcover`/`landuse`/`type`/`category`/`natural`. Classes mapped to `forest|agriculture|industrial|water|bare|other|unknown`. Example `data/osm/industrial_facilities.geojson`, `data/landcover/landcover.geojson`.

Directory convention (Yash):

```
data/
├── firms/                          # input FIRMS CSVs (not in repo)
├── osm/
│   └── industrial_facilities.geojson
├── landcover/
│   └── landcover.geojson           # or separate forest.geojson / agriculture.geojson
└── boundaries/
```

### 14.2 Facility Enrichment

```python
from ml.geospatial import FacilityEnricher

enricher = FacilityEnricher.from_geojson("industrial_facilities.geojson")
info = enricher.enrich(19.076, 72.877)
# → {nearest_facility_id, nearest_facility_name, facility_type, distance_to_industry, inside_industrial_area}
```

- **Distance:** geodesic `haversine_m` (meters), not Cartesian. Accuracy verified `<100m` / `100–500m` / `500m–1km` / `>1km` tiers.
- **Nearest:** linear scan over facilities; `Point` → haversine, `Polygon`/`MultiPolygon` → 0 if inside else min edge distance via haversine-to-segment. Scales to thousands without external DB; replace with `STRtree`/`geopandas` spatial index later without API change.
- **Missing:** `facilities=None` → all `None` (never 0). No fabricated facilities.

### 14.3 Facility Type Normalization

Controlled vocabulary (canonical):

```
refinery, power_plant, factory, industrial_area, oil_gas, chemical, steel, cement, warehouse, other
```

OSM mapping (documented in `facility_enrichment.py`, not assumed universal):

| OSM tag | Example value | Canonical |
|---------|---------------|-----------|
| `industrial` | `oil`, `gas`, `petroleum` | `oil_gas` |
| `industrial` | `refinery` | `refinery` |
| `industrial` | `chemical` | `chemical` |
| `industrial` | `steel` | `steel` |
| `industrial` | `cement` | `cement` |
| `industrial` | `factory`, `manufacturing` | `factory` |
| `power` | `plant`, `generator` | `power_plant` |
| `landuse` | `industrial` | `industrial_area` |
| `man_made` | `works` | `factory` |

Original OSM value preserved as `original_facility_type`. Pre-normalized files with `facility_type` passthrough.

### 14.4 Land-Cover Enrichment

```python
from ml.geospatial import LandcoverEnricher
lc = LandcoverEnricher.from_geojson("landcover.geojson")
info = lc.enrich(19.075, 72.865)
# → {landcover_class, distance_to_forest, distance_to_agriculture}
```

- **Lookup:** ray-casting point-in-polygon (`lon=x, lat=y`) via `geo_utils.py`.
- **Classes:** normalized from `class`/`landcover`/`landuse`/`natural` etc. via `forest|agriculture|industrial|water|bare|other|unknown`.
- **Distances:** `distance_to_forest`/`distance_to_agriculture` = nearest forest/agri polygon edge (meters); `0` if inside same class. If dataset missing → `None`/`"unknown"` (no fabrication).
- Supports separate `forest.geojson` / `agriculture.geojson` via `LandcoverEnricher(polygons=...)` or combined file.

### 14.5 Environmental Distances

Same mechanism as land-cover; optional:

```python
# distance_to_forest and distance_to_agriculture are None when datasets absent
assert enriched["distance_to_forest"] is None  # no fabrication → 0 would falsely imply at forest
```

### 14.6 Temporal / Persistence Enrichment

```python
from ml.geospatial import TemporalEnricher
from ml.geospatial import enrich_events

# historical FIRMS events (ThermalEvent-like)
enriched = enrich_events(events, facilities="facilities.geojson",
                         landcover="landcover.geojson",
                         history=historical_events)  # optional
```

For each event within `persistence_radius_m=500m` (default):

- `detections_24h` / `detections_7d` / `detections_30d` — counts of historical events within radius and time window. Distinct from FIRMS deduplication.
- `persistence_score` / `persistence` (0–1): `max( linear(0.7*det7d/10+0.3*det24h/5), 0.8*(1-exp(-0.35*det7d)) )`; saturates <1, `0` when isolated.

### 14.7 Hotspot Clustering

- Radius-based `hotspot_cluster_size` (default `cluster_radius_m=1000m`).
- Counts historical events within radius + self (`+1`). Simple deterministic, documented radius, no complex DBSCAN needed for prototype.

### 14.8 Facility Baseline / Anomaly

If event is within `facility_assign_radius_m=1000m` of industrial facility:

```
facility_baseline = total_facility_events / 30   (detections/day over 30d window)
current_activity  = detections in last 7d / 7
activity_anomaly  = (current - baseline)/baseline   (via ml/models/anomaly.py)
```

Example from prompt: `baseline=2, current=14 → anomaly=6.0 (600% / 7.0x)`.

**Leakage note:** `TemporalEnricher(..., leakage_safe=True)` counts only history events with `timestamp < event.timestamp` (training-safe). Default `False` counts symmetric window for simple inference when whole dataset supplied — documented in `temporal_enrichment.py`. Future training must enable `leakage_safe=True`.

### 14.9 EnrichedEvent

Final output fits existing `EnrichedEvent` (all new fields optional, `None` when unavailable):

```json
{
  "id": "FIRMS_001",
  "latitude": 19.076, "longitude": 72.877,
  "frp": 124.5, "brightness_temperature": 341.2, "confidence": 87,
  "timestamp": "2026-09-06T10:30:00Z", "satellite": "VIIRS",
  "distance_to_industry": 76, "nearest_facility_id": "OSM_123",
  "facility_type": "refinery",
  "distance_to_forest": 8432, "distance_to_agriculture": 2145,
  "landcover_class": "industrial",
  "detections_24h": 4, "detections_7d": 19, "detections_30d": 71,
  "persistence": 0.83, "persistence_score": 0.83,
  "facility_baseline": 2, "current_activity": 14, "activity_anomaly": 6.0,
  "hotspot_cluster_size": 7
}
```

```python
from ml.data.pipeline import process_firms_file
from ml.geospatial import enrich_events
from ml.inference.pipeline import predict

events, _ = process_firms_file("firms.csv")
enriched = enrich_events(
    events,
    facilities="industrial_facilities.geojson",
    landcover="landcover.geojson",
    history=events  # for persistence/baseline
)
result = predict(enriched[0])  # unchanged interface
```

### 14.10 Missing-Data Behavior

Critical invariant: missing never becomes `0`:

```python
missing_distance = None   # not 0 (would imply at facility)
missing_landcover = "unknown"
```

Feature engineering (`FeatureVector`) handles `None` via flags (`has_industrial_context` etc.) → classifier gracefully falls back to `unknown` with lower confidence.

### 14.11 Performance

- Pure-Python `O(N×M)` would be slow;当前 prototype uses linear scan (thousands of events × thousands of facilities/landcover polygons is still <1s due to haversine early exit, but documented).
- Replace with `GeoPandas`/`Shapely` `STRtree` or projected distance without changing `EnrichmentPipeline` API; `geo_utils.py` isolates distance logic for easy swapping.
- No live API in tests.

### 14.12 Synthetic Test Data

Tests use tiny synthetic GeoJSON (NOT REAL OSM):

- Industrial: `OSM_123` refinery at `19.076,72.877`
- Forest square `72.86–72.87,19.07–19.08`, Agriculture `72.877–72.887,19.05–19.06`, Industrial polygon around refinery.

Scenarios verified: industrial (50–100m), wildfire (forest, >1km), agricultural (inside agri), no-context (None/unknown).

### 14.13 Limitations

- Pure-Python polygon distance approximated via haversine to vertices/edges (adequate <10km; not survey-grade).
- No `Shapefile`/`GeoPackage` direct reader yet — convert to GeoJSON via `ogr2ogr`/`geopandas` first.
- Facility assignment radius 1000m is prototype heuristic; tune with Yash's OSM extent.
- Temporal radii (500m persistence, 1000m cluster) documented but not calibrated on large real dataset.
- Does NOT download OSM; user provides local files.

---

## 15. NASA FIRMS API Downloader

> **The repository does not contain NASA FIRMS data.**
> Tests use synthetic CSV (NOT NASA data). Real downloads require your own `FIRMS_MAP_KEY`.

### 15.1 NASA FIRMS API

- Official docs: https://firms.modaps.eosdis.nasa.gov/api/area/
- Uses **Area API** ` /api/area/csv/{MAP_KEY}/{SOURCE}/{AREA}/{DAY_RANGE}[/{DATE}] `
- `MAP_KEY` is a free NASA key (https://firms.modaps.eosdis.nasa.gov/api/) — never hard-coded, never committed
- All requests via HTTPS, requests library, sequential (no hammering)

### 15.2 MAP_KEY / Environment

```bash
# .env.example (committed)
FIRMS_MAP_KEY=

# .env (gitignored) — create locally
FIRMS_MAP_KEY=YOUR_KEY_HERE
```

Module reads `FIRMS_MAP_KEY` env (also loads `.env` if present via minimal parser). If missing:

```
RuntimeError: FIRMS_MAP_KEY environment variable is required.
```

Never prints or writes MAP_KEY to metadata/logs/filenames.

### 15.3 Supported VIIRS Sources

```
VIIRS_NOAA20_NRT
VIIRS_NOAA21_NRT
VIIRS_SNPP_NRT
```

Configurable per CLI; default is all three. Source validation warns if unknown but proceeds.

### 15.4 India Bounding Box

```
west=68, south=6, east=98, north=36  →  "68,6,98,36"
```

Documented as **bounding box, not exact political polygon** — includes neighboring countries. Stored in metadata `bbox` + `bbox_str` + `bbox_note`.

### 15.5 Maximum 5-Day Chunks

NASA Area API allows max 10 days, prototype enforces **5 days** (`MAX_DAY_RANGE=5`) for robustness. Date ranges split automatically:

```python
chunk_date_range("2026-08-01","2026-09-06") → [("2026-08-01","2026-08-05"), ("2026-08-06","2026-08-10"), ...]
```

User supplies `2026-08-01 → 2026-09-06`; downloader handles splitting and combines chunks.

### 15.6 CLI

```bash
# Download India FIRMS (resumable, rate-limited)
python -m ml.data.firms_api download --start 2026-08-01 --end 2026-09-06
python -m ml.data.firms_api download --start 2026-08-01 --end 2026-08-05 --sources VIIRS_NOAA20_NRT --output data/firms/raw --force --max-days 5

# Generic single-source download to one CSV
python -m ml.data.firms_api download-one --source VIIRS_NOAA20_NRT --bbox 68,6,98,36 --start 2026-08-01 --end 2026-08-05 --output data/firms/raw_combined.csv

# Combine raw chunks
python -m ml.data.firms_api combine --input data/firms/raw --output data/firms/raw_combined.csv
# then clean
python -m ml.data.pipeline data/firms/raw_combined.csv data/firms/processed/firms_clean.csv

# Check availability (optional)
python -m ml.data.firms_api availability --source VIIRS_NOAA20_NRT
```

No default date range — missing `--start/--end` fails with usage.

### 15.7 Rate Limits & Retries

- Retries on transient `429/500/502/503/504` + timeouts with exponential backoff (`backoff * 2^attempt`, default 3 retries)
- Auth failures `401/403` fail immediately (no retry)
- ~0.5s spacing between chunks, sequential (no parallel hammering)
- Configurable `--max-days`, `--map-key`, `max_retries`/`backoff` in code

### 15.8 Raw / Processed Data Structure

```
data/
├── firms/
│   ├── raw/
│   │   ├── VIIRS_NOAA20_NRT/
│   │   │   ├── VIIRS_NOAA20_NRT_2026-08-01_2026-08-05.csv
│   │   │   ├── VIIRS_NOAA20_NRT_2026-08-01_2026-08-05.json  # per-chunk metadata
│   │   │   └── ...
│   │   ├── VIIRS_NOAA21_NRT/
│   │   └── VIIRS_SNPP_NRT/
│   │   └── download_metadata.json  # aggregate
│   ├── raw_combined.csv        # via combine
│   └── processed/
│       └── firms_clean.csv     # via ml.data.pipeline
```

Raw never overwritten by cleaned data.

### 15.9 Reproducibility Metadata

Per-download `download_metadata.json` and per-chunk `*.json`:

```json
{
  "source": "VIIRS_NOAA20_NRT",
  "bbox": [68,6,98,36],
  "bbox_str": "68,6,98,36",
  "start_date": "2026-08-01",
  "end_date": "2026-09-06",
  "downloaded_at": "2026-09-06T12:00:00Z",
  "record_count": 12345,
  "chunks": [{"start":"2026-08-01","end":"2026-08-05","records":123,"status":"ok"}],
  "failed_chunks": []
}
```

No MAP_KEY recorded.

### 15.10 Resumable Downloads

Deterministic chunk filenames `VIIRS_NOAA20_NRT_2026-08-01_2026-08-05.csv`. Before fetch: if file exists and appears valid (has `latitude` header, size>20 bytes) → skip unless `--force`.

```
Aug 1–5 ✓ (skip)  Aug 6–10 ✓ (skip)  Aug 11–15 missing → download only this  Aug 16–20 ✓ (skip)
```

### 15.11 Combine

`combine_raw_chunks(input_dir, output_path)` recursively finds `*.csv`, preserves first header, appends data rows. Used for feeding `ml.data.pipeline`.

### 15.12 Python API

```python
from ml.data.firms_api import download_firms, download_india_firms, combine_raw_chunks

download_india_firms("2026-08-01","2026-09-06", output_dir="data/firms/raw",
                     sources=["VIIRS_NOAA20_NRT"], map_key="YOUR_KEY")

download_firms("KEY","VIIRS_NOAA20_NRT","68,6,98,36","2026-08-01","2026-08-05","out.csv")

combine_raw_chunks("data/firms/raw", "data/firms/raw_combined.csv")
```

### 15.13 Security

- `.env` gitignored, only `.env.example` committed
- No `FIRMS_MAP_KEY` in code, metadata, logs, filenames
- `get_map_key()` raises clear error if missing

### 15.14 Workflow

```
NASA FIRMS API  →  ml.data.firms_api (raw)  →  ml.data.pipeline (clean ThermalEvents)
→  ml.geospatial.enrichment (EnrichedEvent)  →  ml.inference.predict()
```

### 15.15 Distinguish Real vs Synthetic

- `data/firms/raw/*` — REAL NASA FIRMS (if you run downloader)
- `ml/tests/*` — SYNTHETIC TEST DATA, never called NASA

### 15.16 First Real Download (manual, not auto)

```bash
cp .env.example .env   # add your key
python -m ml.data.firms_api download --start 2026-08-30 --end 2026-09-06
python -m ml.data.firms_api combine --input data/firms/raw --output data/firms/raw_combined.csv
python -m ml.data.pipeline data/firms/raw_combined.csv data/firms/processed/firms_clean.csv
```
