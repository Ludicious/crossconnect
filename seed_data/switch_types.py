"""
Idempotent seed for common switch DeviceType records.

Run standalone:
    .venv/bin/python -m seed_data.switch_types

Or called automatically from seed_data/seed.py on fresh installs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session
from app.models.inventory import DeviceType
from sqlalchemy import func

_SWITCH_TYPES = [
    # manufacturer, model, rack_u, slot_count, port_count, notes
    ("Cisco", "DS-C9148T-K9",      1,  1,  48,   ""),
    ("Cisco", "DS-C9710",         10, 10, 384,   ""),
    ("Cisco", "DS-C9718",         26, 18, 768,   ""),
    ("Cisco", "DS-C9220i-K9",      1,  1,  12,
     "Also has 5 IP ports for FCIP inter-site replication"),
    ("Cisco", "N7K-C7009",        14,  9, None,
     "Port count varies by line card configuration"),
    ("Cisco", "N9K-C93180TC-FX3",  1,  1,  48,   ""),
    ("Cisco", "N9K-C93180YC-FX3",  1,  1,  48,   ""),
    ("Juniper", "QFX5100S",        1,  1,  48,   ""),
]


def seed_switch_types(db: Session) -> dict:
    """
    Idempotent. Inserts DeviceType records for common switch models if
    they don't already exist (checked by manufacturer+model unique constraint).
    Returns {created: N, skipped: N}.
    """
    created = 0
    skipped = 0
    for mfg, model, rack_u, slot_count, port_count, notes in _SWITCH_TYPES:
        existing = db.query(DeviceType).filter(
            func.lower(DeviceType.manufacturer) == mfg.lower(),
            func.lower(DeviceType.model) == model.lower(),
        ).first()
        if existing:
            skipped += 1
            continue
        dt = DeviceType(
            manufacturer=mfg,
            model=model,
            category="switch",
            rack_u=rack_u,
            slot_count=slot_count,
            port_count=port_count,
            notes=notes or None,
        )
        db.add(dt)
        created += 1
    db.commit()
    return {"created": created, "skipped": skipped}


if __name__ == "__main__":
    from app.db import SessionLocal
    db = SessionLocal()
    result = seed_switch_types(db)
    print(f"Switch types: {result['created']} created, {result['skipped']} skipped")
    db.close()
