#!/usr/bin/env python3
"""
Seed the database with:
  - An admin user (prints temp password to stdout — save it)
  - Default app_settings entries

Run once after `alembic upgrade head`:
    python -m seed_data.seed

Re-running is safe: existing records are left untouched.
"""
import sys
from pathlib import Path

# Allow running as `python -m seed_data.seed` from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.models.user import User
from app.models.settings import AppSetting
from app.services.auth import create_user, generate_temp_password, get_user_by_username

DEFAULT_SETTINGS = [
    ("cable_slack_inches_per_end", "18", "Inches of slack added per cable end for length calculation"),
    ("cable_standard_lengths_m", "0.5,1,2,3,5,7,10", "Comma-separated standard cable lengths in metres"),
    ("max_rack_ru", "54", "Maximum valid RU value (1..max_rack_ru)"),
]


def seed():
    db = SessionLocal()
    try:
        # ── Admin user ────────────────────────────────────────────────────
        existing = get_user_by_username(db, "admin")
        if existing:
            print("Admin user already exists — skipping user seed.")
        else:
            temp_pw = generate_temp_password()
            create_user(
                db,
                username="admin",
                display_name="Administrator",
                password=temp_pw,
                role="admin",
                force_password_change=True,
            )
            print("=" * 60)
            print("  Admin user created.")
            print(f"  Username : admin")
            print(f"  Password : {temp_pw}")
            print("  You will be prompted to change this on first login.")
            print("  Store it now — it will not be shown again.")
            print("=" * 60)

        # ── App settings ──────────────────────────────────────────────────
        for key, value, description in DEFAULT_SETTINGS:
            existing_setting = db.get(AppSetting, key)
            if existing_setting is None:
                db.add(AppSetting(key=key, value=value, description=description))
                print(f"  Setting created: {key} = {value}")
            else:
                print(f"  Setting exists:  {key} (skipped)")

        db.commit()
        print("Seed complete.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
