"""
Interactive GIS Map Generator using Folium and Leaflet for Industrial Thermal Anomaly Monitoring
"""
import os
import pandas as pd
import folium
from folium.plugins import MarkerCluster, HeatMap, MiniMap, Fullscreen

def create_gis_map(
    predicted_csv: str = "artifacts_output/firms_predicted_master.csv",
    output_html: str = "artifacts_output/industrial_fire_gis_map.html"
):
    """Generate comprehensive GIS map overlay with Normal Safe Zones and Industrial Thermal Alerts."""
    if not os.path.exists(predicted_csv):
        print(f"File not found: {predicted_csv}")
        return
        
    df = pd.read_csv(predicted_csv)
    print(f"Creating GIS map from {len(df)} detections with Normal Zone & Industrial Alert layers...")
    
    center_lat = df["latitude"].median()
    center_lon = df["longitude"].median()
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=5,
        tiles="CartoDB positron"
    )
    
    # Basemaps
    folium.TileLayer("CartoDB dark_matter", name="Dark Mode (Thermal)").add_to(m)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Satellite Imagery (ESRI)"
    ).add_to(m)
    
    # Layers
    layer_industrial_alerts = folium.FeatureGroup(name="🚨 Industrial Thermal Alerts", show=True)
    layer_flares = folium.FeatureGroup(name="🔥 Active Gas Flares", show=True)
    layer_wildfires = folium.FeatureGroup(name="🌲 Active Wildfires / Forest Fires", show=True)
    layer_normal_ambient = folium.FeatureGroup(name="🟢 Normal / Ambient Surface Heat (Non-Fire)", show=False)
    cluster_layer = MarkerCluster(name="📍 Clustered Hotspots", show=False)
    
    # Heatmap of high-intensity fires only
    heat_high_fire = df[df["frp"] >= 3.0][["latitude", "longitude", "frp"]].dropna().values.tolist()
    heatmap_layer = HeatMap(
        heat_high_fire,
        name="🔥 Active Fire Intensity Heatmap (FRP >= 3MW)",
        min_opacity=0.35,
        radius=14,
        blur=10,
        max_zoom=10,
        show=False
    )
    heatmap_layer.add_to(m)
    
    # Color palette
    def get_color_and_layer(pred_cls: str, is_normal: bool):
        if is_normal:
            return "#3498db", layer_normal_ambient  # Blue / Normal ambient
        elif "Gas Flare" in pred_cls:
            return "#f39c12", layer_flares          # Amber
        elif "Industrial Facility" in pred_cls or "Coal Mine" in pred_cls:
            return "#e74c3c", layer_industrial_alerts # Red
        else:
            return "#27ae60", layer_wildfires       # Green
            
    for idx, row in df.iterrows():
        lat = row["latitude"]
        lon = row["longitude"]
        pred_cls = row.get("detailed_predicted_class", "Thermal Anomaly")
        is_normal = "Normal Background" in pred_cls
        is_ind = row.get("pred_class_fused", "") == "INDUSTRIAL_THERMAL_SOURCE"
        prob_ind = row.get("prob_industrial_fused", 0.0)
        frp = row.get("frp", 0.0)
        ti4 = row.get("bright_ti4", 0.0)
        ti5 = row.get("bright_ti5", 0.0)
        conf = row.get("confidence", "nominal")
        acq_date = row.get("acq_date", "N/A")
        acq_time = str(row.get("acq_time", "N/A")).zfill(4)
        
        p_name = row.get("nearest_plant_name", "N/A")
        p_dist = row.get("distance_to_plant_km", 999.0)
        f_name = row.get("nearest_flare_field", "N/A")
        f_dist = row.get("distance_to_flare_km", 999.0)
        m_name = row.get("nearest_mine_name", "N/A")
        m_dist = row.get("distance_to_coal_mine_km", 999.0)
        
        color, target_layer = get_color_and_layer(pred_cls, is_normal)
        
        status_badge = (
            "<span style='color: #27ae60; font-weight: bold;'>🟢 NORMAL / SAFE (Non-Fire)</span>" if is_normal else
            "<span style='color: #e74c3c; font-weight: bold;'>🚨 ACTIVE THERMAL ALERT</span>" if is_ind else
            "<span style='color: #d35400; font-weight: bold;'>🔥 ACTIVE VEGETATION FIRE</span>"
        )
        
        popup_html = f"""
        <div style="font-family: Arial, sans-serif; min-width: 240px; font-size: 12px; line-height: 1.45;">
            <div style="margin-bottom: 6px;">{status_badge}</div>
            <h4 style="margin: 0 0 6px 0; color: {color};">{pred_cls}</h4>
            <b>Industrial Probability:</b> {prob_ind:.1%}<br>
            <hr style="margin: 6px 0; border: 0; border-top: 1px solid #ddd;">
            <b>Observation Date/Time:</b> {acq_date} {acq_time[:2]}:{acq_time[2:]} UTC<br>
            <b>Coordinates:</b> {lat:.4f}°N, {lon:.4f}°E<br>
            <b>Fire Radiative Power (FRP):</b> {frp:.2f} MW<br>
            <b>Sensor Temps:</b> TI4={ti4:.1f} K | TI5={ti5:.1f} K<br>
            <b>Thermal Diff (TI4 - TI5):</b> {ti4-ti5:.1f} K<br>
            <b>Confidence:</b> {conf}<br>
            <hr style="margin: 6px 0; border: 0; border-top: 1px solid #ddd;">
            <b>Nearest Plant:</b> {p_name} ({p_dist:.2f} km)<br>
            <b>Nearest Flare:</b> {f_name} ({f_dist:.2f} km)<br>
            <b>Nearest Mine:</b> {m_name} ({m_dist:.2f} km)<br>
        </div>
        """
        
        marker = folium.CircleMarker(
            location=[lat, lon],
            radius=3 if is_normal else (6 if is_ind else 4),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.6 if is_normal else 0.85,
            weight=1,
            popup=folium.Popup(popup_html, max_width=320)
        )
        marker.add_to(target_layer)
        
        cluster_item = folium.CircleMarker(
            location=[lat, lon],
            radius=4,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=320)
        )
        cluster_item.add_to(cluster_layer)
        
    layer_industrial_alerts.add_to(m)
    layer_flares.add_to(m)
    layer_wildfires.add_to(m)
    layer_normal_ambient.add_to(m)
    cluster_layer.add_to(m)
    
    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen().add_to(m)
    MiniMap(toggle_display=True, position="bottomright").add_to(m)
    
    # Counts
    n_total = len(df)
    n_normal = df["detailed_predicted_class"].str.contains("Normal Background").sum()
    n_industrial = df["pred_class_fused"].eq("INDUSTRIAL_THERMAL_SOURCE").sum()
    n_wildfire = df["detailed_predicted_class"].str.contains("Active Wildfire").sum()
    
    legend_html = f"""
    <div style="
        position: fixed; 
        bottom: 30px; 
        left: 30px; 
        z-index: 9999; 
        background: rgba(255, 255, 255, 0.96); 
        padding: 14px 18px; 
        border-radius: 8px; 
        box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        font-family: Arial, sans-serif;
        font-size: 12px;
        line-height: 1.6;
        max-width: 290px;
    ">
        <h3 style="margin: 0 0 8px 0; font-size: 14px; color: #2c3e50;">🛰️ Thermal Anomaly & Zone Monitor</h3>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <span style="height: 12px; width: 12px; background: #e74c3c; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <b>🚨 Industrial Facility Alert</b>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <span style="height: 12px; width: 12px; background: #f39c12; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <b>🔥 Gas Flare (Upstream)</b>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <span style="height: 12px; width: 12px; background: #27ae60; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <b>🌲 Active Wildfire / Forest Fire</b>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 8px;">
            <span style="height: 12px; width: 12px; background: #3498db; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <b>🟢 Normal / Non-Fire Heat Zone</b>
        </div>
        <div style="border-top: 1px solid #eee; padding-top: 6px; font-size: 11px; color: #555;">
            <b>Total Monitored Detections:</b> {n_total:,}<br>
            <b>🚨 Industrial Thermal Alerts:</b> {n_industrial:,}<br>
            <b>🔥 Active Wildfires / Vegetation:</b> {n_wildfire:,}<br>
            <b>🟢 Normal Ambient Backgrounds:</b> {n_normal:,}
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    m.save(output_html)
    print(f"Saved enhanced GIS map with Normal Zones to: {output_html}")
    return output_html

if __name__ == "__main__":
    create_gis_map()
