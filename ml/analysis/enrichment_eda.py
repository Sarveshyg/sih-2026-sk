"""
Enrichment EDA for firms_enriched.csv — no labels, no training.
Generates data/firms/analysis/enrichment/eda_report.json + plots
"""
import sys
sys.path.insert(0, ".")
import json
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timezone

ENRICHED = Path("data/firms/processed/firms_enriched.csv")
OUT_DIR = Path("data/firms/analysis/enrichment")
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("Loading enriched", ENRICHED)
df = pd.read_csv(ENRICHED, low_memory=False)
print(f"Loaded {len(df)} rows, {len(df.columns)} cols")

# Basic stats
total = len(df)
# Missingness
missingness = {col: int(df[col].isna().sum()) for col in df.columns}
# OSM coverage: nearest_facility_distance_m not null
osm_with = int(df['nearest_facility_distance_m'].notna().sum()) if 'nearest_facility_distance_m' in df.columns else 0
osm_without = total - osm_with
osm_coverage = round(100*osm_with/total,2) if total else 0
# Landcover
lc_with = int((df['landcover_class'] != 'unknown').sum()) if 'landcover_class' in df.columns else 0
lc_without = total - lc_with
lc_cov = round(100*lc_with/total,2) if total else 0
# Facility distance distributions
dist_cols = [c for c in df.columns if 'distance_m' in c]
dist_stats = {}
for col in dist_cols:
    s = df[col].dropna()
    if len(s):
        dist_stats[col] = {
            "min": float(s.min()),
            "max": float(s.max()),
            "mean": float(s.mean()),
            "median": float(s.median()),
            "p95": float(s.quantile(0.95)),
            "missing": int(df[col].isna().sum()),
        }
# Facility density: counts
count_cols = [c for c in df.columns if 'facility_count' in c]
count_stats = {}
for col in count_cols:
    s = df[col].fillna(0)
    count_stats[col] = {
        "mean": float(s.mean()),
        "max": int(s.max()),
        "non_zero": int((s>0).sum()),
        "pct_non_zero": round(100*(s>0).sum()/total,2),
    }
# Landcover distribution
lc_dist = df['landcover_class'].value_counts().to_dict() if 'landcover_class' in df.columns else {}
# Persistence distribution
persist_stats = {}
for col in ['persistence','detections_24h','detections_7d','detections_30d','hotspot_cluster_size']:
    if col in df.columns:
        s = df[col].dropna()
        if len(s):
            persist_stats[col] = {
                "min": float(s.min()),
                "max": float(s.max()),
                "mean": float(s.mean()),
                "median": float(s.median()),
            }
# Anomaly
anomaly_stats = {}
for col in ['facility_baseline','facility_current_activity','facility_anomaly','activity_anomaly']:
    if col in df.columns:
        s = df[col].dropna()
        if len(s):
            anomaly_stats[col] = {
                "min": float(s.min()),
                "max": float(s.max()),
                "mean": float(s.mean()),
                "median": float(s.median()),
            }

# Correlation matrix for numeric features
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
# Filter to relevant numeric features for classifier
relevant = [c for c in numeric_cols if c not in ['id']]
# Compute correlation
corr = df[relevant].corr(numeric_only=True)
corr_dict = {}
# Save top correlations (abs >0.3)
for i, col1 in enumerate(relevant):
    for col2 in relevant[i+1:]:
        try:
            v = corr.loc[col1, col2]
            if pd.notna(v) and abs(v) > 0.3:
                corr_dict[f"{col1}__{col2}"] = round(float(v),3)
        except Exception:
            continue
# Sort by abs value
sorted_corr = dict(sorted(corr_dict.items(), key=lambda x: abs(x[1]), reverse=True))

report = {
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
    "input": str(ENRICHED),
    "total_records": total,
    "missingness": missingness,
    "osm_coverage": {"with_match": osm_with, "without": osm_without, "pct": osm_with and round(100*osm_with/total,2)},
    "landcover_coverage": {"with": lc_with, "without": lc_without, "pct": lc_cov},
    "facility_distance_distributions": dist_stats,
    "facility_density": count_stats,
    "landcover_distribution": lc_dist,
    "persistence_distribution": persist_stats,
    "anomaly_distribution": anomaly_stats,
    "correlation_top_abs_gt_0_3": sorted_corr,
    "correlation_note": "Correlation does not imply causation; for feature selection only",
    "columns": df.columns.tolist(),
}

