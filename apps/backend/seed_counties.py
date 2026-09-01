"""Seed the counties table. Run: python seed_counties.py"""
from database.connection import SessionLocal, is_configured
from database import models

COUNTIES = [
    ("Uasin Gishu", "Rift Valley", 0.5143, 35.2698, "crops"),
    ("Nakuru", "Rift Valley", -0.3031, 36.0800, "mixed"),
    ("Trans Nzoia", "Rift Valley", 1.0565, 34.9548, "crops"),
    ("Nandi", "Rift Valley", 0.1833, 35.1167, "crops"),
    ("Kericho", "Rift Valley", -0.3689, 35.2863, "crops"),
    ("Turkana", "Rift Valley", 3.3122, 35.5658, "livestock"),
    ("Kajiado", "Eastern", -1.8890, 36.7890, "livestock"),
    ("Kitui", "Eastern", -1.3670, 38.0129, "crops"),
    ("Machakos", "Eastern", -1.5172, 37.2661, "crops"),
    ("Makueni", "Eastern", -1.7829, 37.6220, "crops"),
    ("Meru", "Eastern", 0.0467, 37.6536, "crops"),
    ("Muranga", "Central", -0.7217, 37.1589, "crops"),
    ("Nyeri", "Central", -0.4197, 36.9517, "crops"),
    ("Kirinyaga", "Central", -0.5003, 37.2782, "crops"),
    ("Siaya", "Nyanza", 0.0333, 34.2833, "crops"),
    ("Kisumu", "Nyanza", -0.0917, 34.7680, "mixed"),
    ("Bungoma", "Western", 0.5639, 34.5639, "crops"),
    ("Kakamega", "Western", 0.2817, 34.7583, "crops"),
    ("Kilifi", "Coast", -3.6305, 39.8499, "crops"),
    ("Kwale", "Coast", -4.1728, 39.4587, "crops"),
    ("Taita Taveta", "Coast", -3.4167, 38.5833, "crops"),
    ("Garissa", "North Eastern", -0.4556, 39.6417, "livestock"),
    ("Wajir", "North Eastern", 1.7484, 40.0683, "livestock"),
    ("Mandera", "North Eastern", 3.9375, 41.8600, "livestock"),
]


def seed():
    if not is_configured():
        print("DATABASE_URL is not set. Add it to apps/backend/.env first.")
        return

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
        print(f"Seeding complete. Added {added} counties.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()