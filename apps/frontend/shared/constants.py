"""Shared constants for AgriShield frontend."""

# Kenyan counties with approximate coordinates
KENYAN_COUNTIES = [
    {"name": "Turkana", "lat": 3.1167, "lon": 35.6000},
    {"name": "Kajiado", "lat": -1.8523, "lon": 36.7768},
    {"name": "Uasin Gishu", "lat": 0.5143, "lon": 35.2698},
    {"name": "Nakuru", "lat": -0.3031, "lon": 36.0800},
    {"name": "Kilifi", "lat": -3.5107, "lon": 39.9093},
    {"name": "Meru", "lat": 0.0467, "lon": 37.6536},
    {"name": "Kisumu", "lat": -0.0917, "lon": 34.7680},
    {"name": "Kitui", "lat": -1.3670, "lon": 38.0129},
    {"name": "Machakos", "lat": -1.5172, "lon": 37.2661},
    {"name": "Makueni", "lat": -1.7829, "lon": 37.6220},
    {"name": "Bungoma", "lat": 0.5639, "lon": 34.5639},
    {"name": "Kakamega", "lat": 0.2817, "lon": 34.7583},
    {"name": "Nandi", "lat": 0.1836, "lon": 35.1269},
    {"name": "Siaya", "lat": 0.0617, "lon": 34.2882},
    {"name": "Trans Nzoia", "lat": 1.0667, "lon": 35.0000},
    {"name": "Elgeyo Marakwet", "lat": 0.9333, "lon": 35.6667},
    {"name": "West Pokot", "lat": 1.6167, "lon": 35.1167},
    {"name": "Samburu", "lat": 1.2333, "lon": 36.7000},
    {"name": "Marsabit", "lat": 2.3333, "lon": 37.9833},
    {"name": "Isiolo", "lat": 0.3500, "lon": 37.5833},
    {"name": "Tharaka Nithi", "lat": -0.2833, "lon": 37.8667},
    {"name": "Embu", "lat": -0.5333, "lon": 37.4500},
    {"name": "Kirinyaga", "lat": -0.5000, "lon": 37.2833},
    {"name": "Murang'a", "lat": -0.7167, "lon": 37.1500},
    {"name": "Kiambu", "lat": -1.1667, "lon": 36.8333},
    {"name": "Nairobi", "lat": -1.2921, "lon": 36.8219},
    {"name": "Narok", "lat": -1.0833, "lon": 35.8667},
    {"name": "Bomet", "lat": -0.7833, "lon": 35.3500},
    {"name": "Kericho", "lat": -0.3667, "lon": 35.2833},
    {"name": "Laikipia", "lat": 0.1667, "lon": 36.5333},
    {"name": "Nyandarua", "lat": -0.2333, "lon": 36.3833},
    {"name": "Nyeri", "lat": -0.4167, "lon": 36.9500},
    {"name": "Nyamira", "lat": -0.5667, "lon": 34.9333},
    {"name": "Kisii", "lat": -0.6833, "lon": 34.7667},
    {"name": "Migori", "lat": -1.0667, "lon": 34.4667},
    {"name": "Homa Bay", "lat": -0.5333, "lon": 34.4667},
    {"name": "Busia", "lat": 0.4667, "lon": 34.1167},
    {"name": "Vihiga", "lat": 0.0500, "lon": 34.7167},
    {"name": "Garissa", "lat": -0.4500, "lon": 39.6500},
    {"name": "Wajir", "lat": 1.7500, "lon": 40.0500},
    {"name": "Mandera", "lat": 3.9333, "lon": 41.8500},
    {"name": "Tana River", "lat": -1.6667, "lon": 39.3500},
    {"name": "Lamu", "lat": -2.2667, "lon": 40.9000},
    {"name": "Taita Taveta", "lat": -3.3167, "lon": 38.3667},
    {"name": "Kwale", "lat": -4.1833, "lon": 39.4500},
]

# Short list for quick selectors
PUBLIC_COUNTIES = [
    "Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi",
    "Meru", "Kisumu", "Kitui", "Machakos", "Makueni",
    "Bungoma", "Kakamega", "Nandi", "Siaya", "Trans Nzoia",
]

# Risk level thresholds
RISK_THRESHOLDS = {"CRITICAL": 75, "HIGH": 50, "MODERATE": 25, "SAFE": 0}

RISK_COLORS = {
    "CRITICAL": "#d32f2f",
    "HIGH": "#f57c00",
    "MODERATE": "#fbc02d",
    "SAFE": "#2e7d32",
    "UNKNOWN": "#616161",
}

# Report types
REPORT_TYPES = ["Crop Yield Risk", "Livestock Forage Risk", "Comprehensive Assessment"]
REPORT_TYPE_MAP = {
    "Crop Yield Risk": "crop",
    "Livestock Forage Risk": "livestock",
    "Comprehensive Assessment": "comprehensive",
}

# Kenyan regions
KENYAN_REGIONS = [
    "Rift Valley", "Eastern", "Central", "Nyanza", "Western", "Coast", "North Eastern"
]
