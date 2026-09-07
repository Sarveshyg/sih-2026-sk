# India Country Boundary — Metadata

**File:** `india.geojson`

## Source

- **Dataset:** Natural Earth — Admin 0 – Countries (1:50m)
- **URL:** https://www.naturalearthdata.com/downloads/50m-cultural-vectors/ (via https://github.com/nvkelso/natural-earth-vector — `geojson/ne_50m_admin_0_countries.geojson`)
- **Feature extracted:** `ISO_A3 == "IND"` (India, Sovereign country, Admin-0)
- **Original file version:** 5.1.1 (Natural Earth Vector, public domain)
- **Extraction date:** 2026-09-07

## Dataset / License

- **License:** Public Domain (Natural Earth). Natural Earth data is explicitly placed in the public domain — no permission required, no attribution mandatory (attribution appreciated). See https://www.naturalearthdata.com/about/terms-of-use/
- **Reuse:** Suitable for prototype; de facto boundaries as controlled on the ground.

## Boundary Level

- **Level:** Country (Admin-0)
- **Type:** Sovereign country (`TYPE="Sovereign country"`, `LEVEL=2`)
- **Geometry type:** MultiPolygon (14 polygons — mainland + islands including Andaman & Nicobar, Lakshadweep)
- **Source scale:** 1:50 million (sufficient for prototype country-level filtering; not survey-grade)

## CRS

- **CRS:** WGS84 (EPSG:4326) — GeoJSON standard longitude, latitude in decimal degrees. No reprojection required. Validated that coordinates are in [-180,180]/[-90,90] and polygon winding follows GeoJSON spec.

## Notes on Disputed Areas

Natural Earth draws boundaries according to de facto control. For India this affects Kashmir/Aksai Chin/Arunachal Pradesh representation. This prototype uses the Natural Earth de facto line; for operational deployment replace with Survey of India or LGD-authoritative boundary.

## File Info

- **Path:** `data/geospatial/boundaries/india.geojson`
- **Format:** GeoJSON FeatureCollection with single India feature (original properties preserved)
- **Size:** ~142 KB
- **Acquisition method:** `urllib.request` extraction in `ml/geospatial/boundary_filter.py` logic (no manual digitizing)

## Validation

- Geometry validated via pure-Python point-in-polygon (see `ml/geospatial/geo_utils.py`) and optional Shapely `is_valid` check if available.
- Tested: New Delhi (28.61,77.20) inside, Sri Lanka Colombo (6.93,79.86) outside, Andaman (11.74,92.65) inside, Pakistan Karachi (24.86,67.01) outside.
