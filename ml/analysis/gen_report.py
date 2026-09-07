import sys
sys.path.insert(0, ".")
import json, math
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
import pandas as pd
import numpy as np

INDIA_CSV = Path("data/firms/processed/firms_india.csv")
BOUNDARY = Path("data/geospatial/boundaries/india.geojson")
OUT_DIR = Path("data/firms/analysis")
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("load", flush=True)
df = pd.read_csv(INDIA_CSV)
print(f"loaded {len(df)}", flush=True)
def parse(s):
    return datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc)
df['ts'] = df['timestamp'].apply(parse)
df['date'] = df['ts'].apply(lambda d: d.date().isoformat())
df['hour'] = df['ts'].apply(lambda d: d.hour)
df['month'] = df['ts'].apply(lambda d: d.strftime('%Y-%m'))
df['daynight_approx'] = df['hour'].apply(lambda h: 'D' if 6 <= h <= 18 else 'N')
print("parsed", flush=True)

total_records = len(df)
unique_ids = df['id'].nunique()
duplicate_ids = total_records - unique_ids
missing = df.isnull().sum().to_dict()
invalid_lat = int(((df['latitude'] < -90) | (df['latitude'] > 90)).sum())
invalid_lon = int(((df['longitude'] < -180) | (df['longitude'] > 180)).sum())
timestamp_range = [min(df['ts']).isoformat().replace('+00:00','Z'), max(df['ts']).isoformat().replace('+00:00','Z')]
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
print("numeric", flush=True)
from ml.geospatial.boundary_filter import load_boundary, is_inside
boundary = load_boundary(BOUNDARY)
inside_count = sum(1 for _, r in df.iterrows() if is_inside(float(r['latitude']), float(r['longitude']), boundary))
outside_count = total_records - inside_count
print(f"verify inside {inside_count}", flush=True)

per_day = df['date'].value_counts().sort_index()
per_hour = df['hour'].value_counts().sort_index()
daynight_counts = df['daynight_approx'].value_counts().to_dict()
sat_counts = df['satellite'].value_counts().to_dict()
per_month = df['month'].value_counts().to_dict()
mean_daily = float(per_day.mean())
std_daily = float(per_day.std())
threshold = mean_daily + 2*std_daily
high_days = per_day[per_day > threshold].to_dict()
if not high_days:
    high_days = per_day.nlargest(5).to_dict()
high_days = {str(k): int(v) for k,v in high_days.items()}
daily_frp = df.groupby('date')['frp'].agg(['count','mean','median','max','min','std']).round(2)
daily_frp_dict = {}
for idx, row in daily_frp.iterrows():
    daily_frp_dict[str(idx)] = {k: (float(v) if not pd.isna(v) else None) for k,v in row.to_dict().items()}
print("temporal ok", flush=True)

thermal_stats = numeric_summary
# Use subset before nlargest to avoid pandas bug with timezone-aware 'ts' column on Python 3.14
top50 = df[['id','latitude','longitude','frp','brightness_temperature','confidence','timestamp','satellite']].nlargest(50, 'frp').copy()
top50_records = top50.to_dict(orient='records')
print("thermal ok", flush=True)

