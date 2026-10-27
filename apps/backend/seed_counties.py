"""Seed all 47 Kenyan counties into the counties table. Run: python seed_counties.py"""
from typing import Optional
from sqlalchemy.orm import Session
from database.connection import SessionLocal, Base, engine, is_configured
from database import models

# Canonical 47 Kenyan counties: (name, region, latitude, longitude, primary_focus)
COUNTIES = [
    ("Baringo", "Rift Valley", 0.4820, 35.9720, "livestock"),
    ("Bomet", "Rift Valley", -0.7800, 35.3420, "crops"),
    ("Bungoma", "Western", 0.5639, 34.5639, "crops"),
    ("Busia", "Western", 0.4600, 34.1110, "crops"),
    ("Elgeyo Marakwet", "Rift Valley", 1.0510, 35.5700, "crops"),
    ("Embu", "Eastern", -0.5330, 37.4560, "crops"),
    ("Garissa", "North Eastern", -0.4556, 39.6417, "livestock"),
    ("Homa Bay", "Nyanza", -0.5230, 34.4570, "mixed"),
    ("Isiolo", "Eastern", 0.3540, 37.5860, "livestock"),
    ("Kajiado", "Rift Valley", -1.8500, 36.7800, "livestock"),
    ("Kakamega", "Western", 0.2817, 34.7583, "crops"),
    ("Kericho", "Rift Valley", -0.3689, 35.2863, "crops"),
    ("Kiambu", "Central", -1.1170, 36.8170, "crops"),
    ("Kilifi", "Coast", -3.6305, 39.8499, "crops"),
    ("Kirinyaga", "Central", -0.5003, 37.2782, "crops"),
    ("Kisii", "Nyanza", -0.6730, 34.7860, "crops"),
    ("Kisumu", "Nyanza", -0.0917, 34.7680, "mixed"),
    ("Kitui", "Eastern", -1.3670, 38.0129, "mixed"),
    ("Kwale", "Coast", -4.1728, 39.4587, "crops"),
    ("Laikipia", "Rift Valley", 0.2760, 36.8270, "livestock"),
    ("Lamu", "Coast", -2.2680, 40.9020, "mixed"),
    ("Machakos", "Eastern", -1.5172, 37.2661, "crops"),
    ("Makueni", "Eastern", -1.7829, 37.6220, "crops"),
    ("Mandera", "North Eastern", 3.9375, 41.8600, "livestock"),
    ("Marsabit", "Eastern", 2.3340, 37.9890, "livestock"),
    ("Meru", "Eastern", 0.0467, 37.6536, "crops"),
    ("Migori", "Nyanza", -1.0630, 34.4730, "crops"),
    ("Mombasa", "Coast", -4.0435, 39.6682, "crops"),
    ("Murang'a", "Central", -0.7217, 37.1589, "crops"),
    ("Nairobi", "Nairobi", -1.2860, 36.8170, "crops"),
    ("Nakuru", "Rift Valley", -0.3031, 36.0800, "mixed"),
    ("Nandi", "Rift Valley", 0.1833, 35.1167, "crops"),
    ("Narok", "Rift Valley", -1.0930, 35.8700, "mixed"),
    ("Nyamira", "Nyanza", -0.5620, 34.9350, "crops"),
    ("Nyandarua", "Central", -0.1500, 36.3900, "crops"),
    ("Nyeri", "Central", -0.4197, 36.9517, "crops"),
    ("Samburu", "Rift Valley", 1.1720, 37.0710, "livestock"),
    ("Siaya", "Nyanza", 0.0333, 34.2833, "crops"),
    ("Taita Taveta", "Coast", -3.4167, 38.5833, "crops"),
    ("Tana River", "Coast", -1.9300, 40.1000, "livestock"),
    ("Tharaka Nithi", "Eastern", -0.2980, 37.8700, "crops"),
    ("Trans Nzoia", "Rift Valley", 1.0565, 34.9548, "crops"),
    ("Turkana", "Rift Valley", 3.3122, 35.5658, "livestock"),
    ("Uasin Gishu", "Rift Valley", 0.5143, 35.2698, "crops"),
    ("Vihiga", "Western", 0.0780, 34.7280, "crops"),
    ("Wajir", "North Eastern", 1.7484, 40.0683, "livestock"),
    ("West Pokot", "Rift Valley", 1.5160, 35.1160, "livestock"),
]

COUNTY_METADATA = {
    name: {"region": region, "latitude": lat, "longitude": lon, "primary_focus": focus}
    for name, region, lat, lon, focus in COUNTIES
}

COUNTY_ALIASES = {
    "muranga": "Murang'a",
    "murang'a": "Murang'a",
    "taita-taveta": "Taita Taveta",
    "taita taveta": "Taita Taveta",
    "tharaka-nithi": "Tharaka Nithi",
    "tharaka nithi": "Tharaka Nithi",
    "tharaka": "Tharaka Nithi",
    "elgeyo-marakwet": "Elgeyo Marakwet",
    "elgeyo marakwet": "Elgeyo Marakwet",
    "keiyo-marakwet": "Elgeyo Marakwet",
    "keiyo marakwet": "Elgeyo Marakwet",
    "homabay": "Homa Bay",
    "homa bay": "Homa Bay",
    "homa-bay": "Homa Bay",
    "trans-nzoia": "Trans Nzoia",
    "trans nzoia": "Trans Nzoia",
    "uasin-gishu": "Uasin Gishu",
    "uasin gishu": "Uasin Gishu",
    "tana-river": "Tana River",
    "tana river": "Tana River",
    "west-pokot": "West Pokot",
    "west pokot": "West Pokot",
    "nairobi city": "Nairobi",
}
for _c_name, *_ in COUNTIES:
    COUNTY_ALIASES[_c_name.lower()] = _c_name


def normalize_county_name(raw_name: Optional[str]) -> str:
    """Resolve common spelling/hyphenation variants to canonical county names."""
    if not raw_name:
        return ""
    cleaned = " ".join(str(raw_name).strip().split())
    lower = cleaned.lower()
    if lower in COUNTY_ALIASES:
        return COUNTY_ALIASES[lower]
    no_hyphen = lower.replace("-", " ")
    if no_hyphen in COUNTY_ALIASES:
        return COUNTY_ALIASES[no_hyphen]
    return cleaned


def ensure_counties_seeded(db: Session) -> None:
    """Ensure tables exist and all 47 Kenyan counties are seeded when table is empty."""
    try:
        if engine is not None:
            Base.metadata.create_all(bind=engine)
        count = db.query(models.County).count()
        if count >= 47:
            return
        existing = {c.name for c in db.query(models.County).all()}
        added = 0
        for name, region, lat, lon, focus in COUNTIES:
            if name not in existing:
                db.add(models.County(
                    name=name,
                    region=region,
                    latitude=lat,
                    longitude=lon,
                    primary_focus=focus,
                ))
                added += 1
        if added > 0:
            db.commit()
    except Exception:
        db.rollback()


def seed():
    if not is_configured():
        print("DATABASE_URL is not set. Add it to apps/backend/.env first.")
        return

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = {c.name for c in db.query(models.County).all()}
        added = 0
        for name, region, lat, lon, focus in COUNTIES:
            if name not in existing:
                db.add(models.County(
                    name=name, region=region, latitude=lat,
                    longitude=lon, primary_focus=focus,
                ))
                added += 1
        db.commit()
        print(f"Seeding complete. Added {added} counties (Total: {len(existing) + added}).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
