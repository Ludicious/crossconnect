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

_CANONICAL_MAP = {
    "action": 0, "fabric": 1, "port_description": 2, "cable_type": 3, "purpose": 4,
    "system_name_raw": 5, "device_name_raw": 6, "device_serial": 7,
    "device_rack_name_raw": 8, "device_grid": 9, "device_rack_u": 10, "device_slot": 11, "device_port": 12,
    "device_patch_rack_name_raw": 13, "device_patch_ru": 14, "device_patch_side": 15,
    "device_patch_module": 16, "device_patch_port": 17,
    "switch_patch_rack_name_raw": 18, "switch_patch_ru": 19, "switch_patch_side": 20,
    "switch_patch_module": 21, "switch_patch_port": 22,
    "switch_name_raw": 23, "switch_serial": 24, "switch_rack_name_raw": 25,
    "switch_grid": 26, "switch_rack_u": 27, "switch_slot": 28, "switch_port": 29,
    "vlan_vsan": 30, "lag_id": 31, "fiber_mode": 32, "comments": 33,
}

_HONDA_MAP = {
    "action": 0, "fabric": 1, "cable_type": 2, "purpose": 3,
    "device_name_raw": 4, "device_rack_name_raw": 5, "device_rack_u": 6,
    "device_slot": 7, "device_port": 8,
    "switch_name_raw": 9, "switch_rack_name_raw": 10, "switch_rack_u": 11,
    "switch_slot": 12, "switch_port": 13,
    "vlan_vsan": 14, "lag_id": 15, "fiber_mode": 16, "comments": 17,
}

import json as _json

DEFAULT_SETTINGS = [
    ("cable_slack_inches_per_end", "18", "Inches of slack added per cable end for length calculation"),
    ("cable_standard_lengths_m", "0.5,1,2,3,5,7,10", "Comma-separated standard cable lengths in metres"),
    ("max_rack_ru", "54", "Maximum valid RU value (1..max_rack_ru)"),
    ("audit_level", "medium", "Audit logging level: none | work_orders | medium | wide"),
    (
        "excel_import_column_map",
        _json.dumps(_CANONICAL_MAP),
        "JSON mapping CrossConnect field names to 0-based column indices for Excel import (canonical 34-col layout)",
    ),
    (
        "excel_import_skip_sheets",
        "Schema",
        "Comma-separated sheet name(s) to ignore during Excel import",
    ),
    (
        "excel_import_column_map_custom1_example",
        _json.dumps(_HONDA_MAP),
        "Example alternate column map for Honda/legacy 18-col layout (reference only — copy key and edit value to activate)",
    ),
    (
        "port_adjacency_threshold",
        "4",
        "Switch ports within this many positions of each other on the same switch are flagged as too close for redundant connections to the same device.",
    ),
    (
        "recycle_bin_enabled",
        "true",
        "When false, deletes are immediate hard deletes. Existing soft-deleted rows are retained until manually purged.",
    ),
    (
        "backup_directory",
        "./backups",
        "Directory for scheduled backups (Phase 11). Used by install script to configure cron job.",
    ),
    (
        "purpose_alias_map",
        _json.dumps({
            "isl": "storage",
            "disk_storage": "storage",
            "tape_server": "storage",
            "tape_storage": "storage",
            "disk": "storage",
            "tape": "storage",
            "san": "storage",
            "lan": "data",
            "mgmt": "management",
            "management": "management",
            "idrac": "management",
            "ilo": "management",
        }),
        "JSON object mapping lowercased raw source purpose strings to canonical purpose values (management/data/storage/other). Applied during connection import.",
    ),
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

        # ── Switch type reference data ─────────────────────────────────────
        try:
            from seed_data.switch_types import seed_switch_types
            sw_result = seed_switch_types(db)
            print(f"  Switch types: {sw_result['created']} created, {sw_result['skipped']} skipped")
        except Exception as e:
            print(f"  WARNING: switch_types seed failed: {e}")

        print("Seed complete.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
