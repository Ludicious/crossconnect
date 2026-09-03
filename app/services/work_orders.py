"""
Work order and connection service.
All business rules enforced here; routers only handle HTTP concerns.
"""
import logging
from datetime import date, datetime

_log = logging.getLogger(__name__)
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_

import json as _json

from app.models.work_order import WorkOrder, VALID_STATUSES, VALID_WORK_TYPES
from app.services.cable_length import calculate_and_store
from app.services.audit import write_audit
from app.services.settings import get_bool_setting, get_setting
from app.models.connection import Connection, INSTALL_STATUSES, ACTIONS, CABLE_TYPES, PURPOSES
from app.models.user import User

# ── Status transition table ───────────────────────────────────────────────
TRANSITIONS = {
    "draft":       {"issued", "cancelled"},
    "issued":      {"draft", "in_progress", "cancelled"},
    "in_progress": {"complete", "cancelled"},
    "complete":    set(),
    "cancelled":   set(),
}

# Mandatory connection fields — checked on save/issue
MANDATORY_FIELDS = [
    "action", "cable_type", "purpose",
    "device_rack_name_raw", "device_rack_u", "device_slot", "device_port",
    "switch_rack_name_raw", "switch_rack_u", "switch_slot", "switch_port",
]


# ── Work orders ───────────────────────────────────────────────────────────

def list_work_orders(db: Session, dc_id: Optional[int] = None,
                     status: Optional[str] = None,
                     created_by: Optional[int] = None) -> list[WorkOrder]:
    q = db.query(WorkOrder).options(
        joinedload(WorkOrder.datacenter),
        joinedload(WorkOrder.creator),
    ).filter(WorkOrder.deleted_at.is_(None))
    if dc_id:
        q = q.filter(WorkOrder.datacenter_id == dc_id)
    if status:
        q = q.filter(WorkOrder.status == status)
    if created_by:
        q = q.filter(WorkOrder.created_by == created_by)
    return q.order_by(WorkOrder.updated_at.desc()).all()


def get_work_order(db: Session, wo_id: int) -> Optional[WorkOrder]:
    return db.query(WorkOrder).options(
        joinedload(WorkOrder.datacenter),
        joinedload(WorkOrder.creator),
    ).filter(WorkOrder.id == wo_id, WorkOrder.deleted_at.is_(None)).first()


def create_work_order(db: Session, name: str, datacenter_id: int,
                      work_type: str, created_by: int,
                      target_date: Optional[date] = None,
                      notes: str = "",
                      change_req_number: Optional[str] = None) -> WorkOrder:
    if work_type not in VALID_WORK_TYPES:
        raise ValueError(f"Invalid work type: {work_type}")
    wo = WorkOrder(
        name=name, datacenter_id=datacenter_id, work_type=work_type,
        created_by=created_by, target_date=target_date,
        notes=notes or None, status="draft",
        change_req_number=change_req_number,
    )
    db.add(wo)
    db.flush()
    write_audit(db, created_by, "medium", "work_order", wo.id, "create",
                detail=f"Created WO '{wo.name}' type={work_type}")
    db.commit()
    db.refresh(wo)
    return wo


def update_work_order(db: Session, wo: WorkOrder, user_id: Optional[int] = None, **kwargs) -> WorkOrder:
    if "work_type" in kwargs and kwargs["work_type"] not in VALID_WORK_TYPES:
        raise ValueError(f"Invalid work type: {kwargs['work_type']}")
    for k, v in kwargs.items():
        setattr(wo, k, v or None if k == "notes" else v)
    write_audit(db, user_id, "medium", "work_order", wo.id, "update",
                detail=f"Updated WO '{wo.name}'")
    db.commit()
    db.refresh(wo)
    return wo


