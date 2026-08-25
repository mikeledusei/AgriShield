#!/usr/bin/env python3
"""
AgriShield Frontend Scaffolding Script
Creates ONLY the apps/frontend/ folder structure with all empty files.

USAGE:
    1. Place this script in your project root (AgriGuard folder).
    2. Run:  python create_frontend.py

    Existing files are skipped and never overwritten.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
# Path to your project root. Path(".") means the current directory.
BASE_DIR = Path(".")

# All paths below are relative to BASE_DIR.
FRONTEND = "apps/frontend"

# ---------------------------------------------------------------------------
# DIRECTORIES
# ---------------------------------------------------------------------------
DIRECTORIES = [
    f"{FRONTEND}",
    f"{FRONTEND}/government",
    f"{FRONTEND}/government/.streamlit",
    f"{FRONTEND}/government/pages",
    f"{FRONTEND}/government/components",
    f"{FRONTEND}/government/assets",
    f"{FRONTEND}/public",
    f"{FRONTEND}/public/.streamlit",
    f"{FRONTEND}/public/pages",
    f"{FRONTEND}/public/components",
    f"{FRONTEND}/public/assets",
    f"{FRONTEND}/shared",
    f"{FRONTEND}/shared/translations",
    f"{FRONTEND}/assets",
    f"{FRONTEND}/assets/icons",
]

# ---------------------------------------------------------------------------
# FILES
# ---------------------------------------------------------------------------
FILES = [
    # Root of apps/frontend/
    f"{FRONTEND}/.env.example",
    f"{FRONTEND}/requirements.txt",
    f"{FRONTEND}/README.md",
    f"{FRONTEND}/config.py",

    # Government dashboard
    f"{FRONTEND}/government/gov_app.py",
    f"{FRONTEND}/government/.streamlit/config.toml",
    f"{FRONTEND}/government/pages/__init__.py",
    f"{FRONTEND}/government/pages/1_overview.py",
    f"{FRONTEND}/government/pages/2_map_all_counties.py",
    f"{FRONTEND}/government/pages/3_trends.py",
    f"{FRONTEND}/government/pages/4_comparison.py",
    f"{FRONTEND}/government/pages/5_regional.py",
    f"{FRONTEND}/government/pages/6_scenarios.py",
    f"{FRONTEND}/government/pages/7_reports.py",
    f"{FRONTEND}/government/pages/8_upload_data.py",
    f"{FRONTEND}/government/pages/9_settings.py",
    f"{FRONTEND}/government/components/__init__.py",
    f"{FRONTEND}/government/components/auth.py",
    f"{FRONTEND}/government/components/advanced_charts.py",
    f"{FRONTEND}/government/components/data_tables.py",
    f"{FRONTEND}/government/components/export_tools.py",
    f"{FRONTEND}/government/assets/gov_logo.png",
    f"{FRONTEND}/government/assets/gov_style.css",

    # Public dashboard
    f"{FRONTEND}/public/public_app.py",
    f"{FRONTEND}/public/.streamlit/config.toml",
    f"{FRONTEND}/public/pages/__init__.py",
    f"{FRONTEND}/public/pages/1_home.py",
    f"{FRONTEND}/public/pages/2_my_county.py",
    f"{FRONTEND}/public/pages/3_ask_gria.py",
    f"{FRONTEND}/public/pages/4_quick_report.py",
    f"{FRONTEND}/public/pages/5_farming_tips.py",
    f"{FRONTEND}/public/pages/6_upload_photo.py",
    f"{FRONTEND}/public/components/__init__.py",
    f"{FRONTEND}/public/components/simple_gauge.py",
    f"{FRONTEND}/public/components/voice_input.py",
    f"{FRONTEND}/public/components/voice_output.py",
    f"{FRONTEND}/public/components/sms_subscription.py",
    f"{FRONTEND}/public/components/quick_actions.py",
    f"{FRONTEND}/public/assets/public_logo.png",
    f"{FRONTEND}/public/assets/public_style.css",

    # Shared components
    f"{FRONTEND}/shared/__init__.py",
    f"{FRONTEND}/shared/api_client.py",
    f"{FRONTEND}/shared/gria_chat.py",
    f"{FRONTEND}/shared/uploader.py",
    f"{FRONTEND}/shared/charts.py",
    f"{FRONTEND}/shared/map_renderer.py",
    f"{FRONTEND}/shared/gauges.py",
    f"{FRONTEND}/shared/risk_helpers.py",
    f"{FRONTEND}/shared/pdf_renderer.py",
    f"{FRONTEND}/shared/sidebar.py",
    f"{FRONTEND}/shared/translations/en.json",
    f"{FRONTEND}/shared/translations/sw.json",

    # Shared static assets
    f"{FRONTEND}/assets/kenya_counties.geojson",
    f"{FRONTEND}/assets/kenya_regions.geojson",
    f"{FRONTEND}/assets/favicon.png",
    f"{FRONTEND}/assets/icons/crop_icon.png",
    f"{FRONTEND}/assets/icons/livestock_icon.png",
    f"{FRONTEND}/assets/icons/map_icon.png",
    f"{FRONTEND}/assets/icons/report_icon.png",
]


def create_frontend():
    created_dirs = 0
    created_files = 0
    skipped = 0

    print("=" * 62)
    print("AgriShield Frontend Scaffolding")
    print(f"Target directory: {(BASE_DIR / FRONTEND).resolve()}")
    print("=" * 62)

    # Create directories
    for dir_path in DIRECTORIES:
        full_path = BASE_DIR / dir_path
        if full_path.exists():
            print(f"[SKIP DIR ] {dir_path}")
            skipped += 1
        else:
            full_path.mkdir(parents=True, exist_ok=True)
            print(f"[CREATE DIR] {dir_path}")
            created_dirs += 1

    # Create empty files
    for file_path in FILES:
        full_path = BASE_DIR / file_path

        if full_path.exists():
            print(f"[SKIP FILE] {file_path}")
            skipped += 1
            continue

        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()
        print(f"[CREATE FILE] {file_path}")
        created_files += 1

    print("=" * 62)
    print("SUMMARY")
    print(f"  Directories created : {created_dirs}")
    print(f"  Files created       : {created_files}")
    print(f"  Skipped (existing)  : {skipped}")
    print("=" * 62)
    print("Frontend structure created successfully!")


if __name__ == "__main__":
    create_frontend()