# Write report
out_report = OUT_DIR / "enrichment_eda_report.json"
out_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"Wrote {out_report}")

# Plots
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Missingness bar
plt.figure(figsize=(12,4))
missing_series = pd.Series(missingness).sort_values(ascending=False)
missing_series[missing_series>0].plot(kind='bar', color='#d62728')
plt.title('Missingness by feature (enriched)')
plt.ylabel('Missing count')
plt.xticks(rotation=90, fontsize=6)
plt.tight_layout()
plt.savefig(OUT_DIR / "missingness.png", dpi=150)
plt.close()

# OSM distance hist
if 'nearest_facility_distance_m' in df.columns:
    s = df['nearest_facility_distance_m'].dropna()
    if len(s):
        plt.figure(figsize=(8,4))
        plt.hist(s, bins=50, color='#1f77b4', edgecolor='white')
        plt.title('Nearest facility distance (m)')
        plt.xlabel('meters')
        plt.ylabel('count')
        plt.yscale('log')
        plt.tight_layout()
        plt.savefig(OUT_DIR / "osm_distance_hist.png", dpi=150)
        plt.close()

# Facility counts hist
for col in ['facility_count_1km','industrial_facility_count_1km']:
    if col in df.columns:
        plt.figure(figsize=(6,3))
        df[col].hist(bins=20, color='#2ca02c')
        plt.title(col)
        plt.xlabel('count')
        plt.tight_layout()
        plt.savefig(OUT_DIR / f"{col}_hist.png", dpi=150)
        plt.close()

# Persistence hist
if 'persistence' in df.columns:
    plt.figure(figsize=(6,3))
    plt.hist(df['persistence'].dropna(), bins=20, color='#ff7f0e')
    plt.title('Persistence 0-1')
    plt.tight_layout()
    plt.savefig(OUT_DIR / "persistence_hist.png", dpi=150)
    plt.close()

# Anomaly hist
if 'facility_anomaly' in df.columns:
    s = df['facility_anomaly'].dropna()
    if len(s):
        plt.figure(figsize=(6,3))
        plt.hist(s, bins=30, color='#9467bd')
        plt.title('Facility anomaly (current-baseline)/baseline')
        plt.tight_layout()
        plt.savefig(OUT_DIR / "anomaly_hist.png", dpi=150)
        plt.close()

# Correlation heatmap (simplified)
if len(relevant) > 1:
    # Select top numeric cols for heatmap
    top_corr_cols = ['frp','brightness_temperature','confidence','persistence','detections_7d','hotspot_cluster_size','nearest_facility_distance_m','facility_count_1km']
    top_corr_cols = [c for c in top_corr_cols if c in df.columns]
    if len(top_corr_cols) >= 3:
        corr_mat = df[top_corr_cols].corr()
        plt.figure(figsize=(8,6))
        im = plt.imshow(corr_mat, cmap='RdBu', vmin=-1, vmax=1)
        plt.colorbar(im, label='correlation')
        plt.xticks(range(len(top_corr_cols)), top_corr_cols, rotation=45, ha='right', fontsize=7)
        plt.yticks(range(len(top_corr_cols)), top_corr_cols, fontsize=7)
        plt.title('Correlation matrix (numeric features) — not causal')
        plt.tight_layout()
        plt.savefig(OUT_DIR / "correlation_heatmap.png", dpi=150)
        plt.close()

# Landcover pie
if 'landcover_class' in df.columns:
    plt.figure(figsize=(5,5))
    lc_series = df['landcover_class'].value_counts()
    plt.pie(lc_series, labels=lc_series.index, autopct='%1.1f%%')
    plt.title('Landcover class')
    plt.tight_layout()
    plt.savefig(OUT_DIR / "landcover_pie.png", dpi=150)
    plt.close()

print("Plots done")
# List files
for p in sorted(OUT_DIR.glob("*")):
    print(p.name, p.stat().st_size)
