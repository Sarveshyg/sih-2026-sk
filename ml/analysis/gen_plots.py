import sys
sys.path.insert(0, ".")
from pathlib import Path
import pandas as pd
import json
from datetime import datetime, timezone

OUT_DIR = Path("data/firms/analysis")
INDIA_CSV = Path("data/firms/processed/firms_india.csv")
df = pd.read_csv(INDIA_CSV)
def parse(s):
    return datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc)
df['ts'] = df['timestamp'].apply(parse)
df['date'] = df['ts'].apply(lambda d: d.date().isoformat())
df['hour'] = df['ts'].apply(lambda d: d.hour)
df['month'] = df['ts'].apply(lambda d: d.strftime('%Y-%m'))
df['daynight_approx'] = df['hour'].apply(lambda h: 'D' if 6 <= h <= 18 else 'N')
# Load report for center
report = json.loads((OUT_DIR / "eda_report.json").read_text())
center_lat = report['spatial']['extent']['center_lat']
center_lon = report['spatial']['extent']['center_lon']
per_day = df['date'].value_counts().sort_index()
per_hour = df['hour'].value_counts().sort_index()
daynight_counts = df['daynight_approx'].value_counts().to_dict()

# Need persist_clusters for persistent map - recompute quickly or load from report
# For map, use report's persist clusters centroids
persist_clusters = report['persistence']['largest_persist_clusters'] + report['persistence']['longest_persistence']
# Use top 30 persist clusters for map

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# daily
plt.figure(figsize=(10,4))
per_day.sort_index().plot(kind='bar', color='#d95f0e')
plt.title('Detections per day (India FIRMS, 2026-08-01 to 2026-08-30)')
plt.xlabel('Date')
plt.ylabel('Count')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(OUT_DIR / "daily_count.png", dpi=150)
plt.close()
print("daily", flush=True)

plt.figure(figsize=(8,4))
plt.hist(df['frp'], bins=50, color='#1f77b4', edgecolor='white')
plt.title('FRP distribution (MW)')
plt.xlabel('FRP')
plt.ylabel('Count')
plt.yscale('log')
plt.tight_layout()
plt.savefig(OUT_DIR / "frp_hist.png", dpi=150)
plt.close()

plt.figure(figsize=(8,4))
plt.hist(df['brightness_temperature'], bins=50, color='#2ca02c', edgecolor='white')
plt.title('Brightness Temperature distribution (K)')
plt.xlabel('K')
plt.ylabel('Count')
plt.tight_layout()
plt.savefig(OUT_DIR / "bt_hist.png", dpi=150)
plt.close()

plt.figure(figsize=(6,4))
df['confidence'].value_counts().sort_index().plot(kind='bar', color='#9467bd')
plt.title('Confidence distribution')
plt.xlabel('Confidence')
plt.ylabel('Count')
plt.tight_layout()
plt.savefig(OUT_DIR / "confidence_hist.png", dpi=150)
plt.close()

plt.figure(figsize=(5,5))
sat_counts = df['satellite'].value_counts()
plt.pie(sat_counts, labels=sat_counts.index, autopct='%1.1f%%', colors=['#ff7f0e','#1f77b4','#2ca02c'])
plt.title('Satellite distribution')
plt.tight_layout()
plt.savefig(OUT_DIR / "satellite_pie.png", dpi=150)
plt.close()

plt.figure(figsize=(8,3))
per_hour.sort_index().plot(kind='bar', color='#17becf')
plt.title('Detections by hour (UTC)')
plt.xlabel('Hour')
plt.ylabel('Count')
plt.tight_layout()
plt.savefig(OUT_DIR / "hourly_hist.png", dpi=150)
plt.close()

plt.figure(figsize=(7,8))
plt.scatter(df['longitude'], df['latitude'], s=2, c=df['frp'], cmap='hot', alpha=0.5)
cbar = plt.colorbar(label='FRP')
plt.title('India FIRMS spatial density (color=FRP)')
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.xlim(68,98)
plt.ylim(6,36)
plt.tight_layout()
plt.savefig(OUT_DIR / "spatial_scatter.png", dpi=150)
plt.close()
print("spatial", flush=True)

plt.figure(figsize=(7,8))
plt.scatter(df['longitude'], df['latitude'], s=1, c='lightgray', alpha=0.3)
for c in report['persistence']['largest_persist_clusters'][:30]:
    plt.scatter(c['centroid_lon'], c['centroid_lat'], s=min(200, 10*c['size']), alpha=0.6, c='red', edgecolors='black', linewidth=0.3)
plt.title('Persistent hotspots (500m clusters, top 30)')
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.xlim(68,98)
plt.ylim(6,36)
plt.tight_layout()
plt.savefig(OUT_DIR / "persistent_map.png", dpi=150)
plt.close()

plt.figure(figsize=(4,4))
import pandas as pd
pd.Series(daynight_counts).plot(kind='bar', color=['#ffbb78','#98df8a'])
plt.title('Day vs Night (approx hour 6-18 day)')
plt.ylabel('Count')
plt.tight_layout()
plt.savefig(OUT_DIR / "daynight.png", dpi=150)
plt.close()

# interactive HTML
candidate_records = report['candidate_anomalies']['top20_ranked']
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
(OUT_DIR / "india_hotspots.html").write_text(html, encoding="utf-8")
print("plots done", flush=True)
