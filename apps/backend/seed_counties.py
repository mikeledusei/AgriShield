"""Seed the counties table. Run: python seed_counties.py"""
from database.connection import SessionLocal, is_configured
from database import models

COUNTIES = [
    ("Mombasa", "Coast", -4.0435, 39.6682, "mixed"),
    ("Kwale", "Coast", -4.1740, 39.4520, "crops"),
    ("Kilifi", "Coast", -3.6305, 39.8499, "crops"),
    ("Tana River", "Coast", -1.9300, 40.1000, "livestock"),
    ("Lamu", "Coast", -2.2680, 40.9020, "crops"),
    ("Taita-Taveta", "Coast", -3.4167, 38.5833, "crops"),
    ("Garissa", "North Eastern", -0.4556, 39.6417, "livestock"),
    ("Wajir", "North Eastern", 1.7484, 40.0683, "livestock"),
    ("Mandera", "North Eastern", 3.9375, 41.8600, "livestock"),
    ("Marsabit", "North Eastern", 2.3340, 37.9890, "livestock"),
    ("Isiolo", "Eastern", 0.3540, 37.5860, "livestock"),
    ("Meru", "Eastern", 0.0467, 37.6536, "crops"),
    ("Tharaka-Nithi", "Eastern", -0.2980, 37.8700, "crops"),
    ("Embu", "Eastern", -0.5330, 37.4560, "crops"),
    ("Kitui", "Eastern", -1.3670, 38.0129, "crops"),
    ("Machakos", "Eastern", -1.5172, 37.2661, "crops"),
    ("Makueni", "Eastern", -1.7829, 37.6220, "crops"),
    ("Nyandarua", "Central", -0.1500, 36.3900, "crops"),
    ("Nyeri", "Central", -0.4197, 36.9517, "crops"),
    ("Kirinyaga", "Central", -0.5003, 37.2782, "crops"),
    ("Murang'a", "Central", -0.7217, 37.1589, "crops"),
    ("Kiambu", "Central", -1.1170, 36.8170, "mixed"),
    ("Turkana", "Rift Valley", 3.1170, 35.6060, "livestock"),
    ("West Pokot", "Rift Valley", 1.5160, 35.1160, "livestock"),
    ("Samburu", "Rift Valley", 1.1720, 37.0710, "livestock"),
    ("Trans Nzoia", "Rift Valley", 1.0190, 34.9900, "crops"),
    ("Uasin Gishu", "Rift Valley", 0.5150, 35.2800, "crops"),
    ("Elgeyo-Marakwet", "Rift Valley", 1.0510, 35.5700, "crops"),
    ("Nandi", "Rift Valley", 0.1770, 35.1090, "crops"),
    ("Baringo", "Rift Valley", 0.4820, 35.9720, "livestock"),
    ("Laikipia", "Rift Valley", 0.2760, 36.8270, "crops"),
    ("Nakuru", "Rift Valley", -0.3031, 36.0800, "mixed"),
    ("Narok", "Rift Valley", -1.0930, 35.8700, "livestock"),
    ("Kajiado", "Rift Valley", -1.8500, 36.7800, "livestock"),
    ("Kericho", "Rift Valley", -0.3670, 35.2830, "crops"),
    ("Bomet", "Rift Valley", -0.7800, 35.3420, "crops"),
    ("Kakamega", "Western", 0.2820, 34.7510, "crops"),
    ("Vihiga", "Western", 0.0780, 34.7280, "crops"),
    ("Bungoma", "Western", 0.5630, 34.5610, "crops"),
    ("Busia", "Western", 0.4600, 34.1110, "crops"),
    ("Siaya", "Nyanza", -0.0610, 34.2880, "crops"),
    ("Kisumu", "Nyanza", -0.1020, 34.7610, "mixed"),
    ("Homa Bay", "Nyanza", -0.5230, 34.4570, "crops"),
    ("Migori", "Nyanza", -1.0630, 34.4730, "crops"),
    ("Kisii", "Nyanza", -0.6730, 34.7860, "crops"),
    ("Nyamira", "Nyanza", -0.5620, 34.9350, "crops"),
    ("Nairobi", "Nairobi", -1.2860, 36.8170, "mixed"),
]


def _normalize_name(value: str) -> str:
    return value.strip().replace("Taita Taveta", "Taita-Taveta").replace("Taita-Taveta", "Taita-Taveta").replace("Muranga", "Murang'a").replace("Murang a", "Murang'a").replace("Tharaka Nithi", "Tharaka-Nithi").replace("Elgeyo Marakwet", "Elgeyo-Marakwet").replace("Trans Nzioa", "Trans Nzoia")


def seed():
    if not is_configured():
        print("DATABASE_URL is not set. Add it to apps/backend/.env first.")
        return

    db = SessionLocal()
    try:
        existing = { _normalize_name(c.name): c for c in db.query(models.County).all() }
        added = 0
        updated = 0
        for name, region, lat, lon, focus in COUNTIES:
            key = _normalize_name(name)
            county = existing.get(key)
            if county is None:
                db.add(models.County(
                    name=name, region=region, latitude=lat,
                    longitude=lon, primary_focus=focus,
                ))
                added += 1
            else:
                changed = False
                for field_name, field_value in {"region": region, "latitude": lat, "longitude": lon, "primary_focus": focus}.items():
                    if getattr(county, field_name) != field_value:
                        setattr(county, field_name, field_value)
                        changed = True
                if county.name != name:
                    county.name = name
                    changed = True
                if changed:
                    updated += 1
        db.commit()
        print(f"Seeding complete. Added {added} counties and updated {updated} records.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()