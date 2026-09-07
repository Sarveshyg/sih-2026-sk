"""
Geospatial Data Processing and Nearest-Neighbor Join using BallTree (Haversine Metric)
"""
import os
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

def load_and_clean_firms(filepath: str) -> pd.DataFrame:
    """Load and clean NASA FIRMS VIIRS dataset."""
    print(f"Loading FIRMS data from: {filepath}")
    df = pd.read_csv(filepath)
    
    # Standardize column types
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["bright_ti4"] = pd.to_numeric(df["bright_ti4"], errors="coerce")
    df["bright_ti5"] = pd.to_numeric(df["bright_ti5"], errors="coerce")
    df["frp"] = pd.to_numeric(df["frp"], errors="coerce")
    df["scan"] = pd.to_numeric(df["scan"], errors="coerce")
    df["track"] = pd.to_numeric(df["track"], errors="coerce")
    df["acq_time"] = df["acq_time"].astype(str).str.zfill(4)
    
    # Feature engineering: temperature difference and physical indicators
    df["temp_diff_ti4_ti5"] = df["bright_ti4"] - df["bright_ti5"]
    df["log_frp"] = np.log1p(np.maximum(0, df["frp"]))
    df["is_night"] = (df["daynight"].str.upper() == "N").astype(int)
    
    # Numeric confidence mapping: low -> 0.33, nominal -> 0.66, high -> 1.0
    conf_map = {"l": 0.33, "low": 0.33, "n": 0.66, "nominal": 0.66, "h": 1.0, "high": 1.0}
    df["confidence_numeric"] = df["confidence"].astype(str).str.lower().map(conf_map).fillna(0.5)
    
    # Extract acquisition hour
    df["acq_hour"] = df["acq_time"].str[:2].astype(int)
    
    print(f"Loaded {len(df)} FIRMS detections.")
    return df

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize DataFrame column names by trimming and replacing multiple whitespace."""
    df.columns = df.columns.str.strip().str.replace(r"\s+", " ", regex=True)
    return df

def load_and_filter_plants(filepath: str, bbox: dict = None) -> pd.DataFrame:
    """Load Global Oil and Gas Plant Tracker and filter spatially."""
    print(f"Loading Plant tracker from: {filepath}")
    df = pd.read_excel(filepath, sheet_name="Gas & Oil Units")
    df = standardize_columns(df)
    
    keep_cols = [
        "Plant name", "Fuel", "Capacity (MW)", "Status",
        "Latitude", "Longitude", "Country/Area", "Subregion"
    ]
    avail_cols = [c for c in keep_cols if c in df.columns]
    plants = df[avail_cols].copy()
    plants = plants.rename(columns={"Latitude": "latitude", "Longitude": "longitude"})
    
    plants["latitude"] = pd.to_numeric(plants["latitude"], errors="coerce")
    plants["longitude"] = pd.to_numeric(plants["longitude"], errors="coerce")
    plants["Capacity (MW)"] = pd.to_numeric(plants["Capacity (MW)"], errors="coerce").fillna(0)
    plants = plants.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    
    if bbox:
        plants = plants[
            (plants["latitude"] >= bbox["min_lat"]) & (plants["latitude"] <= bbox["max_lat"]) &
            (plants["longitude"] >= bbox["min_lon"]) & (plants["longitude"] <= bbox["max_lon"])
        ].reset_index(drop=True)
    
    print(f"Prepared {len(plants)} relevant oil & gas plant units.")
    return plants

def load_and_filter_flares(filepath: str, bbox: dict = None) -> pd.DataFrame:
    """Load Flare Volume Estimates and aggregate unique flare locations."""
    print(f"Loading Flare tracker from: {filepath}")
    df = pd.read_excel(filepath, sheet_name="2012-2024-Flare-Volume-Estimate")
    df = standardize_columns(df)
    
    keep_cols = [
        "Country", "Latitude", "Longitude", "Year", "Field Type",
        "Field Name", "Field Operator", "Flare Level", "Flaring Vol (million m3)"
    ]
    avail_cols = [c for c in keep_cols if c in df.columns]
    flares = df[avail_cols].copy()
    flares = flares.rename(columns={"Latitude": "latitude", "Longitude": "longitude"})
    
    flares["latitude"] = pd.to_numeric(flares["latitude"], errors="coerce")
    flares["longitude"] = pd.to_numeric(flares["longitude"], errors="coerce")
    flares["Flaring Vol (million m3)"] = pd.to_numeric(flares["Flaring Vol (million m3)"], errors="coerce").fillna(0)
    flares = flares.dropna(subset=["latitude", "longitude"])
    
    if bbox:
        flares = flares[
            (flares["latitude"] >= bbox["min_lat"]) & (flares["latitude"] <= bbox["max_lat"]) &
            (flares["longitude"] >= bbox["min_lon"]) & (flares["longitude"] <= bbox["max_lon"])
        ]
        
    # Aggregate across years to unique geographic flare sites
    flare_agg = flares.groupby(["latitude", "longitude"]).agg(
        Country=("Country", "first"),
        field_name=("Field Name", "first"),
        field_operator=("Field Operator", "first") if "Field Operator" in flares.columns else ("Country", "first"),
        flare_level=("Flare Level", "last"),
        mean_flaring_vol=("Flaring Vol (million m3)", "mean"),
        max_flaring_vol=("Flaring Vol (million m3)", "max"),
        active_years_count=("Year", "nunique") if "Year" in flares.columns else ("latitude", "count")
    ).reset_index()
    
    flare_agg = flare_agg.rename(columns={
        "field_name": "Field Name",
        "field_operator": "Field Operator",
        "flare_level": "Flare Level"
    })
    
    print(f"Aggregated to {len(flare_agg)} unique flare locations in region.")
    return flare_agg

def load_and_filter_coal_mines(filepath: str, bbox: dict = None) -> pd.DataFrame:
    """Load Coal Mine Tracker and filter spatially."""
    print(f"Loading Coal Mine tracker from: {filepath}")
    df_open = pd.read_excel(filepath, sheet_name="Non-closed mines")
    df_open = standardize_columns(df_open)
    
    keep_cols = [
        "GEM Mine ID", "Country / Area", "Mine Name", "Status",
        "Mine Type", "Latitude", "Longitude", "Location Accuracy"
    ]
    avail_cols = [c for c in keep_cols if c in df_open.columns]
    mines = df_open[avail_cols].copy()
    mines = mines.rename(columns={"Latitude": "latitude", "Longitude": "longitude"})
    
    mines["latitude"] = pd.to_numeric(mines["latitude"], errors="coerce")
    mines["longitude"] = pd.to_numeric(mines["longitude"], errors="coerce")
    mines = mines.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    
    if bbox:
        mines = mines[
            (mines["latitude"] >= bbox["min_lat"]) & (mines["latitude"] <= bbox["max_lat"]) &
            (mines["longitude"] >= bbox["min_lon"]) & (mines["longitude"] <= bbox["max_lon"])
        ].reset_index(drop=True)
        
    print(f"Prepared {len(mines)} relevant coal mines.")
    return mines

def spatial_nearest_join(events_df: pd.DataFrame, ref_df: pd.DataFrame, prefix: str) -> tuple:
    """
    Perform nearest-neighbor spatial join using BallTree with Haversine metric.
    Computes exact geographic distance in kilometers (Earth radius = 6371.0 km).
    """
    if len(ref_df) == 0:
        events_df[f"distance_to_{prefix}_km"] = 9999.0
        return events_df, np.array([])
    
    # Convert lat/lon degrees to radians
    event_rad = np.radians(events_df[["latitude", "longitude"]].values)
    ref_rad = np.radians(ref_df[["latitude", "longitude"]].values)
    
    # Fit BallTree on reference coordinates
    tree = BallTree(ref_rad, metric="haversine")
    
    # Query nearest point (k=1)
    distances_rad, indices = tree.query(event_rad, k=1)
    
    # Convert angular distance (radians) to kilometers
    earth_radius_km = 6371.0
    distances_km = distances_rad[:, 0] * earth_radius_km
    nearest_idx = indices[:, 0]
    
    events_df[f"distance_to_{prefix}_km"] = distances_km
    events_df[f"log_distance_to_{prefix}"] = np.log1p(distances_km)
    
    return events_df, nearest_idx

def build_enriched_dataset(
    firms_file: str,
    plants_file: str,
    flares_file: str,
    coal_file: str,
    output_file: str = "firms_industrial_dataset_enriched.csv"
) -> pd.DataFrame:
    """End-to-end spatial enrichment pipeline."""
    firms = load_and_clean_firms(firms_file)
    
    # Define bounding box with a 2-degree buffer around FIRMS coverage
    bbox = {
        "min_lat": max(-90.0, firms["latitude"].min() - 2.0),
        "max_lat": min(90.0, firms["latitude"].max() + 2.0),
        "min_lon": max(-180.0, firms["longitude"].min() - 2.0),
        "max_lon": min(180.0, firms["longitude"].max() + 2.0),
    }
    print(f"Spatial bounding box with buffer: {bbox}")
    
    plants = load_and_filter_plants(plants_file, bbox)
    flares = load_and_filter_flares(flares_file, bbox)
    mines = load_and_filter_coal_mines(coal_file, bbox)
    
    # 1. Join with Plants
    firms, plant_idx = spatial_nearest_join(firms, plants, "plant")
    if len(plant_idx) > 0:
        firms["nearest_plant_name"] = plants.iloc[plant_idx]["Plant name"].values
        firms["nearest_plant_fuel"] = plants.iloc[plant_idx]["Fuel"].fillna("Unknown").values
        firms["nearest_plant_capacity_mw"] = plants.iloc[plant_idx]["Capacity (MW)"].fillna(0).values
        firms["nearest_plant_status"] = plants.iloc[plant_idx]["Status"].fillna("Unknown").values
        
    # 2. Join with Flares
    firms, flare_idx = spatial_nearest_join(firms, flares, "flare")
    if len(flare_idx) > 0:
        firms["nearest_flare_field"] = flares.iloc[flare_idx]["Field Name"].fillna("Unknown").values
        firms["nearest_flare_operator"] = flares.iloc[flare_idx]["Field Operator"].fillna("Unknown").values
        firms["nearest_flare_level"] = flares.iloc[flare_idx]["Flare Level"].fillna("Unknown").values
        firms["nearest_flare_mean_vol"] = flares.iloc[flare_idx]["mean_flaring_vol"].fillna(0).values
        firms["nearest_flare_active_years"] = flares.iloc[flare_idx]["active_years_count"].fillna(0).values

    # 3. Join with Coal Mines
    firms, mine_idx = spatial_nearest_join(firms, mines, "coal_mine")
    if len(mine_idx) > 0:
        firms["nearest_mine_name"] = mines.iloc[mine_idx]["Mine Name"].fillna("Unknown").values
        firms["nearest_mine_type"] = mines.iloc[mine_idx]["Mine Type"].fillna("Unknown").values
        firms["nearest_mine_status"] = mines.iloc[mine_idx]["Status"].fillna("Unknown").values

    # Minimum distance to any industrial infrastructure
    firms["min_distance_to_industrial_km"] = firms[[
        "distance_to_plant_km",
        "distance_to_flare_km",
        "distance_to_coal_mine_km"
    ]].min(axis=1)
    firms["log_min_industrial_distance"] = np.log1p(firms["min_distance_to_industrial_km"])

    # Proximity boolean features (useful inductive biases)
    firms["is_near_plant_3km"] = (firms["distance_to_plant_km"] <= 3.0).astype(int)
    firms["is_near_flare_3km"] = (firms["distance_to_flare_km"] <= 3.0).astype(int)
    firms["is_near_mine_5km"] = (firms["distance_to_coal_mine_km"] <= 5.0).astype(int)
    firms["is_near_industrial_5km"] = (firms["min_distance_to_industrial_km"] <= 5.0).astype(int)

    # Save to CSV
    firms.to_csv(output_file, index=False)
    print(f"Successfully created and saved enriched dataset to {output_file} ({len(firms)} rows, {len(firms.columns)} columns).")
    
    return firms

if __name__ == "__main__":
    build_enriched_dataset(
        firms_file="J1_VIIRS_C2_South_Asia_7d.csv",
        plants_file="Global Oil and Gas Plant Tracker (GOGPT) - August 2026.xlsx",
        flares_file="2012-2024-Flare-Volume-Estimates-by-individual-Flare-Location.xlsx",
        coal_file="Global Coal Mine Tracker, August 2026.xlsx"
    )
