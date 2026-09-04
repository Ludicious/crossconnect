"""
Recycle bin service — list, restore, and hard-delete soft-deleted records.
All hard-delete / purge operations must be authorized at the router level (admin only).
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session, joinedload

from app.models.connection import Connection
from app.models.inventory import Device, Rack, Switch, System, PatchPanel, Trunk
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


def list_deleted_patch_panels(db: Session) -> list[PatchPanel]:
    return (db.query(PatchPanel)
            .filter(PatchPanel.deleted_at.isnot(None))
            .options(joinedload(PatchPanel.rack), joinedload(PatchPanel.deleter))
            .order_by(PatchPanel.deleted_at.desc())
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


def restore_patch_panel(db: Session, pp_id: int) -> PatchPanel:
    obj = db.get(PatchPanel, pp_id)
    _restore(obj, f"Patch Panel {pp_id}")
    db.commit()
    db.refresh(obj)
    return obj


# ── Purge dependency guard ──────────────────────────────────────────────────
# Extends the "block while children exist" policy the normal soft-delete guards
# (delete_rack, delete_system, ...) already apply, to the PERMANENT purge path —
# which previously trusted the caller entirely and either crashed (NOT NULL FK:
# rack/device, rack/switch, work_order/connection) or silently corrupted live
# data (nullable FK: system/device — device.system_id got NULLed on live,
# non-deleted devices, with no error and no audit trail). See
# DESIGN_DECISIONS.md, "Purge cascade fixed."
#
# For each entity type, the (child_model, fk_attr, label) triples that must
# have ZERO rows — active OR soft-deleted-but-unpurged — referencing the row
# before it can be permanently purged. This is a read-only existence check,
# not a cascade: it turns every one of the failure modes above into the same
# clean ValueError the normal delete path already raises.
_PURGE_DEPENDENTS: dict[str, list[tuple[type, str, str]]] = {
    "racks": [
        (Device, "rack_id", "device"),
        (Switch, "rack_id", "switch"),
        (PatchPanel, "rack_id", "patch panel"),
        (Connection, "device_rack_id", "connection (device rack)"),
        (Connection, "device_patch_rack_id", "connection (device patch rack)"),
        (Connection, "switch_patch_rack_id", "connection (switch patch rack)"),
        (Connection, "switch_rack_id", "connection (switch rack)"),
    ],
    "systems": [
        (Device, "system_id", "device"),
    ],
    "devices": [
        (Connection, "device_id", "connection"),
        (Device, "parent_device_id", "child device"),
    ],
    "switches": [
        (Connection, "switch_id", "connection"),
    ],
    "patch_panels": [
        (Trunk, "panel_a_id", "trunk (endpoint A)"),
        (Trunk, "panel_b_id", "trunk (endpoint B)"),
    ],
    "work_orders": [
        (Connection, "work_order_id", "connection"),
    ],
    "connections": [
        # discovered_via_connection_id on Trunk is intentionally NOT a blocker:
        # per DESIGN_DECISIONS.md, a trunk survives deletion of the connection
        # that discovered it. _detach_trunks_from_connection() below clears the
        # pointer explicitly instead of leaving it dangling or blocking the purge.
    ],
}

_LABELS = {
    "connections": "connection",
    "work_orders": "work order",
    "devices": "device",
    "racks": "rack",
    "switches": "switch",
    "systems": "system",
    "patch_panels": "patch panel",
}


def _check_purge_dependents(db: Session, entity_type: str, obj_id: int) -> None:
    problems = []
    for child_model, fk_attr, label in _PURGE_DEPENDENTS.get(entity_type, []):
        count = db.query(child_model).filter(getattr(child_model, fk_attr) == obj_id).count()
        if count:
            problems.append(f"{count} {label}{'s' if count != 1 else ''}")
    if problems:
        name = _LABELS.get(entity_type, entity_type)
        raise ValueError(
            f"Cannot purge {name} {obj_id}: still referenced by {', '.join(problems)}. "
            f"Delete/purge those first."
        )


def _detach_trunks_from_connection(db: Session, conn_id: int) -> None:
    """Trunks survive deletion of the connection that discovered them (design
    intent) — explicitly clear the pointer rather than leaving it dangling."""
    db.query(Trunk).filter(Trunk.discovered_via_connection_id == conn_id).update(
        {"discovered_via_connection_id": None}
    )


# ── Hard delete functions (admin only — enforce in router) ────────────────

def _require_deleted(obj, label: str):
    if obj is None:
        raise ValueError(f"{label} not found.")
    if obj.deleted_at is None:
        raise ValueError(f"{label} is not in the recycle bin. Use normal delete instead.")


def _hard_delete(db: Session, model: type, obj_id: int, entity_type: str) -> None:
    obj = db.get(model, obj_id)
    label = _LABELS.get(entity_type, entity_type).capitalize()
    _require_deleted(obj, f"{label} {obj_id}")
    _check_purge_dependents(db, entity_type, obj_id)
    if entity_type == "connections":
        _detach_trunks_from_connection(db, obj_id)
    db.delete(obj)
    db.commit()


def hard_delete_connection(db: Session, conn_id: int) -> None:
    _hard_delete(db, Connection, conn_id, "connections")


def hard_delete_work_order(db: Session, wo_id: int) -> None:
    _hard_delete(db, WorkOrder, wo_id, "work_orders")


def hard_delete_device(db: Session, device_id: int) -> None:
    _hard_delete(db, Device, device_id, "devices")


def hard_delete_rack(db: Session, rack_id: int) -> None:
    _hard_delete(db, Rack, rack_id, "racks")


def hard_delete_switch(db: Session, switch_id: int) -> None:
    _hard_delete(db, Switch, switch_id, "switches")


def hard_delete_system(db: Session, system_id: int) -> None:
    _hard_delete(db, System, system_id, "systems")


def hard_delete_patch_panel(db: Session, pp_id: int) -> None:
    _hard_delete(db, PatchPanel, pp_id, "patch_panels")


# ── Purge all ─────────────────────────────────────────────────────────────

_ENTITY_MAP = {
    "connections": Connection,
    "work_orders": WorkOrder,
    "devices": Device,
    "racks": Rack,
    "switches": Switch,
    "systems": System,
    "patch_panels": PatchPanel,
}


def purge_all(db: Session, entity_type: str) -> dict:
    """
    Hard-delete every soft-deleted row of the given entity type.
    Returns {"deleted": [ids], "skipped": [{"id", "reason"}]} — a row still
    referenced by a live dependent is skipped with a reason (via the same
    guard hard_delete_* uses), never silently dropped and never allowed to
    crash or corrupt the rest of the batch.
    """
    model = _ENTITY_MAP.get(entity_type)
    if model is None:
        raise ValueError(f"Unknown entity type: {entity_type!r}. "
                         f"Valid types: {', '.join(_ENTITY_MAP)}")
    rows = db.query(model).filter(model.deleted_at.isnot(None)).all()
    deleted: list[int] = []
    skipped: list[dict] = []
    for row in rows:
        try:
            _check_purge_dependents(db, entity_type, row.id)
        except ValueError as e:
            skipped.append({"id": row.id, "reason": str(e)})
            continue
        if entity_type == "connections":
            _detach_trunks_from_connection(db, row.id)
        db.delete(row)
        deleted.append(row.id)
    db.commit()
    return {"deleted": deleted, "skipped": skipped}


def get_deleted_counts(db: Session) -> dict[str, int]:
    """Return count of soft-deleted rows per entity type."""
    return {
        name: db.query(model).filter(model.deleted_at.isnot(None)).count()
        for name, model in _ENTITY_MAP.items()
    }
