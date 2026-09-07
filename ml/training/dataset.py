"""
ml/training/dataset.py — Build prototype training dataset from FIRMS India.

Uses genuinely available features only:
- FIRMS: frp, bt, confidence, lat/lon, satellite, daynight (recovered), hour, dow, month
- Temporal: detections_24h/7d/30d, persistence, hotspot_cluster_size, facility_baseline/anomaly (leakage_safe)
- Spatial: 500m/1km cluster sizes, distances (derived from same)

OSM/landcover excluded (synthetic or 0% coverage) — not used for training.
Weak labels via ml.labels.WeakLabeler (v1) — multiple signals, not single feature.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
import pandas as pd
import numpy as np

from ml.geospatial.temporal_enrichment import TemporalEnricher
from ml.geospatial.geo_utils import haversine_m
from ml.labels.weak_labels import WeakLabeler

DEFAULT_INPUT = Path("data/firms/processed/firms_india.csv")
DEFAULT_RAW = Path("data/firms/raw_combined.csv")
DEFAULT_OUTPUT_DIR = Path("data/firms/ml")

# For daynight recovery
def _deterministic_id(satellite: str, timestamp: str, lat: float, lon: float) -> str:
    payload = f"{satellite}|{timestamp}|{lat:.5f}|{lon:.5f}"
    return f"FIRMS_{hashlib.sha1(payload.encode()).hexdigest()[:8].upper()}"

def load_daynight_map(raw_path: Path = DEFAULT_RAW) -> Dict[str, str]:
    import csv
    if not raw_path.exists():
        alt = Path("data/firms/raw_combined.csv")
        if alt.exists():
            raw_path = alt
        else:
            return {}
    try:
        with raw_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "daynight" not in reader.fieldnames:
                return {}
            mapping = {}
            for row in reader:
                try:
                    lat = float(row["latitude"])
                    lon = float(row["longitude"])
                    acq_date = row.get("acq_date", "").strip()
                    acq_time = row.get("acq_time", "").strip()
                    sat = row.get("satellite", "").strip()
                    if acq_date and acq_time:
                        t = acq_time.strip()
                        if ":" in t:
                            parts = t.split(":")
                            hour = int(parts[0])
                            minute = int(parts[1]) if len(parts) >1 else 0
                        else:
                            t_padded = t.zfill(4)
                            hour = int(t_padded[:2])
                            minute = int(t_padded[2:4])
                        dt = datetime.strptime(acq_date, "%Y-%m-%d")
                        dt = dt.replace(hour=hour, minute=minute, tzinfo=timezone.utc)
                        ts_iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    else:
                        ts_iso = row.get("timestamp","").strip()
                        if not ts_iso:
                            continue
                    sat_norm = sat.upper().strip() if sat else "VIIRS"
                    fid = _deterministic_id(sat_norm, ts_iso, lat, lon)
                    mapping[fid] = row["daynight"].strip().upper()
                except Exception:
                    continue
            return mapping
    except Exception:
        return {}
    return {}

def cluster_points(lats, lons, eps_m):
    n = len(lats)
    parent = list(range(n))
    rank = [0]*n
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra==rb: return
        if rank[ra]<rank[rb]:
            parent[ra]=rb
        elif rank[ra]>rank[rb]:
            parent[rb]=ra
        else:
            parent[rb]=ra
            rank[ra]+=1
    cell_deg = eps_m/111320.0
    grid = defaultdict(list)
    for i,(lat,lon) in enumerate(zip(lats,lons)):
        grid[(int(lat//cell_deg), int(lon//cell_deg))].append(i)
    for i,(lat,lon) in enumerate(zip(lats,lons)):
        cell=(int(lat//cell_deg), int(lon//cell_deg))
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for j in grid.get((cell[0]+dx, cell[1]+dy),[]):
                    if j<=i: continue
                    if haversine_m(lat,lon,lats[j],lons[j]) <= eps_m:
                        union(i,j)
    clusters=defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)
    labels=[0]*n
    for idx,(root,members) in enumerate(clusters.items()):
        for m in members:
            labels[m]=idx
    return labels, clusters

def build_training_dataset(
    input_path: Path = DEFAULT_INPUT,
    raw_path: Path = DEFAULT_RAW,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    leakage_safe: bool = True,
) -> Dict[str, Any]:
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    total = len(df)
    print(f"Loaded {total} FIRMS India records from {input_path}")

    # Parse timestamps for temporal — use object dtype to avoid pandas datetime64 hang on Python 3.14
    def parse_ts(s):
        return datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc)
    df['ts'] = df['timestamp'].apply(parse_ts).astype(object)
    df['date'] = df['ts'].apply(lambda d: d.date().isoformat())
    df['hour_utc'] = df['ts'].apply(lambda d: d.hour)
    df['day_of_week'] = df['ts'].apply(lambda d: d.weekday())
    df['month'] = df['ts'].apply(lambda d: d.month)
    # Daynight recovery
    daynight_map = load_daynight_map(raw_path)
    print(f"Daynight map {len(daynight_map)} entries")
    def get_daynight(row):
        fid = _deterministic_id(str(row['satellite']).upper(), str(row['timestamp']), float(row['latitude']), float(row['longitude']))
        dn = daynight_map.get(fid)
        if dn in ("D","N"):
            return dn
        # fallback hour approx
        h = int(row['hour_utc'])
        return "D" if 6 <= h <= 18 else "N"
    df['daynight'] = df.apply(get_daynight, axis=1)
    # Satellite encoding: keep original, will one-hot later
    # Temporal enrichment — leakage_safe
    print("Building history_records...", flush=True)
    history_records = df.to_dict(orient="records")
    print(f"History {len(history_records)}", flush=True)
    temporal = TemporalEnricher(history=history_records, leakage_safe=leakage_safe, persistence_radius_m=500, cluster_radius_m=1000)
    print("Temporal enricher built", flush=True)
    # For each row, compute temporal
    temp_features = []
    for idx, row in df.iterrows():
        if idx % 100 == 0:
            print(f"Temporal enrich {idx}/{len(df)}", flush=True)
        info = temporal.enrich(row.to_dict())
        temp_features.append(info)
    print("Temporal done", flush=True)
    print("Building temp_df...", flush=True)
    temp_df = pd.DataFrame(temp_features)
    for col in temp_df.columns:
        df[col] = temp_df[col].values
    print("Temp df done", flush=True)

    # Facility baseline (also leakage_safe) - compute per row via temporal.facility_baseline at event location
    # For prototype, use event lat/lon as facility proxy (since no OSM)
    print("Facility baseline start...", flush=True)
    baseline_vals = []
    for idx, row in df.iterrows():
        if idx % 100 == 0:
            print(f"Baseline {idx}/{len(df)}", flush=True)
        bl = temporal.facility_baseline(float(row['latitude']), float(row['longitude']), current_event=row.to_dict())
        baseline_vals.append(bl)
    print("Baseline done", flush=True)
    print("Building bl_df...", flush=True)
    bl_df = pd.DataFrame(baseline_vals)
    print(f"bl_df {bl_df.shape}", flush=True)
    # Rename to match schema
    df['facility_baseline'] = bl_df['facility_baseline']
    df['facility_current_activity'] = bl_df['current_activity']
    # Keep both names
    df['current_activity'] = bl_df['current_activity']
    df['activity_anomaly'] = bl_df['activity_anomaly']
    df['facility_anomaly'] = bl_df['activity_anomaly']
    print("Baseline df assigned", flush=True)

    # Spatial clustering for persistence helper fields
    print("Clustering 500m...", flush=True)
    lats = df['latitude'].values
    lons = df['longitude'].values
    labels_500, clusters_500 = cluster_points(lats, lons, 500)
    print(f"500m clusters {len(clusters_500)}", flush=True)
    # For each cluster, compute distinct_dates and span_days
    # Build maps
    # First need date column
    # clusters_500 is dict root->list of indices
    # For each cluster, compute distinct_dates and span
    cluster_distinct = {}
    cluster_span = {}
    cluster_size = {}
    for cid, members in clusters_500.items():
        sub = df.iloc[members]
        # Use Python set to avoid pandas nunique hang with ts present
        distinct = len(set(sub['date'].tolist()))
        # span via timestamp strings
        dts = [datetime.fromisoformat(s.replace('Z','+00:00')) for s in sub['timestamp'].tolist()]
        span = int((max(dts) - min(dts)).days) if len(dts)>1 else 0
        for idx in members:
            cluster_distinct[idx] = distinct
            cluster_span[idx] = span
            cluster_size[idx] = len(members)
    df['_distinct_dates'] = [cluster_distinct[i] for i in range(len(df))]
    df['_span_days'] = [cluster_span[i] for i in range(len(df))]
    df['_cluster_size_500'] = [cluster_size[i] for i in range(len(df))]

    # Also 1km cluster for hotspot size (already have hotspot_cluster_size from temporal, but also compute)
    labels_1000, clusters_1000 = cluster_points(lats, lons, 1000)
    # hotspot_cluster_size already from temporal, but we keep it

    # Also store 500m cluster id for split grouping
    df['_spatial_cluster_id'] = labels_500

    # Weak labels
    labeler = WeakLabeler(version="weak_rule_v1")
    # Prepare rows for labeling: need to include _distinct_dates/_span_days
    # WeakLabeler expects row dict with those keys
    results = labeler.label_batch(df.to_dict(orient="records"))
    df['weak_label'] = [r.label for r in results]
    df['label_confidence'] = [r.label_confidence for r in results]
    df['label_source'] = [r.label_source for r in results]
    df['label_reasons'] = [",".join(r.label_reasons) for r in results]
    df['confidence_level'] = [r.confidence_level for r in results]

    # For training, we need to decide feature set
    # Genuinely available: FIRMS + temporal + spatial (500m) + time
    # Exclude OSM/landcover (synthetic or missing)
    feature_cols = [
        "latitude","longitude","frp","brightness_temperature","confidence",
        "hour_utc","day_of_week","month",
        "detections_24h","detections_7d","detections_30d","persistence","hotspot_cluster_size",
        "facility_baseline","facility_current_activity","facility_anomaly",
        "_cluster_size_500","_distinct_dates","_span_days",
    ]
    # Also include satellite and daynight encoded separately (we will handle in training)
    # Keep them as categorical for later encoding
    # For dataset report, we need to handle class distribution etc.
    
    # Ensure output dir
    output_dir.mkdir(parents=True, exist_ok=True)
    # Save training dataset (full)
    # Keep all columns plus weak labels
    # For CSV, we need to flatten
    # Select columns to save: original + derived + weak labels
    # Keep deterministic order
    save_cols = ["id","latitude","longitude","frp","brightness_temperature","confidence","timestamp","satellite","daynight","hour_utc","day_of_week","month",
                 "detections_24h","detections_7d","detections_30d","persistence","persistence_score","hotspot_cluster_size",
                 "facility_baseline","facility_current_activity","facility_anomaly","current_activity","activity_anomaly",
                 "_cluster_size_500","_distinct_dates","_span_days","_spatial_cluster_id",
                 "weak_label","label_confidence","label_source","label_reasons","confidence_level"]
    # Ensure all exist
    for c in save_cols:
        if c not in df.columns:
            df[c] = None
    out_csv = output_dir / "training_dataset.csv"
    df[save_cols].to_csv(out_csv, index=False)
    print(f"Wrote training dataset {out_csv} with {len(df)} rows")

    # Labels.csv separate (id, weak_label, confidence, reasons)
    labels_df = df[["id","weak_label","label_confidence","label_source","label_reasons","confidence_level"]].copy()
    labels_csv = output_dir / "labels.csv"
    labels_df.to_csv(labels_csv, index=False)
    print(f"Wrote labels {labels_csv}")

    # Dataset report — use Python Counter to avoid pandas hang with ts column
    class_counts = dict(Counter(df['weak_label'].tolist()))
    total_labeled = sum(1 for v in df['weak_label'].tolist() if v != "unknown")
    total_unknown = sum(1 for v in df['weak_label'].tolist() if v == "unknown")
    low_conf = sum(1 for v in df['label_confidence'].tolist() if v < 0.5)
    # Missing feature stats — use Python
    missing_stats = {}
    for col in feature_cols:
        if col in df.columns:
            missing_stats[col] = int(sum(1 for v in df[col].tolist() if pd.isna(v)))
        else:
            missing_stats[col] = 0
    # Also OSM/landcover missing (should be 100%)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "input": str(input_path),
        "total_samples": int(total),
        "class_counts": {k: int(v) for k,v in class_counts.items()},
        "class_percentages": {k: round(100*v/total,2) for k,v in class_counts.items()},
        "total_labeled": total_labeled,
        "total_unknown": total_unknown,
        "unknown_pct": round(100*total_unknown/total,2) if total else 0,
        "low_confidence_samples": low_conf,
        "low_confidence_pct": round(100*low_conf/total,2) if total else 0,
        "missing_feature_stats": missing_stats,
        "features_used": feature_cols + ["satellite","daynight"],  # categorical extra
        "features_excluded_due_to_missing": ["landcover_class","forest_fraction","nearest_facility_distance_m","facility_count_500m","oil_gas_facility_count_1km","ndvi","ndbi"],
        "label_method": "weak_rule_v1 (multi-signal, no single feature defines label)",
        "label_rules": {k: [desc for desc,_ in v] for k,v in __import__('ml.labels.label_rules', fromlist=['RULES']).RULES.items()},
        "leakage_note": "Weak labels use persistence/detections/hotspot; training features include same temporal features => weak-supervision baseline, not independent evaluation. See leakage_report.",
        "temporal_leakage_safe": leakage_safe,
        "spatial_clusters_500m": int(len(clusters_500)),
        "output_files": {
            "training_dataset": str(out_csv),
            "labels": str(labels_csv),
        }
    }
    report_path = output_dir / "dataset_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote dataset report {report_path}")

    # Leakage report — map rule descriptions to actual feature names
    # Extract base feature names from rule descriptions (e.g., "detections_7d>=5" -> "detections_7d")
    import re
    label_feature_bases = set()
    for rules in __import__('ml.labels.label_rules', fromlist=['RULES']).RULES.values():
        for desc, _ in rules:
            # Extract alphanumeric + underscore before operator
            m = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)", desc)
            if m:
                label_feature_bases.add(m.group(1))
            else:
                label_feature_bases.add(desc)
    training_features = set(feature_cols)
    overlap = label_feature_bases.intersection(training_features)
    leakage_report = {
        "label_generating_features": sorted(list(label_feature_bases)),
        "training_features": sorted(list(training_features | {"satellite","daynight"})),
        "overlap": sorted(list(overlap)),
        "risk": "Overlap indicates weak-supervision baseline, not independent. For independent evaluation, exclude overlapping features or treat as rule-based baseline.",
        "recommendation": "For prototype, keep overlap but document as weak-supervision baseline. Future: collect independent ground truth or use OSM/landcover not used in labeling.",
    }
    leakage_path = output_dir / "leakage_report.json"
    leakage_path.write_text(json.dumps(leakage_report, indent=2), encoding="utf-8")
    print(f"Wrote leakage report {leakage_path}")

    # README
    readme = f"""# Training Dataset — Prototype (Weak Labels, Not Ground Truth)

