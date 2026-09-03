"""
Recycle bin service — list, restore, and hard-delete soft-deleted records.
All hard-delete / purge operations must be authorized at the router level (admin only).
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session, joinedload

from app.models.connection import Connection
from app.models.inventory import Device, Rack, Switch, System
from app.models.work_order import WorkOrder


# ── List functions ────────────────────────────────────────────────────────

def list_deleted_connections(db: Session) -> list[Connection]:
    return (db.query(Connection)
            .filter(Connection.deleted_at.isnot(None))
            .order_by(Connection.deleted_at.desc())
            .all())


def list_deleted_work_orders(db: Session) -> list[WorkOrder]:
    return (db.query(WorkOrder)
            .filter(WorkOrder.deleted_at.isnot(None))
            .options(joinedload(WorkOrder.datacenter), joinedload(WorkOrder.deleter))
            .order_by(WorkOrder.deleted_at.desc())
            .all())


def list_deleted_devices(db: Session) -> list[Device]:
    return (db.query(Device)
            .filter(Device.deleted_at.isnot(None))
            .options(joinedload(Device.rack), joinedload(Device.deleter))
            .order_by(Device.deleted_at.desc())
            .all())


def list_deleted_racks(db: Session) -> list[Rack]:
    return (db.query(Rack)
            .filter(Rack.deleted_at.isnot(None))
            .options(joinedload(Rack.datacenter), joinedload(Rack.deleter))
            .order_by(Rack.deleted_at.desc())
            .all())


def list_deleted_switches(db: Session) -> list[Switch]:
    return (db.query(Switch)
            .filter(Switch.deleted_at.isnot(None))
            .options(joinedload(Switch.rack), joinedload(Switch.deleter))
            .order_by(Switch.deleted_at.desc())
            .all())


def list_deleted_systems(db: Session) -> list[System]:
    return (db.query(System)
            .filter(System.deleted_at.isnot(None))
            .options(joinedload(System.deleter))
            .order_by(System.deleted_at.desc())
            .all())


# ── Restore functions ─────────────────────────────────────────────────────

def _restore(obj, label: str):
    if obj is None:
        raise ValueError(f"{label} not found.")
    if obj.deleted_at is None:
        raise ValueError(f"{label} is not in the recycle bin.")
    obj.deleted_at = None
    obj.deleted_by = None


def restore_connection(db: Session, conn_id: int) -> Connection:
    obj = db.get(Connection, conn_id)
    _restore(obj, f"Connection {conn_id}")
    db.commit()
    db.refresh(obj)
    return obj


def restore_work_order(db: Session, wo_id: int) -> WorkOrder:
    obj = db.get(WorkOrder, wo_id)
    _restore(obj, f"Work Order {wo_id}")
    db.commit()
    db.refresh(obj)
    return obj


def restore_device(db: Session, device_id: int) -> Device:
    obj = db.get(Device, device_id)
    _restore(obj, f"Device {device_id}")
    db.commit()
    db.refresh(obj)
    return obj


def restore_rack(db: Session, rack_id: int) -> Rack:
    obj = db.get(Rack, rack_id)
    _restore(obj, f"Rack {rack_id}")
    db.commit()
    db.refresh(obj)
    return obj


def restore_switch(db: Session, switch_id: int) -> Switch:
    obj = db.get(Switch, switch_id)
    _restore(obj, f"Switch {switch_id}")
    db.commit()
    db.refresh(obj)
    return obj


def restore_system(db: Session, system_id: int) -> System:
    obj = db.get(System, system_id)
    _restore(obj, f"System {system_id}")
    db.commit()
    db.refresh(obj)
    return obj


# ── Hard delete functions (admin only — enforce in router) ────────────────

def _require_deleted(obj, label: str):
    if obj is None:
        raise ValueError(f"{label} not found.")
    if obj.deleted_at is None:
        raise ValueError(f"{label} is not in the recycle bin. Use normal delete instead.")


def hard_delete_connection(db: Session, conn_id: int) -> None:
    obj = db.get(Connection, conn_id)
    _require_deleted(obj, f"Connection {conn_id}")
    db.delete(obj)
    db.commit()


def hard_delete_work_order(db: Session, wo_id: int) -> None:
    obj = db.get(WorkOrder, wo_id)
    _require_deleted(obj, f"Work Order {wo_id}")
    db.delete(obj)
    db.commit()


def hard_delete_device(db: Session, device_id: int) -> None:
    obj = db.get(Device, device_id)
    _require_deleted(obj, f"Device {device_id}")
    db.delete(obj)
    db.commit()


def hard_delete_rack(db: Session, rack_id: int) -> None:
    obj = db.get(Rack, rack_id)
    _require_deleted(obj, f"Rack {rack_id}")
    db.delete(obj)
    db.commit()


def hard_delete_switch(db: Session, switch_id: int) -> None:
    obj = db.get(Switch, switch_id)
    _require_deleted(obj, f"Switch {switch_id}")
    db.delete(obj)
    db.commit()


def hard_delete_system(db: Session, system_id: int) -> None:
    obj = db.get(System, system_id)
    _require_deleted(obj, f"System {system_id}")
    db.delete(obj)
    db.commit()


# ── Purge all ─────────────────────────────────────────────────────────────

_ENTITY_MAP = {
    "connections": Connection,
    "work_orders": WorkOrder,
    "devices": Device,
    "racks": Rack,
    "switches": Switch,
    "systems": System,
}


def purge_all(db: Session, entity_type: str) -> int:
    """Hard delete all soft-deleted rows of the given entity type. Returns count deleted."""
    model = _ENTITY_MAP.get(entity_type)
    if model is None:
        raise ValueError(f"Unknown entity type: {entity_type!r}. "
                         f"Valid types: {', '.join(_ENTITY_MAP)}")
    rows = db.query(model).filter(model.deleted_at.isnot(None)).all()
    count = len(rows)
    for row in rows:
        db.delete(row)
    db.commit()
    return count


def get_deleted_counts(db: Session) -> dict[str, int]:
    """Return count of soft-deleted rows per entity type."""
    return {
        name: db.query(model).filter(model.deleted_at.isnot(None)).count()
        for name, model in _ENTITY_MAP.items()
    }
