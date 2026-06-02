"""
Inventory service — all DB reads/writes for inventory entities.
Raises ValueError for business-rule violations (duplicate names, etc.)
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from app.models.inventory import Datacenter, DCContact, Rack, System, Device, Switch, PatchPanel
from app.services.audit import write_audit
from app.services.settings import get_bool_setting


def _s(v) -> str:
    """Coerce any cell value (int, float, None, str) to a stripped string."""
    return "" if v is None else str(v).strip()


# ── Datacenters ───────────────────────────────────────────────────────────

def list_datacenters(db: Session) -> list[Datacenter]:
    return db.query(Datacenter).order_by(Datacenter.name).all()


def get_datacenter(db: Session, dc_id: int) -> Optional[Datacenter]:
    return db.query(Datacenter).options(
        joinedload(Datacenter.contacts),
        joinedload(Datacenter.racks),
    ).filter(Datacenter.id == dc_id).first()


def get_datacenter_by_code(db: Session, code: str) -> Optional[Datacenter]:
    return db.query(Datacenter).filter(func.lower(Datacenter.code) == code.lower()).first()


def create_datacenter(db: Session, name: str, code: str, address: str = "",
                      has_grid_system: bool = False, notes: str = "",
                      user_id: Optional[int] = None) -> Datacenter:
    if db.query(Datacenter).filter(func.lower(Datacenter.name) == name.lower()).first():
        raise ValueError(f"Datacenter named '{name}' already exists.")
    if db.query(Datacenter).filter(func.lower(Datacenter.code) == code.upper().lower()).first():
        raise ValueError(f"Datacenter code '{code}' is already in use.")
    dc = Datacenter(name=name, code=code.upper(), address=address or None,
                    has_grid_system=has_grid_system, notes=notes or None)
    db.add(dc)
    db.flush()
    write_audit(db, user_id, "wide", "datacenter", dc.id, "create",
                detail=f"{dc.name} ({dc.code})")
    db.commit()
    db.refresh(dc)
    return dc


def update_datacenter(db: Session, dc: Datacenter, user_id: Optional[int] = None,
                      **kwargs) -> Datacenter:
    if "name" in kwargs and kwargs["name"] != dc.name:
        if db.query(Datacenter).filter(
            func.lower(Datacenter.name) == kwargs["name"].lower(),
            Datacenter.id != dc.id
        ).first():
            raise ValueError(f"Datacenter named '{kwargs['name']}' already exists.")
    if "code" in kwargs and kwargs["code"].upper() != dc.code:
        if db.query(Datacenter).filter(
            func.lower(Datacenter.code) == kwargs["code"].lower(),
            Datacenter.id != dc.id
        ).first():
            raise ValueError(f"Datacenter code '{kwargs['code']}' is already in use.")
        kwargs["code"] = kwargs["code"].upper()
    for k, v in kwargs.items():
        setattr(dc, k, v or None if k in ("address", "notes") else v)
    write_audit(db, user_id, "wide", "datacenter", dc.id, "update",
                detail=f"{dc.name} ({dc.code})")
    db.commit()
    db.refresh(dc)
    return dc


def delete_datacenter(db: Session, dc: Datacenter, user_id: Optional[int] = None) -> None:
    if dc.work_orders:
        raise ValueError("Cannot delete datacenter with existing work orders.")
    write_audit(db, user_id, "wide", "datacenter", dc.id, "delete",
                detail=f"{dc.name} ({dc.code})")
    db.delete(dc)
    db.commit()


# ── DC Contacts ───────────────────────────────────────────────────────────

def upsert_contacts(db: Session, dc: Datacenter, contacts_data: list[dict]) -> None:
    """Replace all contacts for a DC with the provided list."""
    db.query(DCContact).filter(DCContact.datacenter_id == dc.id).delete()
    for c in contacts_data:
        if not c.get("name", "").strip():
            continue
        db.add(DCContact(
            datacenter_id=dc.id,
            name=c["name"].strip(),
            role=c.get("role", "").strip() or None,
            email=c.get("email", "").strip() or None,
            phone=c.get("phone", "").strip() or None,
        ))
    db.commit()


# ── Racks ─────────────────────────────────────────────────────────────────

def list_racks(db: Session, dc_id: int) -> list[Rack]:
    return (db.query(Rack)
            .filter(Rack.datacenter_id == dc_id, Rack.deleted_at.is_(None))
            .order_by(Rack.name)
            .all())


def get_rack(db: Session, rack_id: int) -> Optional[Rack]:
    return db.query(Rack).options(
        joinedload(Rack.devices).joinedload(Device.system),
        joinedload(Rack.switches),
        joinedload(Rack.patch_panels),
    ).filter(Rack.id == rack_id, Rack.deleted_at.is_(None)).first()


def create_rack(db: Session, dc_id: int, name: str, grid_position: str = "",
                total_ru: int = 42, notes: str = "",
                user_id: Optional[int] = None) -> Rack:
    if db.query(Rack).filter(Rack.datacenter_id == dc_id,
                              func.lower(Rack.name) == name.lower()).first():
        raise ValueError(f"Rack '{name}' already exists in this datacenter.")
    rack = Rack(datacenter_id=dc_id, name=name,
                grid_position=grid_position or None,
                total_ru=total_ru, notes=notes or None)
    db.add(rack)
    db.flush()
    write_audit(db, user_id, "wide", "rack", rack.id, "create",
                detail=f"{rack.name} dc_id={dc_id}")
    db.commit()
    db.refresh(rack)
    return rack


def update_rack(db: Session, rack: Rack, user_id: Optional[int] = None, **kwargs) -> Rack:
    if "name" in kwargs and kwargs["name"] != rack.name:
        if db.query(Rack).filter(
            Rack.datacenter_id == rack.datacenter_id,
            func.lower(Rack.name) == kwargs["name"].lower(),
            Rack.id != rack.id
        ).first():
            raise ValueError(f"Rack '{kwargs['name']}' already exists in this datacenter.")
    for k, v in kwargs.items():
        setattr(rack, k, v or None if k in ("grid_position", "notes") else v)
    write_audit(db, user_id, "wide", "rack", rack.id, "update",
                detail=f"{rack.name} dc_id={rack.datacenter_id}")
    db.commit()
    db.refresh(rack)
    return rack


def delete_rack(db: Session, rack: Rack, user_id: Optional[int] = None) -> None:
    active_devices = [d for d in rack.devices if d.deleted_at is None]
    active_switches = [s for s in rack.switches if s.deleted_at is None]
    if active_devices or active_switches or rack.patch_panels:
        raise ValueError("Cannot delete rack that contains devices, switches, or patch panels.")
    write_audit(db, user_id, "wide", "rack", rack.id, "delete",
                detail=f"{rack.name} dc_id={rack.datacenter_id}")
    if get_bool_setting(db, "recycle_bin_enabled", default=True):
        rack.deleted_at = datetime.utcnow()
        rack.deleted_by = user_id
    else:
        db.delete(rack)
    db.commit()


# ── Systems ───────────────────────────────────────────────────────────────

def list_systems(db: Session, search: str = "") -> list[System]:
    q = db.query(System)
    if search:
        q = q.filter(System.name.ilike(f"%{search}%"))
    return q.order_by(System.name).all()


def get_system(db: Session, system_id: int) -> Optional[System]:
    return db.query(System).options(
        joinedload(System.devices).joinedload(Device.rack)
    ).filter(System.id == system_id).first()


def create_system(db: Session, name: str, system_type: str = "",
                  notes: str = "", user_id: Optional[int] = None) -> System:
    if db.query(System).filter(func.lower(System.name) == name.lower()).first():
        raise ValueError(f"System named '{name}' already exists.")
    s = System(name=name, system_type=system_type or None, notes=notes or None)
    db.add(s)
    db.flush()
    write_audit(db, user_id, "wide", "system", s.id, "create",
                detail=f"{s.name} type={system_type}")
    db.commit()
    db.refresh(s)
    return s


def update_system(db: Session, system: System, user_id: Optional[int] = None,
                  **kwargs) -> System:
    if "name" in kwargs and kwargs["name"] != system.name:
        if db.query(System).filter(
            func.lower(System.name) == kwargs["name"].lower(),
            System.id != system.id
        ).first():
            raise ValueError(f"System named '{kwargs['name']}' already exists.")
    for k, v in kwargs.items():
        setattr(system, k, v or None if k in ("notes", "system_type") else v)
    write_audit(db, user_id, "wide", "system", system.id, "update",
                detail=f"{system.name}")
    db.commit()
    db.refresh(system)
    return system


def delete_system(db: Session, system: System, user_id: Optional[int] = None) -> None:
    if any(d.system_id == system.id for d in system.devices):
        raise ValueError("Cannot delete system with existing devices. Reassign or delete them first.")
    write_audit(db, user_id, "wide", "system", system.id, "delete",
                detail=f"{system.name}")
    db.delete(system)
    db.commit()


# ── Devices ───────────────────────────────────────────────────────────────

def list_devices(db: Session, rack_id: Optional[int] = None,
                 system_id: Optional[int] = None) -> list[Device]:
    q = db.query(Device).options(joinedload(Device.system), joinedload(Device.rack))
    q = q.filter(Device.deleted_at.is_(None))
    if rack_id:
        q = q.filter(Device.rack_id == rack_id)
    if system_id:
        q = q.filter(Device.system_id == system_id)
    return q.order_by(Device.name).all()


def get_device(db: Session, device_id: int) -> Optional[Device]:
    return db.query(Device).options(
        joinedload(Device.system), joinedload(Device.rack)
    ).filter(Device.id == device_id).first()


def create_device(db: Session, rack_id: int, name: str,
                  system_id: Optional[int] = None,
                  node_label: Optional[str] = None,
                  serial: str = "", starting_ru: Optional[int] = None,
                  device_type_id: Optional[int] = None,
                  parent_device_id: Optional[int] = None,
                  slot_number: Optional[int] = None,
                  notes: str = "", user_id: Optional[int] = None) -> Device:
    d = Device(rack_id=rack_id, name=name, system_id=system_id,
               node_label=node_label or None,
               serial=serial or None, starting_ru=starting_ru,
               device_type_id=device_type_id, parent_device_id=parent_device_id,
               slot_number=slot_number, notes=notes or None)
    db.add(d)
    db.flush()
    write_audit(db, user_id, "wide", "device", d.id, "create",
                detail=f"{d.name} rack_id={rack_id}")
    db.commit()
    db.refresh(d)
    return d


def update_device(db: Session, device: Device, user_id: Optional[int] = None,
                  **kwargs) -> Device:
    for k, v in kwargs.items():
        setattr(device, k, v or None if k in ("serial", "notes", "node_label") else v)
    write_audit(db, user_id, "wide", "device", device.id, "update",
                detail=f"{device.name} rack_id={device.rack_id}")
    db.commit()
    db.refresh(device)
    return device


def delete_device(db: Session, device: Device, user_id: Optional[int] = None) -> None:
    write_audit(db, user_id, "wide", "device", device.id, "delete",
                detail=f"{device.name} rack_id={device.rack_id}")
    if get_bool_setting(db, "recycle_bin_enabled", default=True):
        device.deleted_at = datetime.utcnow()
        device.deleted_by = user_id
    else:
        db.delete(device)
    db.commit()


# ── Switches ──────────────────────────────────────────────────────────────

def list_switches(db: Session, rack_id: Optional[int] = None) -> list[Switch]:
    q = db.query(Switch).options(joinedload(Switch.rack))
    q = q.filter(Switch.deleted_at.is_(None))
    if rack_id:
        q = q.filter(Switch.rack_id == rack_id)
    return q.order_by(Switch.name).all()


def get_switch(db: Session, switch_id: int) -> Optional[Switch]:
    return db.query(Switch).options(joinedload(Switch.rack)).filter(Switch.id == switch_id).first()


def create_switch(db: Session, rack_id: int, name: str, switch_role: str = "LAN",
                  serial: str = "", starting_ru: Optional[int] = None,
                  switch_type_id: Optional[int] = None,
                  notes: str = "", user_id: Optional[int] = None) -> Switch:
    sw = Switch(rack_id=rack_id, name=name, switch_role=switch_role,
                serial=serial or None, starting_ru=starting_ru,
                switch_type_id=switch_type_id, notes=notes or None)
    db.add(sw)
    db.flush()
    write_audit(db, user_id, "wide", "switch", sw.id, "create",
                detail=f"{sw.name} role={switch_role} rack_id={rack_id}")
    db.commit()
    db.refresh(sw)
    return sw


def update_switch(db: Session, switch: Switch, user_id: Optional[int] = None,
                  **kwargs) -> Switch:
    for k, v in kwargs.items():
        setattr(switch, k, v or None if k in ("serial", "notes") else v)
    write_audit(db, user_id, "wide", "switch", switch.id, "update",
                detail=f"{switch.name} rack_id={switch.rack_id}")
    db.commit()
    db.refresh(switch)
    return switch


def delete_switch(db: Session, switch: Switch, user_id: Optional[int] = None) -> None:
    write_audit(db, user_id, "wide", "switch", switch.id, "delete",
                detail=f"{switch.name} rack_id={switch.rack_id}")
    if get_bool_setting(db, "recycle_bin_enabled", default=True):
        switch.deleted_at = datetime.utcnow()
        switch.deleted_by = user_id
    else:
        db.delete(switch)
    db.commit()


# ── Patch Panels ──────────────────────────────────────────────────────────

def list_patch_panels(db: Session, rack_id: int) -> list[PatchPanel]:
    return db.query(PatchPanel).filter(PatchPanel.rack_id == rack_id).order_by(PatchPanel.name).all()


def create_patch_panel(db: Session, rack_id: int, name: str,
                       starting_ru: Optional[int] = None, notes: str = "",
                       user_id: Optional[int] = None) -> PatchPanel:
    pp = PatchPanel(rack_id=rack_id, name=name, starting_ru=starting_ru, notes=notes or None)
    db.add(pp)
    db.flush()
    write_audit(db, user_id, "wide", "patch_panel", pp.id, "create",
                detail=f"{pp.name} rack_id={rack_id}")
    db.commit()
    db.refresh(pp)
    return pp


def update_patch_panel(db: Session, pp: PatchPanel, user_id: Optional[int] = None,
                       **kwargs) -> PatchPanel:
    for k, v in kwargs.items():
        setattr(pp, k, v or None if k == "notes" else v)
    write_audit(db, user_id, "wide", "patch_panel", pp.id, "update",
                detail=f"{pp.name} rack_id={pp.rack_id}")
    db.commit()
    db.refresh(pp)
    return pp


def delete_patch_panel(db: Session, pp: PatchPanel, user_id: Optional[int] = None) -> None:
    write_audit(db, user_id, "wide", "patch_panel", pp.id, "delete",
                detail=f"{pp.name} rack_id={pp.rack_id}")
    db.delete(pp)
    db.commit()


# ── Autocomplete endpoints ────────────────────────────────────────────────

def autocomplete_datacenters(db: Session, q: str, limit: int = 10) -> list[dict]:
    rows = db.query(Datacenter).filter(
        or_(Datacenter.name.ilike(f"%{q}%"), Datacenter.code.ilike(f"%{q}%"))
    ).order_by(Datacenter.name).limit(limit).all()
    return [{"id": r.id, "label": f"{r.name} ({r.code})", "name": r.name, "code": r.code} for r in rows]


def autocomplete_racks(db: Session, q: str, dc_id: Optional[int] = None, limit: int = 10) -> list[dict]:
    query = db.query(Rack).filter(Rack.name.ilike(f"%{q}%"), Rack.deleted_at.is_(None))
    if dc_id:
        query = query.filter(Rack.datacenter_id == dc_id)
    rows = query.order_by(Rack.name).limit(limit).all()
    return [{"id": r.id, "label": r.name, "name": r.name, "dc_id": r.datacenter_id} for r in rows]


def autocomplete_systems(db: Session, q: str, limit: int = 10) -> list[dict]:
    rows = db.query(System).filter(System.name.ilike(f"%{q}%")).order_by(System.name).limit(limit).all()
    return [{"id": r.id, "label": r.name, "name": r.name, "type": r.system_type} for r in rows]


def autocomplete_devices(db: Session, q: str, rack_id: Optional[int] = None, limit: int = 10) -> list[dict]:
    query = db.query(Device).options(joinedload(Device.rack)).filter(
        Device.name.ilike(f"%{q}%"), Device.deleted_at.is_(None))
    if rack_id:
        query = query.filter(Device.rack_id == rack_id)
    rows = query.order_by(Device.name).limit(limit).all()
    return [{"id": r.id, "label": r.name, "name": r.name,
             "serial": r.serial or "", "rack": r.rack.name,
             "rack_u": r.starting_ru,
             "system": r.system.name if r.system else "",
             "node_label": r.node_label or ""} for r in rows]


def autocomplete_switches(db: Session, q: str, role: Optional[str] = None, limit: int = 10) -> list[dict]:
    query = db.query(Switch).options(joinedload(Switch.rack)).filter(
        Switch.name.ilike(f"%{q}%"), Switch.deleted_at.is_(None))
    if role:
        query = query.filter(Switch.switch_role == role)
    rows = query.order_by(Switch.name).limit(limit).all()
    return [{"id": r.id, "label": f"{r.name} ({r.switch_role})", "name": r.name,
             "role": r.switch_role, "serial": r.serial or "",
             "rack": r.rack.name, "rack_u": r.starting_ru} for r in rows]


# ── Device Types ──────────────────────────────────────────────────────────

from app.models.inventory import DeviceType

def list_device_types(db: Session, category: Optional[str] = None) -> list[DeviceType]:
    q = db.query(DeviceType)
    if category:
        q = q.filter(DeviceType.category == category)
    return q.order_by(DeviceType.manufacturer, DeviceType.model).all()


def get_device_type(db: Session, dt_id: int) -> Optional[DeviceType]:
    return db.get(DeviceType, dt_id)


def create_device_type(db: Session, manufacturer: str, model: str,
                        category: str = "server", rack_u: Optional[int] = None,
                        slot_count: Optional[int] = None,
                        port_count: Optional[int] = None,
                        notes: str = "",
                        user_id: Optional[int] = None) -> DeviceType:
    if db.query(DeviceType).filter(
        func.lower(DeviceType.manufacturer) == manufacturer.lower(),
        func.lower(DeviceType.model) == model.lower()
    ).first():
        raise ValueError(f"Device type '{manufacturer} {model}' already exists.")
    dt = DeviceType(manufacturer=manufacturer, model=model, category=category,
                    rack_u=rack_u, slot_count=slot_count, port_count=port_count,
                    notes=notes or None)
    db.add(dt)
    db.flush()
    write_audit(db, user_id, "wide", "device_type", dt.id, "create",
                detail=f"{dt.manufacturer} {dt.model} category={category}")
    db.commit()
    db.refresh(dt)
    return dt


def update_device_type(db: Session, dt: DeviceType, user_id: Optional[int] = None,
                       **kwargs) -> DeviceType:
    if "manufacturer" in kwargs or "model" in kwargs:
        mfg = kwargs.get("manufacturer", dt.manufacturer)
        mdl = kwargs.get("model", dt.model)
        if db.query(DeviceType).filter(
            func.lower(DeviceType.manufacturer) == mfg.lower(),
            func.lower(DeviceType.model) == mdl.lower(),
            DeviceType.id != dt.id
        ).first():
            raise ValueError(f"Device type '{mfg} {mdl}' already exists.")
    for k, v in kwargs.items():
        setattr(dt, k, v or None if k == "notes" else v)
    write_audit(db, user_id, "wide", "device_type", dt.id, "update",
                detail=f"{dt.manufacturer} {dt.model}")
    db.commit()
    db.refresh(dt)
    return dt


def delete_device_type(db: Session, dt: DeviceType, user_id: Optional[int] = None) -> None:
    if dt.devices or dt.switches:
        raise ValueError("Cannot delete device type that is assigned to devices or switches.")
    write_audit(db, user_id, "wide", "device_type", dt.id, "delete",
                detail=f"{dt.manufacturer} {dt.model}")
    db.delete(dt)
    db.commit()


def autocomplete_device_types(db: Session, q: str, category: Optional[str] = None,
                               limit: int = 10) -> list[dict]:
    query = db.query(DeviceType).filter(
        or_(DeviceType.manufacturer.ilike(f"%{q}%"),
            DeviceType.model.ilike(f"%{q}%"))
    )
    if category:
        query = query.filter(DeviceType.category == category)
    rows = query.order_by(DeviceType.manufacturer, DeviceType.model).limit(limit).all()
    return [{"id": r.id, "label": f"{r.manufacturer} {r.model}",
             "manufacturer": r.manufacturer, "model": r.model,
             "category": r.category, "rack_u": r.rack_u,
             "slot_count": r.slot_count} for r in rows]


# ── CSV Bulk Import helpers ───────────────────────────────────────────────

def list_racks_with_stats(
    db: Session,
    datacenter_id: Optional[int] = None,
    max_ru: int = 42,
) -> list[dict]:
    """
    Return one dict per non-deleted rack with aggregated counts and U usage.
    Avoids N+1: counts come from two grouped queries, not per-rack loops.
    Sorted by datacenter_code then rack name.
    """
    from sqlalchemy import case

    # ── Base rack query with datacenter eager-loaded ───────────────────────
    rack_q = (
        db.query(Rack)
        .options(joinedload(Rack.datacenter))
        .filter(Rack.deleted_at.is_(None))
    )
    if datacenter_id:
        rack_q = rack_q.filter(Rack.datacenter_id == datacenter_id)
    racks = rack_q.all()
    if not racks:
        return []

    rack_ids = [r.id for r in racks]

    # ── Device counts & U usage per rack ──────────────────────────────────
    from app.models.inventory import DeviceType
    dev_rows = (
        db.query(
            Device.rack_id,
            func.count(Device.id),
            func.sum(
                case((DeviceType.rack_u.isnot(None), DeviceType.rack_u), else_=1)
            ),
        )
        .outerjoin(DeviceType, Device.device_type_id == DeviceType.id)
        .filter(Device.rack_id.in_(rack_ids), Device.deleted_at.is_(None))
        .group_by(Device.rack_id)
        .all()
    )
    device_count_map: dict[int, int] = {}
    device_u_map: dict[int, int] = {}
    for rack_id, cnt, u_sum in dev_rows:
        device_count_map[rack_id] = cnt
        device_u_map[rack_id] = int(u_sum or 0)

    # ── Switch counts & U usage per rack ──────────────────────────────────
    from app.models.inventory import Switch as _Switch
    sw_rows = (
        db.query(
            _Switch.rack_id,
            func.count(_Switch.id),
            func.sum(
                case((DeviceType.rack_u.isnot(None), DeviceType.rack_u), else_=1)
            ),
        )
        .outerjoin(DeviceType, _Switch.switch_type_id == DeviceType.id)
        .filter(_Switch.rack_id.in_(rack_ids), _Switch.deleted_at.is_(None))
        .group_by(_Switch.rack_id)
        .all()
    )
    switch_count_map: dict[int, int] = {}
    switch_u_map: dict[int, int] = {}
    for rack_id, cnt, u_sum in sw_rows:
        switch_count_map[rack_id] = cnt
        switch_u_map[rack_id] = int(u_sum or 0)

    # ── Assemble results ──────────────────────────────────────────────────
    results = []
    for rack in racks:
        u_occupied = device_u_map.get(rack.id, 0) + switch_u_map.get(rack.id, 0)
        results.append({
            "rack": rack,
            "datacenter_code": rack.datacenter.code,
            "datacenter_name": rack.datacenter.name,
            "device_count": device_count_map.get(rack.id, 0),
            "switch_count": switch_count_map.get(rack.id, 0),
            "u_occupied": u_occupied,
            "max_ru": max_ru,
        })

    results.sort(key=lambda x: (x["datacenter_code"].lower(), x["rack"].name.lower()))
    return results


def get_device_by_name_in_rack(db: Session, rack_id: int, name: str) -> "Optional[Device]":
    return db.query(Device).filter(
        Device.rack_id == rack_id,
        func.lower(Device.name) == name.lower(),
        Device.deleted_at.is_(None),
    ).first()


def get_switch_by_name_in_rack(db: Session, rack_id: int, name: str) -> "Optional[Switch]":
    return db.query(Switch).filter(
        Switch.rack_id == rack_id,
        func.lower(Switch.name) == name.lower(),
        Switch.deleted_at.is_(None),
    ).first()


def get_patch_panel_by_name_in_rack(db: Session, rack_id: int, name: str) -> "Optional[PatchPanel]":
    return db.query(PatchPanel).filter(
        PatchPanel.rack_id == rack_id,
        func.lower(PatchPanel.name) == name.lower(),
    ).first()


def get_rack_by_name(db: Session, dc_id: int, name: str) -> "Optional[Rack]":
    return db.query(Rack).filter(
        Rack.datacenter_id == dc_id,
        func.lower(Rack.name) == name.lower(),
        Rack.deleted_at.is_(None),
    ).first()


def get_system_by_name(db: Session, name: str) -> "Optional[System]":
    return db.query(System).filter(func.lower(System.name) == name.lower()).first()


def get_device_type_by_model(db: Session, model: str) -> "Optional[DeviceType]":
    return db.query(DeviceType).filter(func.lower(DeviceType.model) == model.lower()).first()


def bulk_create_racks(
    db: Session,
    rows: list[dict],
    user_id: Optional[int] = None,
) -> dict:
    """
    Import racks from a list of dicts (parsed from CSV).
    Returns {created: N, skipped: [{row, reason}]}.
    """
    created = 0
    skipped: list[dict] = []

    for i, row in enumerate(rows):
        dc_code  = _s(row.get("datacenter_code", ""))
        name     = _s(row.get("name", ""))
        row_lbl  = _s(row.get("row_label", "")) or None
        rack_num = _s(row.get("rack_number", "")) or None
        notes    = _s(row.get("notes", "")) or None

        if not dc_code or not name:
            skipped.append({"row": i + 1, "reason": "Missing datacenter_code or name"})
            continue

        dc = get_datacenter_by_code(db, dc_code)
        if not dc:
            skipped.append({"row": i + 1, "reason": f"Datacenter '{dc_code}' not found"})
            continue

        if get_rack_by_name(db, dc.id, name):
            skipped.append({"row": i + 1, "reason": f"Rack '{name}' already exists in {dc.code}"})
            continue

        # Compose grid_position from row_label + rack_number if available
        grid_pos = ""
        if row_lbl and rack_num:
            grid_pos = f"{row_lbl}{rack_num}"
        elif row_lbl:
            grid_pos = row_lbl
        elif rack_num:
            grid_pos = rack_num

        try:
            create_rack(db, dc_id=dc.id, name=name, grid_position=grid_pos,
                        notes=notes or "", user_id=user_id)
            created += 1
        except ValueError as exc:
            skipped.append({"row": i + 1, "reason": str(exc)})

    return {"created": created, "skipped": skipped}


def bulk_create_devices(
    db: Session,
    rows: list[dict],
    user_id: Optional[int] = None,
) -> dict:
    """
    Import devices from a list of dicts (parsed from CSV).
    Returns {created: N, skipped: [{row, reason}]}.
    Auto-creates stub systems when system_name is provided but unknown.
    """
    created = 0
    skipped: list[dict] = []

    for i, row in enumerate(rows):
        dc_code     = _s(row.get("datacenter_code", ""))
        rack_name   = _s(row.get("rack_name", ""))
        device_name = _s(row.get("device_name", ""))

        if not dc_code or not rack_name or not device_name:
            skipped.append({"row": i + 1, "reason": "Missing datacenter_code, rack_name, or device_name"})
            continue

        dc = get_datacenter_by_code(db, dc_code)
        if not dc:
            skipped.append({"row": i + 1, "reason": f"Datacenter '{dc_code}' not found"})
            continue

        rack = get_rack_by_name(db, dc.id, rack_name)
        if not rack:
            skipped.append({"row": i + 1, "reason": f"Rack '{rack_name}' not found in {dc.code}"})
            continue

        # Duplicate device check within the rack
        dup = db.query(Device).filter(
            Device.rack_id == rack.id,
            func.lower(Device.name) == device_name.lower(),
            Device.deleted_at.is_(None),
        ).first()
        if dup:
            skipped.append({"row": i + 1, "reason": f"Device '{device_name}' already exists in rack {rack_name}"})
            continue

        # starting_ru — optional integer 1-54
        starting_ru: Optional[int] = None
        ru_raw = _s(row.get("starting_ru", ""))
        if ru_raw:
            try:
                v = int(float(ru_raw))
                if 1 <= v <= 54:
                    starting_ru = v
            except (ValueError, TypeError):
                pass

        # System — look up or auto-create stub
        system_id: Optional[int] = None
        sys_name = _s(row.get("system_name", "")) or None
        if sys_name:
            sys_obj = get_system_by_name(db, sys_name)
            if not sys_obj:
                sys_obj = System(name=sys_name, system_type=None, notes=None)
                db.add(sys_obj)
                db.flush()
                write_audit(db, user_id, "wide", "system", sys_obj.id, "create",
                            detail=f"{sys_obj.name} (auto via device import)")
                db.commit()
                db.refresh(sys_obj)
            system_id = sys_obj.id

        # Device type — look up by model string, leave None if not found
        device_type_id: Optional[int] = None
        dt_model = _s(row.get("device_type_model", "")) or None
        if dt_model:
            dt_obj = get_device_type_by_model(db, dt_model)
            if dt_obj:
                device_type_id = dt_obj.id

        serial     = _s(row.get("serial", "")) or None
        node_label = _s(row.get("node_label", "")) or None
        notes      = _s(row.get("notes", "")) or None

        try:
            create_device(
                db, rack_id=rack.id, name=device_name,
                system_id=system_id, node_label=node_label,
                serial=serial, starting_ru=starting_ru,
                device_type_id=device_type_id,
                notes=notes or "", user_id=user_id,
            )
            created += 1
        except Exception as exc:
            skipped.append({"row": i + 1, "reason": str(exc)})

    return {"created": created, "skipped": skipped}


def hydrate_inventory_from_connections(
    db: Session,
    datacenter_id: int,
    connection_rows: list[dict],
    created_by: int,
) -> dict:
    """
    Given parsed connection rows, create any missing inventory records within
    datacenter_id. Idempotent — never duplicates existing records. Commits once.
    Skips rows where action == "R".
    Returns summary: {racks_created, systems_created, devices_created,
                      switches_created, skipped_existing}.
    """
    def _si(v) -> Optional[int]:
        """Coerce a value to int, None if blank/invalid."""
        s = _s(v)
        if not s:
            return None
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return None

    active_rows = [r for r in connection_rows if _s(r.get("action", "")).upper() != "R"]

    racks_created = 0
    systems_created = 0
    devices_created = 0
    switches_created = 0
    patch_panels_created = 0
    skipped_existing = 0

    # ── In-session caches to avoid repeat DB hits ─────────────────────────
    rack_cache: dict[str, Rack] = {}   # lower(name) → Rack
    system_cache: dict[str, System] = {}  # lower(name) → System

    def _get_or_create_rack(name_raw: str) -> Optional[Rack]:
        nonlocal racks_created, skipped_existing
        name = _s(name_raw)
        if not name:
            return None
        key = name.lower()
        if key in rack_cache:
            return rack_cache[key]
        existing = get_rack_by_name(db, datacenter_id, name)
        if existing:
            rack_cache[key] = existing
            skipped_existing += 1
            return existing
        rack = Rack(datacenter_id=datacenter_id, name=name)
        db.add(rack)
        db.flush()
        write_audit(db, created_by, "wide", "rack", rack.id, "create",
                    detail=f"{rack.name} dc_id={datacenter_id} (hydrated)")
        rack_cache[key] = rack
        racks_created += 1
        return rack

    def _get_or_create_system(name_raw: str) -> Optional[System]:
        nonlocal systems_created, skipped_existing
        name = _s(name_raw)
        if not name:
            return None
        key = name.lower()
        if key in system_cache:
            return system_cache[key]
        existing = get_system_by_name(db, name)
        if existing:
            system_cache[key] = existing
            skipped_existing += 1
            return existing
        system = System(name=name)
        db.add(system)
        db.flush()
        write_audit(db, created_by, "wide", "system", system.id, "create",
                    detail=f"{system.name} (hydrated)")
        system_cache[key] = system
        systems_created += 1
        return system

    # ── Pass 1: racks ─────────────────────────────────────────────────────
    for row in active_rows:
        for field in ("device_rack_name_raw", "switch_rack_name_raw",
                      "device_patch_rack_name_raw", "switch_patch_rack_name_raw"):
            _get_or_create_rack(_s(row.get(field, "")))

    # ── Pass 2: systems ───────────────────────────────────────────────────
    for row in active_rows:
        _get_or_create_system(_s(row.get("system_name_raw", "")))

    # ── Pass 3: devices ───────────────────────────────────────────────────
    seen_devices: set[tuple] = set()
    for row in active_rows:
        dev_name = _s(row.get("device_name_raw", ""))
        rack_name = _s(row.get("device_rack_name_raw", ""))
        if not dev_name or not rack_name:
            skipped_existing += 1
            continue
        rack = rack_cache.get(rack_name.lower())
        if not rack:
            skipped_existing += 1
            continue
        key = (rack.id, dev_name.lower())
        if key in seen_devices:
            continue
        seen_devices.add(key)
        if get_device_by_name_in_rack(db, rack.id, dev_name):
            skipped_existing += 1
            continue
        system = _get_or_create_system(_s(row.get("system_name_raw", "")))
        device = Device(
            rack_id=rack.id,
            name=dev_name,
            system_id=system.id if system else None,
            serial=_s(row.get("device_serial", "")) or None,
            starting_ru=_si(row.get("device_rack_u")),
        )
        db.add(device)
        db.flush()
        write_audit(db, created_by, "wide", "device", device.id, "create",
                    detail=f"{device.name} rack_id={rack.id} (hydrated)")
        devices_created += 1

    # ── Pass 4: switches ──────────────────────────────────────────────────
    seen_switches: set[tuple] = set()
    switch_role_map: dict[tuple, str] = {}  # (rack_id, lower_name) → role (first-wins)
    for row in active_rows:
        sw_name = _s(row.get("switch_name_raw", ""))
        rack_name = _s(row.get("switch_rack_name_raw", ""))
        if not sw_name or not rack_name:
            continue
        rack = rack_cache.get(rack_name.lower())
        if not rack:
            continue
        key = (rack.id, sw_name.lower())
        if key not in switch_role_map:
            purpose = _s(row.get("purpose", "")).lower()
            switch_role_map[key] = "SAN" if purpose == "storage" else "LAN"

    for row in active_rows:
        sw_name = _s(row.get("switch_name_raw", ""))
        rack_name = _s(row.get("switch_rack_name_raw", ""))
        if not sw_name or not rack_name:
            skipped_existing += 1
            continue
        rack = rack_cache.get(rack_name.lower())
        if not rack:
            skipped_existing += 1
            continue
        key = (rack.id, sw_name.lower())
        if key in seen_switches:
            continue
        seen_switches.add(key)
        if get_switch_by_name_in_rack(db, rack.id, sw_name):
            skipped_existing += 1
            continue
        role = switch_role_map.get(key, "LAN")
        switch = Switch(
            rack_id=rack.id,
            name=sw_name,
            switch_role=role,
            serial=_s(row.get("switch_serial", "")) or None,
            starting_ru=_si(row.get("switch_rack_u")),
        )
        db.add(switch)
        db.flush()
        write_audit(db, created_by, "wide", "switch", switch.id, "create",
                    detail=f"{switch.name} role={role} rack_id={rack.id} (hydrated)")
        switches_created += 1

    # ── Pass 5: patch panels ──────────────────────────────────────────────
    # Each connection row may reference a device-side patch panel rack + module
    # and a switch-side patch panel rack + module. We create one PatchPanel stub
    # per unique (rack, module) pair. Module is used as the panel name since a
    # rack may hold multiple numbered modules. Rows with no module are skipped.
    seen_panels: set[tuple] = set()

    def _get_or_create_panel(rack_name_raw: str, module_raw: str) -> None:
        nonlocal patch_panels_created, skipped_existing
        rack_name = _s(rack_name_raw)
        module = _s(module_raw)
        if not rack_name or not module:
            return
        rack = rack_cache.get(rack_name.lower())
        if not rack:
            return
        key = (rack.id, module.lower())
        if key in seen_panels:
            return
        seen_panels.add(key)
        if get_patch_panel_by_name_in_rack(db, rack.id, module):
            skipped_existing += 1
            return
        panel = PatchPanel(rack_id=rack.id, name=module)
        db.add(panel)
        db.flush()
        write_audit(db, created_by, "wide", "patch_panel", panel.id, "create",
                    detail=f"{panel.name} rack_id={rack.id} (hydrated)")
        patch_panels_created += 1

    for row in active_rows:
        _get_or_create_panel(
            _s(row.get("device_patch_rack_name_raw", "")),
            _s(row.get("device_patch_module", "")),
        )
        _get_or_create_panel(
            _s(row.get("switch_patch_rack_name_raw", "")),
            _s(row.get("switch_patch_module", "")),
        )

    db.commit()

    return {
        "racks_created": racks_created,
        "systems_created": systems_created,
        "devices_created": devices_created,
        "switches_created": switches_created,
        "patch_panels_created": patch_panels_created,
        "skipped_existing": skipped_existing,
    }


# ── Rack elevation ────────────────────────────────────────────────────────

def get_rack_elevation(db: Session, rack_id: int, max_ru: int = 42) -> list[dict]:
    """
    Build a slot-per-U elevation list for a rack.
    Returns one dict per U (1..max_ru), with device info + connection stats.
    Continuation rows (U slots 2-N of a multi-U device) set is_continuation=True.
    """
    from app.models.connection import Connection
    from app.models.work_order import WorkOrder

    # Load rack with devices, their types, and their systems
    rack = (
        db.query(Rack)
        .options(
            joinedload(Rack.devices)
            .joinedload(Device.device_type),
            joinedload(Rack.devices)
            .joinedload(Device.system),
        )
        .filter(Rack.id == rack_id, Rack.deleted_at.is_(None))
        .first()
    )
    if not rack:
        return []

    active_devices = [d for d in rack.devices if d.deleted_at is None]

    # ── Connection stats in one query ──────────────────────────────────────
    # Only count connections that reference an inventory device (device_id set)
    conn_rows = (
        db.query(
            Connection.device_id,
            Connection.fabric,
            Connection.work_order_id,
            WorkOrder.status,
        )
        .join(WorkOrder, Connection.work_order_id == WorkOrder.id)
        .filter(
            Connection.device_rack_id == rack_id,
            Connection.deleted_at.is_(None),
            Connection.device_id.isnot(None),
        )
        .all()
    )

    # Build per-device stats dict
    device_stats: dict[int, dict] = {}
    for d_id, fabric, wo_id, wo_status in conn_rows:
        if d_id not in device_stats:
            device_stats[d_id] = {"fabric_a": 0, "fabric_b": 0, "active_wo_ids": set()}
        if fabric == "A":
            device_stats[d_id]["fabric_a"] += 1
        elif fabric == "B":
            device_stats[d_id]["fabric_b"] += 1
        if wo_status in ("issued", "in_progress"):
            device_stats[d_id]["active_wo_ids"].add(wo_id)

    # ── Pre-compute device heights ────────────────────────────────────────
    device_heights: dict[int, int] = {}
    for device in active_devices:
        h = 1
        if device.device_type and device.device_type.rack_u:
            h = device.device_type.rack_u
        device_heights[device.id] = h

    # ── Build U → (device, offset) occupancy map ──────────────────────────
    u_map: dict[int, tuple] = {}  # u → (device, offset_within_device)
    for device in active_devices:
        if device.starting_ru is None:
            continue
        height = device_heights[device.id]
        for offset in range(height):
            u = device.starting_ru + offset
            if 1 <= u <= max_ru:
                u_map[u] = (device, offset)

    # ── Assemble slot list (ascending), then reverse for top-down display ─
    # DC convention: highest RU is at the top of the cabinet.
    # For a multi-U device, the label row is its highest occupied U
    # (offset == height-1), with rowspan extending downward visually.
    slots: list[dict] = []
    for u in range(1, max_ru + 1):
        if u not in u_map:
            slots.append({
                "u": u,
                "device": None,
                "span": 1,
                "is_continuation": False,
                "system_label": None,
                "type_label": None,
                "fabric_a_ports": 0,
                "fabric_b_ports": 0,
                "active_wo_count": 0,
            })
            continue

        device, offset = u_map[u]
        height = device_heights[device.id]
        # Visual top = highest U of the device's span (last in ascending order)
        is_visual_top = (offset == height - 1)

        if not is_visual_top:
            slots.append({
                "u": u,
                "device": device,
                "span": None,
                "is_continuation": True,
                "system_label": None,
                "type_label": None,
                "fabric_a_ports": 0,
                "fabric_b_ports": 0,
                "active_wo_count": 0,
            })
            continue

        # Label row (visual top of this device)
        system_label: Optional[str] = None
        if device.system:
            system_label = (
                f"{device.system.name} / {device.node_label}"
                if device.node_label
                else device.system.name
            )

        type_label: Optional[str] = None
        if device.device_type:
            type_label = f"{device.device_type.manufacturer} {device.device_type.model}"

        stats = device_stats.get(device.id, {})
        slots.append({
            "u": u,
            "device": device,
            "span": height,
            "is_continuation": False,
            "system_label": system_label,
            "type_label": type_label,
            "fabric_a_ports": stats.get("fabric_a", 0),
            "fabric_b_ports": stats.get("fabric_b", 0),
            "active_wo_count": len(stats.get("active_wo_ids", set())),
        })

    # Reverse: highest RU first (top of cabinet = top of table)
    return slots[::-1]
