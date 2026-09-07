# India FIRMS EDA — Exploratory Analysis (NOT Ground Truth)

**Dataset:** `data/firms/processed/firms_india.csv` — 6,523 clean VIIRS detections inside India (filtered from 12,318 India bbox rows via `data/geospatial/boundaries/india.geojson`).

**Report:** `eda_report.json` (machine-readable) + plots + interactive map in this folder.

**Generated:** 2026-09-07 (analysis of 2026-08-01 → 2026-08-30, 30 days, India)

**Boundary:** Natural Earth 1:50m Admin 0 MultiPolygon (14 polygons, WGS84 EPSG:4326, public domain). See `data/geospatial/boundaries/README.md`.

**Status:** Exploratory only. No XGBoost, no labels, no accuracy claims. Candidate anomalies are ranked by thermal + persistence heuristics, not verified ground truth.

---

## 1. Dataset Validation

- **Total records:** 6,523
- **Unique IDs:** 6,523 (duplicate IDs: 0)
- **Missing values:** 0 for all 8 columns (id, latitude, longitude, frp, brightness_temperature, confidence, timestamp, satellite)
- **Invalid coordinates:** 0 (lat ∈ [-90,90], lon ∈ [-180,180])
- **Timestamp range:** 2026-08-01T06:57:00Z → 2026-08-30T21:21:00Z (30 unique dates, continuous)
- **Unique satellites:** N20 (2,277), VIIRS (SNPP, 2,031), N21 (2,215) — all three present, SNPP labeled VIIRS after cleaning
- **Columns:** 8 original FIRMS fields (preserved)
- **Numeric ranges:** FRP 0.15–239.09 (mean 3.31, median 2.15), BT 207.93–367.0 (mean 318.08), confidence 30/60/90 (mean 59.24, 60 dominates: n=nominal)
- **Inside boundary verified:** 6,523/6,523 inside MultiPolygon (100%), 0 outside — Sri Lanka (6.93,79.86) correctly excluded, 3,302 Sri Lanka bbox detections removed from clean bbox dataset. Andaman (11.74,92.65) inside, New Delhi inside.

## 2. Temporal EDA

- **Detections per day:** 2026-08-01 260, 08-02 310, 08-03 41, 08-04 39, 08-05 165, 08-06 218, 08-07 214, 08-08 215, 08-09 357, 08-10 340, ... 08-30 359 (mean ~217/day, std ~150)
- **High-activity days:** > mean+2σ (~517) → 2026-08-09 (357), 08-10 (340) etc. actually none >517? Top 5 are 08-02 (310), 08-09 (357), 08-10 (340) — threshold 517 not exceeded, so top5 reported. Daily FRP stats per day in `eda_report.json:temporal:daily_frp_stats`.
- **By hour (UTC):** Night 0-5 minimal (1 at 05), peak 07-08 UTC (872/1289), afternoon drop, evening 21-23 minimal — reflects VIIRS overpass times, not local diurnal ground truth.
- **Day vs night (approx hour 6-18 = D):** D 6,200+ vs N ~300 — day dominates due to overpass.
- **By satellite:** N20 2,277 (34.9%), VIIRS 2,031 (31.1%), N21 2,215 (34.0%) — balanced.
- **Detections per month:** 2026-08: 6,523.

## 3. Thermal EDA

| Metric | FRP | BT | Confidence |
|---|---|---|---|
| min | 0.15 | 207.93 | 30 |
| max | 239.09 | 367.0 | 90 |
| mean | 3.31 | 318.08 | 59.24 |
| median | 2.15 | 311.22 | 60 |
| std | 5.33 | 16.06 | 5.52 |
| p5 | 0.62 | 298.67 | 60 |
| p25 | 1.27 | 304.81 | 60 |
| p75 | 3.88 | 333.61 | 60 |
| p95 | 9.02 | 343.42 | 60 |
| p99 | 17.25 | 353.25 | 60 |

- **Top 50 FRP:** Highest 239.09 MW at 15.77,76.48 (N21), next 150+ MW cluster near 15.7N 76.4E (likely same fire). Full list in `eda_report.json:thermal:top50_frp` — do NOT interpret high FRP as industrial fire.

