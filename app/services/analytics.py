"""
Analytics service — rack elevation, port adjacency, port utilization.
All functions are read-only; no DB writes.
"""
from collections import defaultdict
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.inventory import Rack, Device, Switch, PatchPanel, DeviceType, Datacenter
from app.models.connection import Connection
from app.models.work_order import WorkOrder
from app.models.settings import AppSetting


# ── Rack elevation ────────────────────────────────────────────────────────────

def get_rack_elevation(db: Session, rack_id: int) -> Optional[dict]:
    """
    Returns everything needed to render a rack elevation diagram, or None if
    the rack does not exist.

    Slots are listed top-down (highest RU first = top of rack). Multi-U items
    have a main entry at their top RU and "continuation" entries for lower RUs.
    Unpositioned items (no starting_ru) are appended after the grid slots.
    """
    rack = db.query(Rack).options(
        joinedload(Rack.devices).joinedload(Device.device_type),
        joinedload(Rack.switches).joinedload(Switch.device_type),
        joinedload(Rack.patch_panels),
        joinedload(Rack.datacenter),
    ).filter(Rack.id == rack_id).first()

    if not rack:
        return None

    total_ru = rack.total_ru or 42

    # Connection counts per device_id / switch_id (non-deleted only)
    dev_counts_rows = db.query(Connection.device_id, func.count(Connection.id)).filter(
        Connection.deleted_at.is_(None),
        Connection.device_id.isnot(None),
    ).group_by(Connection.device_id).all()
    device_conn_counts = {row[0]: row[1] for row in dev_counts_rows}

    sw_counts_rows = db.query(Connection.switch_id, func.count(Connection.id)).filter(
        Connection.deleted_at.is_(None),
        Connection.switch_id.isnot(None),
    ).group_by(Connection.switch_id).all()
    switch_conn_counts = {row[0]: row[1] for row in sw_counts_rows}

    # Initialize grid with empty slots (1-indexed)
    def _empty(ru: int) -> dict:
        return {"ru": ru, "type": "empty", "id": None, "name": None,
                "height_u": 1, "starting_ru": None, "category": None,
                "role": None, "serial": None, "connection_count": 0,
                "device_type": None}

    grid = {ru: _empty(ru) for ru in range(1, total_ru + 1)}
    unpositioned: list[dict] = []

    def _place(item_dict: dict, starting_ru: Optional[int], height: int) -> None:
        if not starting_ru or starting_ru < 1:
            unpositioned.append(item_dict)
            return
        top_ru = min(starting_ru + height - 1, total_ru)
        item_dict["ru"] = top_ru
        grid[top_ru] = item_dict
        for cont_ru in range(starting_ru, top_ru):
            grid[cont_ru] = {
                "ru": cont_ru, "type": "continuation",
                "id": item_dict["id"], "name": item_dict["name"],
                "height_u": 1, "starting_ru": starting_ru,
                "category": None, "role": None, "serial": None,
                "connection_count": 0, "device_type": None,
            }

    for d in rack.devices:
        height = (d.device_type.rack_u if d.device_type and d.device_type.rack_u else 1)
        dt_str = (f"{d.device_type.manufacturer} {d.device_type.model}"
                  if d.device_type else None)
        _place({
            "ru": None, "type": "device", "id": d.id, "name": d.name,
            "height_u": height, "starting_ru": d.starting_ru,
            "category": d.device_type.category if d.device_type else "server",
            "role": None, "serial": d.serial,
            "connection_count": device_conn_counts.get(d.id, 0),
            "device_type": dt_str,
        }, d.starting_ru, height)

    for sw in rack.switches:
        height = (sw.device_type.rack_u if sw.device_type and sw.device_type.rack_u else 1)
        dt_str = (f"{sw.device_type.manufacturer} {sw.device_type.model}"
                  if sw.device_type else None)
        _place({
            "ru": None, "type": "switch", "id": sw.id, "name": sw.name,
            "height_u": height, "starting_ru": sw.starting_ru,
            "category": "switch", "role": sw.switch_role, "serial": sw.serial,
            "connection_count": switch_conn_counts.get(sw.id, 0),
            "device_type": dt_str,
        }, sw.starting_ru, height)

    for pp in rack.patch_panels:
        _place({
            "ru": pp.starting_ru, "type": "patch_panel", "id": pp.id,
            "name": pp.name, "height_u": 1, "starting_ru": pp.starting_ru,
            "category": None, "role": None, "serial": None,
            "connection_count": 0, "device_type": None,
        }, pp.starting_ru, 1)

    # Slots list: top-down, then unpositioned
    slots = [grid[ru] for ru in range(total_ru, 0, -1)] + unpositioned

    # Summary
    used_ru = sum(
        1 for ru in range(1, total_ru + 1)
        if grid[ru]["type"] != "empty"
    )

    return {
        "rack": {
            "id": rack.id,
            "name": rack.name,
            "total_ru": total_ru,
            "grid_position": rack.grid_position,
        },
        "slots": slots,
        "unpositioned": unpositioned,
        "summary": {
            "total_ru": total_ru,
            "used_ru": used_ru,
            "free_ru": total_ru - used_ru,
            "device_count": len(rack.devices),
            "switch_count": len(rack.switches),
            "patch_panel_count": len(rack.patch_panels),
        },
    }


# ── Port adjacency analysis ───────────────────────────────────────────────────

