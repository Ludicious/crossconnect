"""
Work order and connection service.
All business rules enforced here; routers only handle HTTP concerns.
"""
from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_

from app.models.work_order import WorkOrder, VALID_STATUSES, VALID_WORK_TYPES
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
    )
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
    ).filter(WorkOrder.id == wo_id).first()


def create_work_order(db: Session, name: str, datacenter_id: int,
                      work_type: str, created_by: int,
                      target_date: Optional[date] = None,
                      notes: str = "") -> WorkOrder:
    if work_type not in VALID_WORK_TYPES:
        raise ValueError(f"Invalid work type: {work_type}")
    wo = WorkOrder(
        name=name, datacenter_id=datacenter_id, work_type=work_type,
        created_by=created_by, target_date=target_date,
        notes=notes or None, status="draft",
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def update_work_order(db: Session, wo: WorkOrder, **kwargs) -> WorkOrder:
    if "work_type" in kwargs and kwargs["work_type"] not in VALID_WORK_TYPES:
        raise ValueError(f"Invalid work type: {kwargs['work_type']}")
    for k, v in kwargs.items():
        setattr(wo, k, v or None if k == "notes" else v)
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
            raise ValueError(f"{len(errors)} connection row(s) have validation errors. Fix them before issuing.")

    # On complete: soft-delete all R-action connections
    if new_status == "complete":
        now = datetime.utcnow()
        db.query(Connection).filter(
            Connection.work_order_id == wo.id,
            Connection.action == "R",
            Connection.deleted_at.is_(None),
        ).update({"deleted_at": now, "deleted_by": user.id})

    wo.status = new_status
    db.commit()
    db.refresh(wo)
    return wo


def delete_work_order(db: Session, wo: WorkOrder) -> None:
    if wo.status not in ("draft", "cancelled"):
        raise ValueError("Only draft or cancelled work orders can be deleted.")
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
    """Hard block: same switch+slot+port in any non-deleted non-R row."""
    if not all([conn.switch_id, conn.switch_slot, conn.switch_port]):
        return None
    if conn.action == "R":
        return None
    q = db.query(Connection).filter(
        Connection.switch_id == conn.switch_id,
        Connection.switch_slot == conn.switch_slot,
        Connection.switch_port == conn.switch_port,
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


def _conn_from_form(data: dict) -> dict:
    """Coerce form dict to connection field dict."""
    def _int(v):
        try: return int(v) if v else None
        except (ValueError, TypeError): return None

    return dict(
        action=data.get("action", "").strip().upper(),
        fabric=data.get("fabric", "").strip().upper() or None,
        port_description=data.get("port_description", "").strip() or None,
        cable_type=data.get("cable_type", "").strip(),
        purpose=data.get("purpose", "").strip(),
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
        vlan_vsan=data.get("vlan_vsan", "").strip() or None,
        comments=data.get("comments", "").strip() or None,
        install_status=data.get("install_status", "pending"),
    )


def create_connection(db: Session, wo_id: int, form_data: dict,
                       created_by: int) -> tuple[Connection, list[str], list[str]]:
    """
    Returns (connection, hard_errors, warnings).
    Saves even with warnings; does NOT save if hard_errors present.
    """
    fields = _conn_from_form(form_data)
    conn = Connection(work_order_id=wo_id, created_by=created_by, **fields)

    hard_errors = []
    warnings = []

    dup = _check_switch_port_duplicate(db, conn)
    if dup:
        hard_errors.append(dup)

    if hard_errors:
        return conn, hard_errors, warnings

    warn = _check_device_port_warning(db, conn)
    if warn:
        warnings.append(warn)

    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn, [], warnings


def update_connection(db: Session, conn: Connection, form_data: dict,
                       updated_by: int) -> tuple[Connection, list[str], list[str]]:
    fields = _conn_from_form(form_data)
    for k, v in fields.items():
        setattr(conn, k, v)
    conn.updated_by = updated_by
    # Editing a row resets install_status to pending (per spec)
    conn.install_status = "pending"

    hard_errors = []
    warnings = []

    dup = _check_switch_port_duplicate(db, conn, exclude_id=conn.id)
    if dup:
        hard_errors.append(dup)
        return conn, hard_errors, warnings

    warn = _check_device_port_warning(db, conn, exclude_id=conn.id)
    if warn:
        warnings.append(warn)

    db.commit()
    db.refresh(conn)
    return conn, [], warnings


def bulk_create_connections(db: Session, wo_id: int, rows: list[dict],
                             created_by: int) -> dict:
    """
    Create multiple connections from parsed CSV/TSV rows.
    Returns {created: N, skipped: [{row, errors}]}.
    """
    created = 0
    skipped = []
    for i, row in enumerate(rows):
        conn, errors, _ = create_connection(db, wo_id, row, created_by)
        if errors:
            skipped.append({"row": i + 1, "errors": errors})
        else:
            created += 1
    return {"created": created, "skipped": skipped}


def soft_delete_connection(db: Session, conn: Connection, user_id: int) -> None:
    conn.deleted_at = datetime.utcnow()
    conn.deleted_by = user_id
    db.commit()