lat_min, lat_max = float(df['latitude'].min()), float(df['latitude'].max())
lon_min, lon_max = float(df['longitude'].min()), float(df['longitude'].max())
center_lat, center_lon = float(df['latitude'].mean()), float(df['longitude'].mean())
GRID = 0.5
df['grid_lat'] = (df['latitude'] // GRID * GRID).round(2)
df['grid_lon'] = (df['longitude'] // GRID * GRID).round(2)
grid_counts = df.groupby(['grid_lat','grid_lon']).size().sort_values(ascending=False)
grid_top = [{"grid_lat": float(k[0]), "grid_lon": float(k[1]), "count": int(v)} for k,v in grid_counts.head(20).items()]
print("spatial grid ok", flush=True)

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
print("Clustering 1km...", flush=True)
labels_1km, clusters_1km = cluster_points(lats, lons, 1000)
# Keep labels separate to avoid pandas hang with ts column
hotspot_clusters = {cid: members for cid, members in clusters_1km.items() if len(members) >=3}
n_clusters = len(hotspot_clusters)
noise = sum(len(m) for cid, m in clusters_1km.items() if len(m) <3)
size_dist = Counter([len(m) for m in hotspot_clusters.values()])
largest = sorted(hotspot_clusters.items(), key=lambda x: len(x[1]), reverse=True)[:10]
largest_details = []
for cid, members in largest:
    # Use numpy arrays to avoid pandas iloc hang with ts column
    lats_m = [lats[i] for i in members]
    lons_m = [lons[i] for i in members]
    frps = [float(df['frp'].iloc[i]) for i in members]
    sats = [df['satellite'].iloc[i] for i in members]
    dts = [datetime.fromisoformat(df['timestamp'].iloc[i].replace('Z','+00:00')) for i in members]
    largest_details.append({
        "cluster_id": int(cid),
        "size": int(len(members)),
        "centroid_lat": float(np.mean(lats_m)),
        "centroid_lon": float(np.mean(lons_m)),
        "frp_mean": float(np.mean(frps)),
        "frp_max": float(max(frps)),
        "date_span_days": int((max(dts) - min(dts)).days) +1 if len(dts)>1 else 1,
        "satellites": dict(Counter(sats)),
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
print(f"1km done n_clusters {n_clusters}", flush=True)

print("Clustering 500m...", flush=True)
labels_500, clusters_500 = cluster_points(lats, lons, 500)
n_persist = len(clusters_500)
persist_clusters = []
for cid, members in clusters_500.items():
    # Use direct arrays to avoid pandas sort hang with ts
    member_dates = [df['date'].iloc[i] for i in members]
    distinct_dates = len(set(member_dates))
    # span via timestamp strings
    if len(members) > 1:
        dts = [datetime.fromisoformat(df['timestamp'].iloc[i].replace('Z','+00:00')) for i in members]
        span_days = int((max(dts) - min(dts)).days)
    else:
        span_days = 0
    lats_m = [lats[i] for i in members]
    lons_m = [lons[i] for i in members]
    frps = [float(df['frp'].iloc[i]) for i in members]
    sats = [df['satellite'].iloc[i] for i in members]
    persist_clusters.append({
        "cluster_id": int(cid),
        "size": int(len(members)),
        "distinct_dates": int(distinct_dates),
        "span_days": int(span_days),
        "centroid_lat": float(np.mean(lats_m)),
        "centroid_lon": float(np.mean(lons_m)),
        "satellites": dict(Counter(sats)),
        "frp_max": float(max(frps)),
        "frp_mean": float(np.mean(frps)),
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
print(f"persist done {n_persist} isolated {isolated}", flush=True)

# candidates - use subset without 'ts' to avoid hang
candidate_base = df[['id','latitude','longitude','frp','brightness_temperature','confidence','timestamp','satellite','daynight_approx']].copy()
candidate_base['persist_cluster'] = labels_500
cluster_size_map = {c['cluster_id']: c['size'] for c in persist_clusters}
distinct_map = {c['cluster_id']: c['distinct_dates'] for c in persist_clusters}
candidate_base['persist_size'] = candidate_base['persist_cluster'].map(cluster_size_map)
candidate_base['distinct_dates_c'] = candidate_base['persist_cluster'].map(distinct_map)
def norm(s):
    return (s - s.min()) / (s.max() - s.min() + 1e-9)
candidate_base['norm_frp'] = norm(candidate_base['frp'])
candidate_base['norm_bt'] = norm(candidate_base['brightness_temperature'])
candidate_base['norm_persist'] = norm(candidate_base['distinct_dates_c'].astype(float))
candidate_base['norm_cluster'] = norm(candidate_base['persist_size'].astype(float))
candidate_base['night_bonus'] = (candidate_base['daynight_approx'] == 'N').astype(int) * 0.05
candidate_base['candidate_score'] = 0.4*candidate_base['norm_frp'] + 0.2*candidate_base['norm_bt'] + 0.2*candidate_base['norm_persist'] + 0.2*candidate_base['norm_cluster'] + candidate_base['night_bonus']
candidates = candidate_base[['id','latitude','longitude','frp','brightness_temperature','confidence','timestamp','satellite','persist_size','distinct_dates_c','candidate_score','daynight_approx']].nlargest(20, 'candidate_score').copy()
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
        "detections_by_hour": {int(k): int(v) for k,v in pd.Series(df['hour'].value_counts()).to_dict().items()},
        "daynight_approx": daynight_counts,
        "detections_by_satellite": sat_counts,
        "detections_per_month": per_month,
        "daily_frp_stats": {k: {kk: (float(v) if not pd.isna(v) else None) for kk, v in vals.items()} for k, vals in df.groupby('date')['frp'].agg(['count','mean','median','max','min','std']).round(2).to_dict('index').items()},
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
print("report written", flush=True)