def transition_status(db: Session, wo: WorkOrder, new_status: str, user: User) -> WorkOrder:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Unknown status: {new_status}")
    allowed = TRANSITIONS.get(wo.status, set())
    if new_status not in allowed:
        raise ValueError(f"Cannot move from '{wo.status}' to '{new_status}'.")

    # On issue: check all non-deleted rows pass mandatory field validation
    if new_status == "issued":
        errors = _validate_all_connections(db, wo.id)
        if errors:
            # Attach detail to the exception so the router can pass it to the template
            exc = ValueError(f"{len(errors)} connection row(s) have validation errors. Fix them before issuing.")
            exc.row_errors = errors  # list of {id, errors}
            raise exc

    # On complete: soft-delete all R-action connections
    if new_status == "complete":
        now = datetime.utcnow()
        db.query(Connection).filter(
            Connection.work_order_id == wo.id,
            Connection.action == "R",
            Connection.deleted_at.is_(None),
        ).update({"deleted_at": now, "deleted_by": user.id})

    old_status = wo.status
    wo.status = new_status
    write_audit(db, user.id, "work_orders", "work_order", wo.id, "status_change",
                detail=f"'{wo.name}' {old_status} → {new_status}")
    db.commit()
    db.refresh(wo)
    return wo


def delete_work_order(db: Session, wo: WorkOrder, user_id: Optional[int] = None) -> None:
    if wo.status not in ("draft", "cancelled"):
        raise ValueError("Only draft or cancelled work orders can be deleted.")
    wo_name, wo_id = wo.name, wo.id
    write_audit(db, user_id, "medium", "work_order", wo_id, "delete",
                detail=f"Deleted WO '{wo_name}'")
    if get_bool_setting(db, "recycle_bin_enabled", default=True):
        wo.deleted_at = datetime.utcnow()
        wo.deleted_by = user_id
    else:
        db.delete(wo)
    db.commit()


# ── Connections ───────────────────────────────────────────────────────────

def list_connections(db: Session, wo_id: int,
                     include_deleted: bool = False) -> list[Connection]:
    q = db.query(Connection).filter(Connection.work_order_id == wo_id)
    if not include_deleted:
        q = q.filter(Connection.deleted_at.is_(None))
    return q.order_by(Connection.id).all()


def get_connection(db: Session, conn_id: int) -> Optional[Connection]:
    return db.query(Connection).filter(Connection.id == conn_id).first()


def _validate_connection(c: Connection) -> list[str]:
    """Return list of error strings for a single connection row."""
    errors = []
    if c.action not in ACTIONS:
        errors.append("ACTION must be A, R, or C")
    if c.cable_type not in CABLE_TYPES:
        errors.append(f"CABLE TYPE must be one of: {', '.join(CABLE_TYPES)}")
    if c.purpose not in PURPOSES:
        errors.append(f"PURPOSE must be one of: {', '.join(PURPOSES)}")
    if not c.device_rack_name_raw:
        errors.append("DEVICE RACK is required")
    if not c.device_rack_u or not (1 <= c.device_rack_u <= 54):
        errors.append("DEVICE RACK U must be 1–54")
    if not c.device_slot:
        errors.append("DEVICE SLOT is required")
    if not c.device_port:
        errors.append("DEVICE PORT is required")
    if not c.switch_rack_name_raw:
        errors.append("SWITCH RACK is required")
    if not c.switch_rack_u or not (1 <= c.switch_rack_u <= 54):
        errors.append("SWITCH RACK U must be 1–54")
    if not c.switch_slot:
        errors.append("SWITCH SLOT is required")
    if not c.switch_port:
        errors.append("SWITCH PORT is required")
    return errors


def _validate_all_connections(db: Session, wo_id: int) -> list[dict]:
    conns = list_connections(db, wo_id)
    all_errors = []
    for c in conns:
        errs = _validate_connection(c)
        if errs:
            all_errors.append({"id": c.id, "errors": errs})
    return all_errors


