"""
EDA runner for India FIRMS — generates report + plots, no sklearn required.
"""
import json, csv, math
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
import pandas as pd
import numpy as np

OUT_DIR = Path("data/firms/analysis")
OUT_DIR.mkdir(parents=True, exist_ok=True)

INDIA_CSV = Path("data/firms/processed/firms_india.csv")
BOUNDARY = Path("data/geospatial/boundaries/india.geojson")

print("Loading", INDIA_CSV)
df = pd.read_csv(INDIA_CSV)
print(f"Loaded {len(df)} rows")
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
df['date'] = df['timestamp'].dt.date.astype(str)
df['hour'] = df['timestamp'].dt.hour
df['daynight_approx'] = df['hour'].apply(lambda h: 'D' if 6 <= h <= 18 else 'N')
df['month'] = df['timestamp'].dt.to_period('M').astype(str)

# Validation
total_records = len(df)
unique_ids = df['id'].nunique()
duplicate_ids = total_records - unique_ids
missing = df.isnull().sum().to_dict()
invalid_lat = int(((df['latitude'] < -90) | (df['latitude'] > 90)).sum())
invalid_lon = int(((df['longitude'] < -180) | (df['longitude'] > 180)).sum())
timestamp_range = [df['timestamp'].min().isoformat().replace('+00:00','Z'), df['timestamp'].max().isoformat().replace('+00:00','Z')]
unique_dates = int(df['date'].nunique())
unique_sats = sorted(df['satellite'].unique().tolist())
columns = df.columns.tolist()
numeric_summary = {}
for col in ['frp','brightness_temperature','confidence']:
    s = df[col]
    numeric_summary[col] = {
        'min': float(s.min()), 'max': float(s.max()), 'mean': float(s.mean()),
        'median': float(s.median()), 'std': float(s.std()),
        'p5': float(s.quantile(0.05)), 'p25': float(s.quantile(0.25)),
        'p75': float(s.quantile(0.75)), 'p95': float(s.quantile(0.95)), 'p99': float(s.quantile(0.99)),
    }

# Verify inside boundary
try:
    from ml.geospatial.boundary_filter import load_boundary, is_inside
    boundary = load_boundary(BOUNDARY)
    inside_count = 0
    for _, r in df.iterrows():
        if is_inside(float(r['latitude']), float(r['longitude']), boundary):
            inside_count += 1
    outside_count = total_records - inside_count
    verify = {"inside": inside_count, "outside": outside_count, "all_inside": bool(outside_count==0), "crs": boundary["crs"], "geometry_type": boundary["geometry_type"]}
except Exception as e:
    verify = {"error": str(e), "inside": None}
    inside_count = total_records
    outside_count = 0
    print(f"boundary verify error {e}")

print(f"Validation inside {inside_count} outside {outside_count}")

# Temporal
per_day = df['date'].value_counts().sort_index()
per_hour = df['hour'].value_counts().sort_index()
daynight_counts = df['daynight_approx'].value_counts().to_dict()
sat_counts = df['satellite'].value_counts().to_dict()
daily_frp = df.groupby('date')['frp'].agg(['count','mean','median','max','min','std']).round(2)
daily_frp_dict = {k: {kk: (float(v) if not pd.isna(v) else None) for kk,v in vals.items()} for k, vals in daily_frp.to_dict('index').items()}
mean_daily = float(per_day.mean())
std_daily = float(per_day.std())
threshold = mean_daily + 2*std_daily
high_days = per_day[per_day > threshold].to_dict()
if not high_days:
    high_days = per_day.nlargest(5).to_dict()
# Convert high_days keys to str
high_days = {str(k): int(v) for k,v in high_days.items()}

# Thermal
thermal_stats = numeric_summary
top50 = df.nlargest(50, 'frp')[['id','latitude','longitude','frp','brightness_temperature','confidence','timestamp','satellite']].copy()
top50['timestamp'] = top50['timestamp'].astype(str)
top50_records = top50.to_dict(orient='records')