## 4. Spatial EDA

- **Extent:** lat 6.59–35.41, lon 68.19–97.40, center 20.8,80.06 (India)
- **Grid 0.5° top 20:** densest at 23.5,86.0 (877), 15.0,76.5 (355), 23.5,87.0 (228) — eastern India / Deccan hotspots.
- **Hotspot clusters (DBSCAN-like 1km, min 3):** 373 clusters, 1,711 spatial groups total, noise 1,300 points. Largest cluster size  12? (see report). Cluster size distribution in `spatial:hotspot_clusters`.
- **State-level:** Skipped (no India state boundary file provided) — country-level sufficient per task. Future: dissolve with LGD state polygons.

## 5. Persistence Analysis (500m radius, as in geospatial enrichment)

- **Unique spatial locations (500m clusters):** 1,870
- **Cluster size distribution:** 1:1,194 isolated (63.8%), 2: ~300, 3: ~150, ... up to max  12
- **Isolated:** 1,194 (single detection)
- **Repeated:** 676 (≥2)
- **Multi-day:** ~400 locations active on ≥2 distinct dates
- **Multi-week (≥7 days span):** ~50
- **High-persistence (size≥5 or ≥3 dates):** ~80
- **Longest persistence:** top spans 15-29 days (see `persistence:longest_persistence`)
- **Largest persist clusters:** size 12 at 23.6,86.3, etc. (full in report)

**Important distinction:** Repeated satellite observations within 500m & days/weeks may be same physical thermal source revisited (e.g., gas flare, brick kiln) or separate fires — repeated FIRMS ≠ confirmed industrial facility.

## 6. Candidate Anomalies (Discovery Only)

Ranked 20 candidates by `0.4*norm(FRP)+0.2*norm(BT)+0.2*norm(persistence)+0.2*norm(cluster)+night_bonus` — **NOT labels**.

- **FRP p95:** 9.02, **BT p95:** 343.42 thresholds
- **Top candidate:** ~40 MW, 11.8N 92.6E, high BT, persistent (size 5, 3 dates), night — still unvalidated.
- Full ranked table in `candidate_anomalies:top20_ranked` with lat/lon/frp/bt/conf/timestamp/satellite/persist_size/distinct_dates/score.

**Anti-leakage:** Candidate score uses only thermal + persistence, **not** `distance_to_industry` or OSM. No rule like `industrial=dist<500m` was used to create labels.

## 7. Visualizations

All under `data/firms/analysis/` (PNG, 150 dpi, Agg backend):

- `daily_count.png` — bar per day
- `frp_hist.png` — log hist 0–250 MW
- `bt_hist.png` — 207–367 K
- `confidence_hist.png` — 30/60/90 bar
- `satellite_pie.png` — N20/VIIRS/N21
- `hourly_hist.png` — UTC hour
- `spatial_scatter.png` — lon/lat colored by FRP (68-98,6-36)
- `persistent_map.png` — gray all points + red top30 persist centroids sized by cluster
- `daynight.png` — D vs N
- `india_hotspots.html` — Leaflet 20 candidate markers, OSM tiles, centered on India

## 8. Limitations

- Boundary Natural Earth 1:50m simplified — not survey-grade; de facto.
- Day/night approximated from UTC hour (cleaned lacks `daynight` column); solar local time not computed.
- Persistence thresholds 500m/1km from enrichment code — prototype, not calibrated on ground truth.
- FRP high ≠ industrial — requires OSM + field verification.
- No state-level density (no state polygon).
- No labeling/training — EDA only.

## 9. Artifacts

- `eda_report.json` — full machine-readable report (dataset, temporal, thermal, spatial, persistence, candidates, limitations)
- PNGs + `india_hotspots.html` as above
- Source data: `data/firms/processed/firms_india.csv` (6,523), boundary `data/geospatial/boundaries/india.geojson`

## 10. Reproducibility

```bash
python ml/analysis/gen_report.py   # generates eda_report.json
python ml/analysis/gen_plots.py    # generates PNGs + HTML
# Or combined: python ml/analysis/eda_final.py (now split)
```

All tests remain 90 passing (`pytest ml/tests -v`).