Generated: {report['generated_at']}
Input: {input_path} ({total} India FIRMS detections, 2026-08-01 to 2026-08-30)
Output: `training_dataset.csv` ({total} rows, leakage_safe={leakage_safe})

## Features Genuinely Available
- FIRMS: frp, brightness_temperature, confidence, lat/lon, satellite, daynight (recovered), hour_utc, day_of_week, month
- Temporal (leakage_safe): detections_24h/7d/30d, persistence, hotspot_cluster_size, facility_baseline/current_activity/anomaly
- Spatial: 500m cluster size, distinct_dates, span_days, spatial_cluster_id

Excluded (synthetic or 0% coverage): OSM distances/counts, landcover fractions, ndvi/ndbi

## Weak Labels
- Version: weak_rule_v1
- Classes: industrial_fire, persistent_industrial_thermal_source, gas_flare, wildfire, agricultural_fire, unknown
- Method: multi-signal rules (see `ml/labels/label_rules.py`), confidence = satisfied/total
- No single feature defines a label; at least 3 conditions required, score >=0.5
- Unknown when insufficient evidence

## Class Distribution
{json.dumps(class_counts, indent=2)}
Unknown: {total_unknown} ({round(100*total_unknown/total,2)}%)
Low confidence (<0.5): {low_conf}

## Leakage
Overlap between label-generating and training features: {sorted(list(overlap))}
This is a weak-supervision baseline, not independent evaluation.

## Files
- training_dataset.csv — full features + weak labels
- labels.csv — id, weak_label, confidence, reasons
- dataset_report.json — counts, missingness, features
- leakage_report.json — overlap analysis
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")
    print(f"Wrote README {output_dir / 'README.md'}")

    return report