def _check_switch_port_duplicate(db: Session, conn: Connection,
                                  exclude_id: Optional[int] = None) -> Optional[str]:
    """
    Hard block: same switch+slot+port in any non-deleted non-R row.
    Checks via switch_id FK (when set) OR via switch_name_raw (free-text path).
    At least one identifier + slot + port must be present to trigger.
    """
    if conn.action == "R":
        return None
    if not (conn.switch_slot and conn.switch_port):
        return None

    # Build filter — prefer FK, fall back to raw name
    if conn.switch_id:
        switch_filter = Connection.switch_id == conn.switch_id
    elif conn.switch_name_raw:
        switch_filter = func.lower(Connection.switch_name_raw) == conn.switch_name_raw.lower()
    else:
        return None

    q = db.query(Connection).filter(
        switch_filter,
        func.lower(Connection.switch_slot) == conn.switch_slot.lower(),
        func.lower(Connection.switch_port) == conn.switch_port.lower(),
        Connection.action != "R",
        Connection.deleted_at.is_(None),
    )
    if exclude_id:
        q = q.filter(Connection.id != exclude_id)
    existing = q.first()
    if existing:
        wo = db.get(WorkOrder, existing.work_order_id)
        return (f"Switch port {conn.switch_slot}/{conn.switch_port} is already "
                f"assigned in work order '{wo.name if wo else existing.work_order_id}'.")
    return None


def _check_device_port_warning(db: Session, conn: Connection,
                                 exclude_id: Optional[int] = None) -> Optional[str]:
    """Soft warning: same device+slot+port in a different work order by same architect."""
    if not all([conn.device_id, conn.device_slot, conn.device_port]):
        return None
    q = db.query(Connection).join(WorkOrder).filter(
        Connection.device_id == conn.device_id,
        Connection.device_slot == conn.device_slot,
        Connection.device_port == conn.device_port,
        Connection.deleted_at.is_(None),
        WorkOrder.created_by == db.get(WorkOrder, conn.work_order_id).created_by,
        Connection.work_order_id != conn.work_order_id,
    )
    if exclude_id:
        q = q.filter(Connection.id != exclude_id)
    existing = q.first()
    if existing:
        wo = db.get(WorkOrder, existing.work_order_id)
        return (f"Warning: device port {conn.device_slot}/{conn.device_port} also "
                f"appears in your work order '{wo.name if wo else existing.work_order_id}'.")
    return None


def _coerce_vlan(val) -> Optional[str]:
    """Return the VLAN/VSAN string, logging a warning if it looks like Excel
    collapsed a comma-separated list (e.g. "100,101" → integer 100101)."""
    s = str(val).strip() if val is not None else ""
    if not s:
        return None
    if s.isdigit() and len(s) > 6:
        _log.warning("Probable collapsed VLAN/VSAN value '%s' — Excel may have coerced a comma-separated list to integer", s)
    return s


def resolve_purpose(raw: str, alias_map: dict) -> str:
    """Map a raw purpose string to a canonical PURPOSES value.

    Lookup order: alias_map (case-insensitive) → already canonical → "data".
    Falls back to "data" (not "management") so unknown infra terms don't
    mis-classify SAN links.
    """
    key = raw.strip().lower()
    if key in alias_map:
        return alias_map[key]
    if key in PURPOSES:
        return key
    return "data"