def get_port_adjacency_warnings(
    db: Session,
    wo_id: Optional[int] = None,
    dc_id: Optional[int] = None,
) -> list[dict]:
    """
    Find devices with multiple connections to the same switch where the switch
    ports are purely numeric and within the adjacency threshold of each other.

    Threshold is read from app_settings key "port_adjacency_threshold"
    (default 4). Severity: "adjacent" if separation ≤ 1, else "close".
    """
    setting = db.get(AppSetting, "port_adjacency_threshold")
    try:
        threshold = int(setting.value) if setting else 4
    except (ValueError, AttributeError):
        threshold = 4

    q = db.query(Connection).filter(
        Connection.deleted_at.is_(None),
        Connection.action != "R",
    )
    if wo_id:
        q = q.filter(Connection.work_order_id == wo_id)
    if dc_id:
        wo_subq = db.query(WorkOrder.id).filter(
            WorkOrder.datacenter_id == dc_id
        ).subquery()
        q = q.filter(Connection.work_order_id.in_(wo_subq))

    connections = q.all()

    # Group by (device_key, switch_key)
    groups: dict = defaultdict(list)
    for c in connections:
        device_key = c.device_id or f"n:{(c.device_name_raw or '').lower().strip()}"
        switch_key = c.switch_id or f"n:{(c.switch_name_raw or '').lower().strip()}"
        # Skip rows where both sides are unidentifiable
        if device_key in (None, "n:") or switch_key in (None, "n:"):
            continue
        groups[(device_key, switch_key)].append(c)

    # Preload work order names
    all_wo_ids = {c.work_order_id for conns in groups.values() for c in conns}
    wo_names = {}
    if all_wo_ids:
        for wo in db.query(WorkOrder).filter(WorkOrder.id.in_(all_wo_ids)).all():
            wo_names[wo.id] = wo.name

    warnings = []
    for (device_key, switch_key), conns in groups.items():
        if len(conns) < 2:
            continue

        # Only process groups where switch_port is purely numeric
        numeric: list[tuple[int, Connection]] = []
        for c in conns:
            try:
                port_num = int(str(c.switch_port).strip())
                numeric.append((port_num, c))
            except (ValueError, TypeError, AttributeError):
                pass

        if len(numeric) < 2:
            continue

        ports_sorted = sorted(numeric, key=lambda x: x[0])
        min_sep = min(
            ports_sorted[i + 1][0] - ports_sorted[i][0]
            for i in range(len(ports_sorted) - 1)
        )

        if min_sep > threshold:
            continue

        sample = conns[0]
        severity = "adjacent" if min_sep <= 1 else "close"

        warnings.append({
            "device_name": sample.device_name_raw or str(device_key),
            "device_id": sample.device_id,
            "switch_name": sample.switch_name_raw or str(switch_key),
            "switch_id": sample.switch_id,
            "ports": [
                {
                    "connection_id": c.id,
                    "switch_slot": c.switch_slot,
                    "switch_port": c.switch_port,
                    "work_order_name": wo_names.get(c.work_order_id,
                                                    f"WO-{c.work_order_id}"),
                }
                for _, c in ports_sorted
            ],
            "min_separation": min_sep,
            "severity": severity,
        })

    _sev_order = {"adjacent": 0, "close": 1}
    warnings.sort(key=lambda w: (_sev_order.get(w["severity"], 9), w["device_name"]))
    return warnings


# ── Port utilization ──────────────────────────────────────────────────────────

def get_port_utilization(db: Session, dc_id: Optional[int] = None) -> list[dict]:
    """
    For each switch (optionally filtered by DC), return port usage based on
    documented non-deleted non-R connections.
    """
    q = db.query(Switch).join(Rack, Switch.rack_id == Rack.id).options(
        joinedload(Switch.device_type),
        joinedload(Switch.rack).joinedload(Rack.datacenter),
    )
    if dc_id:
        q = q.filter(Rack.datacenter_id == dc_id)
    switches = q.all()

    # Connection counts per switch_id (non-deleted, non-R)
    counts_rows = db.query(Connection.switch_id, func.count(Connection.id)).filter(
        Connection.deleted_at.is_(None),
        Connection.action != "R",
        Connection.switch_id.isnot(None),
    ).group_by(Connection.switch_id).all()
    sw_used = {row[0]: row[1] for row in counts_rows}

    result = []
    for sw in switches:
        port_count = sw.device_type.port_count if sw.device_type else None
        used = sw_used.get(sw.id, 0)
        free = (port_count - used) if port_count is not None else None
        pct = (used / port_count * 100) if port_count else None
        result.append({
            "switch_id": sw.id,
            "switch_name": sw.name,
            "rack_name": sw.rack.name if sw.rack else "—",
            "dc_name": (sw.rack.datacenter.name
                        if sw.rack and sw.rack.datacenter else "—"),
            "role": sw.switch_role,
            "port_count": port_count,
            "documented_used": used,
            "documented_free": free,
            "utilization_pct": round(pct, 1) if pct is not None else None,
            "has_type": sw.device_type is not None,
        })

    # Order: dc_name asc, then unknowns last, then utilization_pct desc
    result.sort(key=lambda x: (
        x["dc_name"],
        x["utilization_pct"] is None,
        -(x["utilization_pct"] or 0),
    ))
    return result
