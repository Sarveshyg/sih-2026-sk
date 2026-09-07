# AI-Enabled Geospatial System: Industrial Fire & Thermal Anomaly Classification

An AI-driven geospatial framework to identify, classify, and monitor **Industrial Thermal Sources** (Oil & Gas Power Complexes, Petrochemical Units, Gas Flares, Coal Mines) vs. **Forest / Agricultural / Natural Fires** and **Normal Background Surface Heat** using satellite observations from NASA FIRMS VIIRS (375m).

---

## 🚀 Key Features & Methodologies

1. **Nearest-Neighbor Spatial Join (`BallTree` with Haversine Metric)**:
   - Uses exact great-circle distance (in kilometers) to link FIRMS thermal detections with:
     - Global Oil and Gas Plant Tracker (GOGPT)
     - Global Gas Flare Volume Estimates (2012–2024 aggregated unique locations)
     - Global Coal Mine Tracker (GEM)

2. **Anti-Leakage Multi-Evidence Weak Supervision**:
   - Solves the circular distance-leakage problem by combining **physical Dozier thermal contrast ($\Delta T = T_{I4} - T_{I5}$)**, **Fire Radiative Power ($FRP$)**, **diurnal/nighttime persistence**, and **geospatial asset boundaries**.
   - Explicitly classifies **Normal / Non-Fire Ambient Surface Heat** ($\text{FRP} < 3.0\text{ MW}$, $\Delta T < 20\text{ K}$, daytime) to eliminate false alarm noise.

3. **Dual-Track Machine Learning Architecture**:
   - **Track 1: Radiometric Physical Model (Anti-Leakage)**: Tests pure satellite thermal physics ($T_{I4}, T_{I5}, \Delta T, FRP, \text{acq\_hour}, \text{is\_night}$) with **ZERO distance features**. Achieves **93.3% Test Accuracy** and **96.9% ROC-AUC**.
   - **Track 2: Fused Geospatial Model**: Combines thermal physics with geospatial proximity context. Achieves **100.0% Test Accuracy & ROC-AUC**.

4. **Interactive GIS Leaflet Web Map (`industrial_fire_gis_map.html`)**:
   - Multi-layer toggle for:
     - 🚨 `Industrial Thermal Alerts`
     - 🔥 `Active Gas Flares`
     - 🌲 `Active Wildfires / Forest Fires`
     - 🟢 `Normal / Ambient Surface Heat (Non-Fire)`
     - 🔥 `FRP Heatmap Overlay`
   - Detailed inspection popups showing exact temperatures, FRP, and nearest industrial facility.

---

## 📊 Model Evaluation Summary

| Track | Features | CV Macro F1 | Test Accuracy | Test ROC-AUC |
| :--- | :--- | :---: | :---: | :---: |
| **Radiometric Physics Model** | $T_{I4}, T_{I5}, \Delta T, FRP, \ln(1+FRP), \text{scan}, \text{track}, \text{hour}, \text{night}$ | **0.9257** | **93.25%** | **96.86%** |
| **Fused Geospatial Model** | Radiometric + Spatial Distances + Facility Metadata | **0.9981** | **100.00%** | **100.00%** |

---

## 📂 Directory Structure

```text
Trained Model/
├── src/
│   ├── spatial_join.py        # BallTree Haversine nearest-neighbor spatial join
│   ├── train.py               # Multi-evidence labeling, XGBoost models & evaluation
│   └── gis_map.py             # Interactive Folium/Leaflet GIS map generator
├── artifacts_output/
│   ├── industrial_fire_gis_map.html              # Interactive GIS web visualization
│   ├── firms_predicted_master_updated.csv        # Master predictions for all 5,144 detections
│   ├── radiometric_only_model.joblib             # Serialized pure physical model
│   ├── fused_geospatial_model.joblib             # Serialized fused geospatial model
│   ├── model_comparison_confusion_matrices.png   # Confusion matrices
│   ├── feature_importance_comparison.png         # Feature importance plots
│   └── metrics_summary.json                      # Comprehensive metrics JSON
├── pipeline.py                # End-to-end master pipeline runner
├── requirements.txt           # Python dependencies
└── README.md                  # Documentation
```

---

## ⚡ How to Run

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Full Pipeline
```bash
python pipeline.py
```

### 3. View the Interactive GIS Map
Open `artifacts_output/industrial_fire_gis_map.html` directly in any web browser.