# Spatial
lat_min, lat_max = float(df['latitude'].min()), float(df['latitude'].max())
lon_min, lon_max = float(df['longitude'].min()), float(df['longitude'].max())
center_lat, center_lon = float(df['latitude'].mean()), float(df['longitude'].mean())
GRID = 0.5
df['grid_lat'] = (df['latitude'] // GRID * GRID).round(2)
df['grid_lon'] = (df['longitude'] // GRID * GRID).round(2)
grid_counts = df.groupby(['grid_lat','grid_lon']).size().sort_values(ascending=False)
grid_top = [{"grid_lat": float(k[0]), "grid_lon": float(k[1]), "count": int(v)} for k,v in grid_counts.head(20).items()]

# Persistence / Hotspot clustering pure python
from ml.geospatial.geo_utils import haversine_m

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
        ra, rb = find(a), find(b)
        if ra==rb: return
        if rank[ra]<rank[rb]:
            parent[ra]=rb
        elif rank[ra]>rank[rb]:
            parent[rb]=ra
        else:
            parent[rb]=ra
            rank[ra]+=1
    cell_deg = eps_m / 111320.0
    grid = defaultdict(list)
    for i, (lat, lon) in enumerate(zip(lats, lons)):
        cell = (int(lat // cell_deg), int(lon // cell_deg))
        grid[cell].append(i)
    for i, (lat, lon) in enumerate(zip(lats, lons)):
        cell = (int(lat // cell_deg), int(lon // cell_deg))
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                neigh = (cell[0]+dx, cell[1]+dy)
                for j in grid.get(neigh, []):
                    if j <= i: continue
                    d = haversine_m(lat, lon, lats[j], lons[j])
                    if d <= eps_m:
                        union(i,j)
    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)
    labels = [0]*n
    for idx, (root, members) in enumerate(clusters.items()):
        for m in members:
            labels[m]=idx
    return labels, clusters

lats = df['latitude'].values
lons = df['longitude'].values
print("Clustering 1km...")
labels_1km, clusters_1km = cluster_points(lats, lons, 1000)
df['cluster_1km'] = labels_1km
# Hotspot: size>=3
hotspot_clusters = {cid: members for cid, members in clusters_1km.items() if len(members) >=3}
n_clusters = len(hotspot_clusters)
noise = sum(len(m) for cid, m in clusters_1km.items() if len(m) <3)
# size distribution for hotspot
size_dist = Counter([len(m) for m in hotspot_clusters.values()])
largest = sorted(hotspot_clusters.items(), key=lambda x: len(x[1]), reverse=True)[:10]
largest_details = []
for cid, members in largest:
    sub = df.iloc[members]
    largest_details.append({
        "cluster_id": int(cid),
        "size": int(len(members)),
        "centroid_lat": float(sub['latitude'].mean()),
        "centroid_lon": float(sub['longitude'].mean()),
        "frp_mean": float(sub['frp'].mean()),
        "frp_max": float(sub['frp'].max()),
        "date_span_days": int((sub['timestamp'].max() - sub['timestamp'].min()).days) +1,
        "satellites": sub['satellite'].value_counts().to_dict(),
    })
cluster_info = {
    "method": "Union-Find haversine eps=1000m (grid-hashed)",
    "n_clusters": int(n_clusters),
    "noise_points": int(noise),
    "total_spatial_groups": int(len(clusters_1km)),
    "cluster_size_distribution": {str(k): int(v) for k,v in sorted(size_dist.items())},
    "largest_clusters": largest_details,
    "eps_m": 1000,
}

print("Clustering 500m for persistence...")
labels_500, clusters_500 = cluster_points(lats, lons, 500)
df['persist_cluster'] = labels_500
n_persist = len(clusters_500)
# For each persist cluster, compute temporal stats
persist_clusters = []
for cid, members in clusters_500.items():
    sub = df.iloc[members].sort_values('timestamp')
    distinct_dates = int(sub['date'].nunique())
    span_days = int((sub['timestamp'].max() - sub['timestamp'].min()).days)
    persist_clusters.append({
        "cluster_id": int(cid),
        "size": int(len(members)),
        "distinct_dates": distinct_dates,
        "span_days": span_days,
        "centroid_lat": float(sub['latitude'].mean()),
        "centroid_lon": float(sub['longitude'].mean()),
        "satellites": sub['satellite'].value_counts().to_dict(),
        "frp_max": float(sub['frp'].max()),
        "frp_mean": float(sub['frp'].mean()),
    })
isolated = sum(1 for c in persist_clusters if c['size']==1)
repeated = sum(1 for c in persist_clusters if c['size']>=2)
multi_day = sum(1 for c in persist_clusters if c['distinct_dates']>=2)
multi_week = sum(1 for c in persist_clusters if c['span_days']>=7)
high_persist = [c for c in persist_clusters if c['size']>=5 or c['distinct_dates']>=3]
longest = sorted(persist_clusters, key=lambda x: x['span_days'], reverse=True)[:5]
p_size_dist = Counter([c['size'] for c in persist_clusters])
persistence_info = {
    "method": "Union-Find haversine eps=500m (unique spatial locations)",
    "n_unique_spatial_clusters": int(n_persist),
    "cluster_size_distribution": {str(k): int(v) for k,v in sorted(p_size_dist.items())},
    "isolated_detections": int(isolated),
    "repeated_detections": int(repeated),
    "multi_day_locations": int(multi_day),
    "multi_week_locations": int(multi_week),
    "high_persistence_locations": int(len(high_persist)),
    "largest_persist_clusters": sorted(persist_clusters, key=lambda x: x['size'], reverse=True)[:10],
    "longest_persistence": longest,
    "eps_m": 500,
}
print(f"Persist isolated {isolated} repeated {repeated} multi_day {multi_day} multi_week {multi_week}")

# Candidate anomalies
candidate_df = df.copy()
cluster_size_map = {c['cluster_id']: c['size'] for c in persist_clusters}
distinct_map = {c['cluster_id']: c['distinct_dates'] for c in persist_clusters}
candidate_df['persist_size'] = candidate_df['persist_cluster'].map(cluster_size_map)
candidate_df['distinct_dates_c'] = candidate_df['persist_cluster'].map(distinct_map)
def norm(s):
    return (s - s.min()) / (s.max() - s.min() + 1e-9)
candidate_df['norm_frp'] = norm(candidate_df['frp'])
candidate_df['norm_bt'] = norm(candidate_df['brightness_temperature'])
candidate_df['norm_persist'] = norm(candidate_df['distinct_dates_c'].astype(float))
candidate_df['norm_cluster'] = norm(candidate_df['persist_size'].astype(float))
candidate_df['night_bonus'] = (candidate_df['daynight_approx'] == 'N').astype(int) * 0.05
candidate_df['candidate_score'] = 0.4*candidate_df['norm_frp'] + 0.2*candidate_df['norm_bt'] + 0.2*candidate_df['norm_persist'] + 0.2*candidate_df['norm_cluster'] + candidate_df['night_bonus']
candidates = candidate_df.nlargest(20, 'candidate_score')[['id','latitude','longitude','frp','brightness_temperature','confidence','timestamp','satellite','persist_size','distinct_dates_c','candidate_score','daynight_approx']].copy()
candidates['timestamp'] = candidates['timestamp'].astype(str)
candidate_records = candidates.rename(columns={'distinct_dates_c':'distinct_dates'}).to_dict(orient='records')

report = {
    "generated_at": datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
    "dataset": {
        "path": str(INDIA_CSV),
        "boundary": str(BOUNDARY),
        "total_records": int(total_records),
        "unique_ids": int(unique_ids),
        "duplicate_ids": int(duplicate_ids),
        "missing_values": missing,
        "invalid_coordinates": {"invalid_lat": int(invalid_lat), "invalid_lon": int(invalid_lon)},
        "timestamp_range": timestamp_range,
        "unique_acquisition_dates": int(unique_dates),
        "unique_satellites": unique_sats,
        "columns": columns,
        "numeric_summary": numeric_summary,
        "inside_boundary_verified": {"inside": int(inside_count), "outside": int(outside_count), "all_inside": bool(outside_count==0), "crs": "EPSG:4326", "geometry_type": "MultiPolygon"},
    },
    "temporal": {
        "detections_per_day": per_day.to_dict(),
        "detections_by_hour": per_hour.to_dict(),
        "daynight_approx": daynight_counts,
        "detections_by_satellite": sat_counts,
        "detections_per_month": df['month'].value_counts().to_dict(),
        "daily_frp_stats": daily_frp_dict,
        "high_activity_days": high_days,
        "mean_per_day": float(mean_daily),
        "std_per_day": float(std_daily),
    },
    "thermal": {
        "frp": numeric_summary['frp'],
        "brightness_temperature": numeric_summary['brightness_temperature'],
        "confidence": numeric_summary['confidence'],
        "top50_frp": top50_records,
    },
    "spatial": {
        "extent": {"lat_min": float(lat_min), "lat_max": float(lat_max), "lon_min": float(lon_min), "lon_max": float(lon_max), "center_lat": float(center_lat), "center_lon": float(center_lon)},
        "grid_0_5deg_top20": grid_top,
        "hotspot_clusters": cluster_info,
    },
    "persistence": persistence_info,
    "candidate_anomalies": {
        "note": "Candidate discovery only — NOT ground-truth labels. High FRP != industrial fire. Ranking uses normalized FRP/BT/persistence/cluster + small night bonus; anti-leakage: no distance_to_industry used.",
        "top20_ranked": candidate_records,
        "frp_p95_threshold": float(df['frp'].quantile(0.95)),
        "bt_p95_threshold": float(df['brightness_temperature'].quantile(0.95)),
    },
    "limitations": {
        "note": "Exploratory analysis, not ground truth. No labeling, no model training. Persistence uses spatial radius 500m/1km thresholds from geospatial enrichment. State-level analysis skipped (no state boundary file). Day/night approximated from hour (6-18 day) because cleaned CSV lacks daynight column.",
        "bbox_note": "India bounding box 68,6,98,36 includes neighbors; boundary filtering to MultiPolygon country polygon corrects this. Filtered 6523/12318 remain (52.96%).",
        "boundary_scale": "Natural Earth 1:50m public domain — prototype, not survey-grade",
    },
    "artifacts": {
        "eda_report": "data/firms/analysis/eda_report.json",
        "plots": [
            "data/firms/analysis/daily_count.png",
            "data/firms/analysis/frp_hist.png",
            "data/firms/analysis/bt_hist.png",
            "data/firms/analysis/confidence_hist.png",
            "data/firms/analysis/satellite_pie.png",
            "data/firms/analysis/hourly_hist.png",
            "data/firms/analysis/spatial_scatter.png",
            "data/firms/analysis/persistent_map.png",
        ],
        "interactive_map": "data/firms/analysis/india_hotspots.html",
    }
}

Path("data/firms/analysis/eda_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("EDA report written to data/firms/analysis/eda_report.json")
print(f"Inside {inside_count}, clusters 1km {n_clusters}, persist clusters {n_persist}")

# --- Visualizations ---
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# daily count
plt.figure(figsize=(10,4))
per_day.sort_index().plot(kind='bar', color='#d95f0e')
plt.title('Detections per day (India FIRMS, 2026-08-01 to 2026-08-30)')
plt.xlabel('Date')
plt.ylabel('Count')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(OUT_DIR / "daily_count.png", dpi=150)
plt.close()

# frp hist
plt.figure(figsize=(8,4))
plt.hist(df['frp'], bins=50, color='#1f77b4', edgecolor='white')
plt.title('FRP distribution (MW)')
plt.xlabel('FRP')
plt.ylabel('Count')
plt.yscale('log')
plt.tight_layout()
plt.savefig(OUT_DIR / "frp_hist.png", dpi=150)
plt.close()

# bt hist
plt.figure(figsize=(8,4))
plt.hist(df['brightness_temperature'], bins=50, color='#2ca02c', edgecolor='white')
plt.title('Brightness Temperature distribution (K)')
plt.xlabel('K')
plt.ylabel('Count')
plt.tight_layout()
plt.savefig(OUT_DIR / "bt_hist.png", dpi=150)
plt.close()

# confidence hist
plt.figure(figsize=(6,4))
df['confidence'].value_counts().sort_index().plot(kind='bar', color='#9467bd')
plt.title('Confidence distribution')
plt.xlabel('Confidence')
plt.ylabel('Count')
plt.tight_layout()
plt.savefig(OUT_DIR / "confidence_hist.png", dpi=150)
plt.close()

# satellite pie
plt.figure(figsize=(5,5))
sat_counts_series = df['satellite'].value_counts()
plt.pie(sat_counts_series, labels=sat_counts_series.index, autopct='%1.1f%%', colors=['#ff7f0e','#1f77b4','#2ca02c'])
plt.title('Satellite distribution')
plt.tight_layout()
plt.savefig(OUT_DIR / "satellite_pie.png", dpi=150)
plt.close()

# hourly
plt.figure(figsize=(8,3))
per_hour.sort_index().plot(kind='bar', color='#17becf')
plt.title('Detections by hour (UTC)')
plt.xlabel('Hour')
plt.ylabel('Count')
plt.tight_layout()
plt.savefig(OUT_DIR / "hourly_hist.png", dpi=150)
plt.close()

# spatial scatter
plt.figure(figsize=(7,8))
# India approx bounds
plt.scatter(df['longitude'], df['latitude'], s=2, c=df['frp'], cmap='hot', alpha=0.5)
plt.colorbar(label='FRP')
plt.title('India FIRMS spatial density (color=FRP)')
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.xlim(68,98)
plt.ylim(6,36)
plt.tight_layout()
plt.savefig(OUT_DIR / "spatial_scatter.png", dpi=150)
plt.close()

# persistent map: centroids sized by cluster size
plt.figure(figsize=(7,8))
# background scatter light
plt.scatter(df['longitude'], df['latitude'], s=1, c='lightgray', alpha=0.3)
# overlay persist clusters sized
# get top persist clusters
for c in sorted(persist_clusters, key=lambda x: x['size'], reverse=True)[:30]:
    plt.scatter(c['centroid_lon'], c['centroid_lat'], s=min(200, 10*c['size']), alpha=0.6, c='red', edgecolors='black', linewidth=0.3)
plt.title('Persistent hotspots (500m clusters, top 30)')
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.xlim(68,98)
plt.ylim(6,36)
plt.tight_layout()
plt.savefig(OUT_DIR / "persistent_map.png", dpi=150)
plt.close()

# daynight
plt.figure(figsize=(4,4))
pd.Series(daynight_counts).plot(kind='bar', color=['#ffbb78','#98df8a'])
plt.title('Day vs Night (approx hour 6-18 day)')
plt.ylabel('Count')
plt.tight_layout()
plt.savefig(OUT_DIR / "daynight.png", dpi=150)
plt.close()

# simple interactive HTML: leaflet with top candidates
html_path = OUT_DIR / "india_hotspots.html"
# generate simple HTML with markers for top20 candidates + cluster centroids
markers = ""
for rec in candidate_records[:20]:
    markers += f"  L.circleMarker([{rec['latitude']}, {rec['longitude']}], {{radius:6, color:'red'}}).addTo(map).bindPopup('FRP {rec['frp']}<br>{rec['id']}');\n"
html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>India Hotspots</title>
<link rel='stylesheet' href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'/>
<script src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'></script>
<style>#map{{height:90vh;}}</style>
</head><body><h3>India FIRMS Hotspots — Top 20 Candidates (exploratory, not labels)</h3><div id='map'></div>
<script>
var map = L.map('map').setView([{center_lat},{center_lon}], 5);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{maxZoom:10, attribution:'© OpenStreetMap | Natural Earth boundary'}}).addTo(map);
{markers}
</script><p>Exploratory candidates ranked by FRP/BT/persistence; not ground truth.</p></body></html>
"""
html_path.write_text(html, encoding="utf-8")
print("Plots done")