def _conn_from_form(data: dict, alias_map: Optional[dict] = None) -> dict:
    """Coerce form dict to connection field dict."""
    def _s(v):
        return "" if v is None else str(v)

    data = {k: _s(v) for k, v in data.items()}

    def _int(v):
        try: return int(v) if v else None
        except (ValueError, TypeError): return None

    raw_purpose = data.get("purpose", "").strip()
    purpose = resolve_purpose(raw_purpose, alias_map or {})

    return dict(
        action=data.get("action", "").strip().upper(),
        fabric=data.get("fabric", "").strip().upper() or None,
        port_description=data.get("port_description", "").strip() or None,
        cable_type=data.get("cable_type", "").strip(),
        purpose=purpose,
        system_name_raw=data.get("system_name_raw", "").strip() or None,
        device_name_raw=data.get("device_name_raw", "").strip() or None,
        device_serial=data.get("device_serial", "").strip() or None,
        device_rack_name_raw=data.get("device_rack_name_raw", "").strip() or None,
        device_grid=data.get("device_grid", "").strip() or None,
        device_rack_u=_int(data.get("device_rack_u")),
        device_slot=data.get("device_slot", "").strip() or None,
        device_port=data.get("device_port", "").strip() or None,
        device_patch_rack_name_raw=data.get("device_patch_rack_name_raw", "").strip() or None,
        device_patch_ru=_int(data.get("device_patch_ru")),
        device_patch_side=data.get("device_patch_side", "").strip() or None,
        device_patch_module=data.get("device_patch_module", "").strip() or None,
        device_patch_port=data.get("device_patch_port", "").strip() or None,
        switch_patch_rack_name_raw=data.get("switch_patch_rack_name_raw", "").strip() or None,
        switch_patch_ru=_int(data.get("switch_patch_ru")),
        switch_patch_side=data.get("switch_patch_side", "").strip() or None,
        switch_patch_module=data.get("switch_patch_module", "").strip() or None,
        switch_patch_port=data.get("switch_patch_port", "").strip() or None,
        switch_name_raw=data.get("switch_name_raw", "").strip() or None,
        switch_serial=data.get("switch_serial", "").strip() or None,
        switch_rack_name_raw=data.get("switch_rack_name_raw", "").strip() or None,
        switch_grid=data.get("switch_grid", "").strip() or None,
        switch_rack_u=_int(data.get("switch_rack_u")),
        switch_slot=data.get("switch_slot", "").strip() or None,
        switch_port=data.get("switch_port", "").strip() or None,
        vlan_vsan=_coerce_vlan(data.get("vlan_vsan", "")),
        comments=data.get("comments", "").strip() or None,
        lag_id=data.get("lag_id", "").strip() or None,
        lag_member_index=_int(data.get("lag_member_index")),
        fiber_mode=data.get("fiber_mode", "").strip() or None,
        install_status=data.get("install_status", "pending"),
    )


_DEFAULT_PURPOSE_ALIAS_MAP = {
    "isl": "storage", "disk_storage": "storage", "tape_server": "storage",
    "tape_storage": "storage", "disk": "storage", "tape": "storage", "san": "storage",
    "lan": "data",
    "mgmt": "management", "management": "management", "idrac": "management", "ilo": "management",
}


def _load_purpose_alias_map(db: Session) -> dict:
    """Read purpose_alias_map setting; upsert the default if missing."""
    from app.services.settings import upsert_setting
    from app.models.settings import AppSetting
    row = db.get(AppSetting, "purpose_alias_map")
    if row is None:
        upsert_setting(db, "purpose_alias_map", _json.dumps(_DEFAULT_PURPOSE_ALIAS_MAP))
        db.commit()
        return dict(_DEFAULT_PURPOSE_ALIAS_MAP)
    try:
        return _json.loads(row.value)
    except (ValueError, TypeError):
        return {}


def create_connection(db: Session, wo_id: int, form_data: dict,
                       created_by: int,
                       alias_map: Optional[dict] = None) -> tuple[Connection, list[str], list[str]]:
    """
    Returns (connection, hard_errors, warnings).
    Saves even with warnings; does NOT save if hard_errors present.
    """
    if alias_map is None:
        alias_map = _load_purpose_alias_map(db)
    fields = _conn_from_form(form_data, alias_map)
    conn = Connection(work_order_id=wo_id, created_by=created_by, **fields)

    hard_errors = []
    warnings = []
    _vv = fields.get('vlan_vsan') or ''
    if _vv.isdigit() and len(_vv) > 6:
        warnings.append(
            f"VLAN/VSAN '{_vv}' looks like a collapsed comma-separated list "
            f"(Excel coerced to integer). Verify source data."
        )

    dup = _check_switch_port_duplicate(db, conn)
    if dup:
        hard_errors.append(dup)

    if hard_errors:
        return conn, hard_errors, warnings

    warn = _check_device_port_warning(db, conn)
    if warn:
        warnings.append(warn)

    db.add(conn)
    db.flush()
    write_audit(db, created_by, "medium", "connection", conn.id, "create",
                detail=f"WO {wo_id} — {conn.device_rack_name_raw} {conn.device_port} → {conn.switch_name_raw} {conn.switch_port}")
    db.commit()
    db.refresh(conn)
    # Compute cable lengths immediately after save
    calculate_and_store(db, conn)
    return conn, [], warnings


