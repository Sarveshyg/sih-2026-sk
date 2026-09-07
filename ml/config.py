"""
ml/config.py — Central configuration for AI Core.

All thresholds here are PROTOTYPE parameters, not official government thresholds.
Values are chosen to make demo scenarios separable and are documented as such.
"""

# --- Classification thresholds ---
INDUSTRIAL_CLOSE_M = 500
INDUSTRIAL_NEAR_M = 2000
INDUSTRIAL_FAR_M = 5000

FOREST_CLOSE_M = 2000
AGRI_CLOSE_M = 2000

# Facility types that hint at gas-flare behaviour
FLARE_FACILITY_TYPES = {
    "refinery",
    "petroleum",
    "oil",
    "gas",
    "lng",
    "gas_plant",
    "petrochemical",
}

INDUSTRIAL_FACILITY_TYPES = {
    "refinery",
    "petroleum",
    "oil",
    "gas",
    "lng",
    "gas_plant",
    "petrochemical",
    "chemical",
    "chemical_plant",
    "power_plant",
    "power",
    "steel",
    "steel_plant",
    "factory",
    "industrial",
    "industrial_area",
    "mine",
    "cement",
    "aluminum",
}

# FRP (MW) bands — VIIRS FRP roughly 0-500+; industrial fires often 20-200
FRP_LOW = 20
FRP_MEDIUM = 50
FRP_HIGH = 100
FRP_VERY_HIGH = 180

# Brightness temperature (K)
BT_LOW = 310
BT_HIGH = 340
BT_VERY_HIGH = 360

# Persistence
PERSISTENCE_LOW = 0.3
PERSISTENCE_MODERATE = 0.6
PERSISTENCE_HIGH = 0.75

# NDVI / NDBI guidance
NDVI_VEGETATION = 0.4
NDVI_LOW = 0.2
NDBI_BUILTUP = 0.3

# --- Risk scoring weights (sum not required to be 1; final normalized to 0-100) ---
RISK_WEIGHTS = {
    "frp": 0.25,
    "persistence": 0.20,
    "industrial_proximity": 0.20,
    "anomaly": 0.15,
    "facility_criticality": 0.10,
    "confidence": 0.10,
}

# Facility criticality multipliers
CRITICAL_FACILITY_TYPES = {"refinery", "petroleum", "chemical", "power_plant", "lng", "oil", "gas"}

# --- Triage thresholds (prototype) ---
TRIAGE_TIER1_RISK = 75  # >=75 -> Tier 1 alert
TRIAGE_MONITOR_RISK = 50  # 50-74 -> monitoring
# <50 -> store only

# Risk level boundaries
RISK_LEVEL_BOUNDARIES = {
    "LOW": (0, 29),
    "MODERATE": (30, 49),
    "HIGH": (50, 74),
    "CRITICAL": (75, 100),
}