def update_connection(db: Session, conn: Connection, form_data: dict,
                       updated_by: int) -> tuple[Connection, list[str], list[str]]:
    fields = _conn_from_form(form_data)
    for k, v in fields.items():
        setattr(conn, k, v)
    conn.updated_by = updated_by
    # Editing connection data resets install_status to pending (per spec),
    # but only if the caller isn't explicitly setting a status themselves.
    # If form_data contains install_status, honour it; otherwise reset to pending.
    if "install_status" not in form_data or not form_data.get("install_status"):
        conn.install_status = "pending"

    hard_errors = []
    warnings = []
    _vv = fields.get('vlan_vsan') or ''
    if _vv.isdigit() and len(_vv) > 6:
        warnings.append(
            f"VLAN/VSAN '{_vv}' looks like a collapsed comma-separated list "
            f"(Excel coerced to integer). Verify source data."
        )

    dup = _check_switch_port_duplicate(db, conn, exclude_id=conn.id)
    if dup:
        hard_errors.append(dup)
        return conn, hard_errors, warnings

    warn = _check_device_port_warning(db, conn, exclude_id=conn.id)
    if warn:
        warnings.append(warn)

    write_audit(db, updated_by, "medium", "connection", conn.id, "update",
                detail=f"WO {conn.work_order_id} — {conn.device_rack_name_raw} {conn.device_port} → {conn.switch_name_raw} {conn.switch_port}")
    db.commit()
    db.refresh(conn)
    calculate_and_store(db, conn)
    return conn, [], warnings


def bulk_create_connections(db: Session, wo_id: int, rows: list[dict],
                             created_by: int) -> dict:
    """
    Create multiple connections from parsed CSV/TSV rows.
    Returns {created: N, skipped: [{row, errors}]}.
    """
    alias_map = _load_purpose_alias_map(db)
    created = 0
    skipped = []
    all_warnings = []
    for i, row in enumerate(rows):
        conn, errors, row_warnings = create_connection(db, wo_id, row, created_by, alias_map=alias_map)
        if errors:
            skipped.append({"row": i + 1, "errors": errors})
        else:
            created += 1
            if row_warnings:
                all_warnings.extend([f"Row {i+1}: {w}" for w in row_warnings])
    return {"created": created, "skipped": skipped, "warnings": all_warnings}


def soft_delete_connection(db: Session, conn: Connection, user_id: int) -> None:
    write_audit(db, user_id, "medium", "connection", conn.id, "delete",
                detail=f"WO {conn.work_order_id} conn {conn.id}")
    if get_bool_setting(db, "recycle_bin_enabled", default=True):
        conn.deleted_at = datetime.utcnow()
        conn.deleted_by = user_id
    else:
        db.delete(conn)
    db.commit()


def soft_delete_connections_bulk(db: Session, wo_id: int, conn_ids: list[int], user_id: int) -> int:
    """Bulk soft/hard delete of connection rows within a work order. Returns count deleted."""
    if not conn_ids:
        return 0
    ids_to_delete = [
        c.id for c in db.query(Connection.id).filter(
            Connection.id.in_(conn_ids),
            Connection.work_order_id == wo_id,
            Connection.deleted_at.is_(None),
        ).all()
    ]
    if not ids_to_delete:
        return 0
    write_audit(db, user_id, "medium", "connection", None, "bulk_delete",
                detail=f"WO {wo_id}: {len(ids_to_delete)} row(s) — ids {ids_to_delete}")
    if get_bool_setting(db, "recycle_bin_enabled", default=True):
        db.query(Connection).filter(Connection.id.in_(ids_to_delete)).update(
            {"deleted_at": datetime.utcnow(), "deleted_by": user_id}, synchronize_session=False)
    else:
        db.query(Connection).filter(Connection.id.in_(ids_to_delete)).delete(synchronize_session=False)
    db.commit()
    return len(ids_to_delete)
