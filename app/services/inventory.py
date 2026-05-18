"""
Inventory service — all DB reads/writes for inventory entities.
Raises ValueError for business-rule violations (duplicate names, etc.)
"""
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from app.models.inventory import Datacenter, DCContact, Rack, System, Device, Switch, PatchPanel
from app.services.audit import write_audit


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
            .filter(Rack.datacenter_id == dc_id)
            .order_by(Rack.name)
            .all())


def get_rack(db: Session, rack_id: int) -> Optional[Rack]:
    return db.query(Rack).options(
        joinedload(Rack.devices).joinedload(Device.system),
        joinedload(Rack.switches),
        joinedload(Rack.patch_panels),
    ).filter(Rack.id == rack_id).first()


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
    if rack.devices or rack.switches or rack.patch_panels:
        raise ValueError("Cannot delete rack that contains devices, switches, or patch panels.")
    write_audit(db, user_id, "wide", "rack", rack.id, "delete",
                detail=f"{rack.name} dc_id={rack.datacenter_id}")
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


def create_system(db: Session, name: str, system_type: str = "server",
                  notes: str = "", user_id: Optional[int] = None) -> System:
    if db.query(System).filter(func.lower(System.name) == name.lower()).first():
        raise ValueError(f"System named '{name}' already exists.")
    s = System(name=name, system_type=system_type, notes=notes or None)
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
        setattr(system, k, v or None if k == "notes" else v)
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
                  serial: str = "", starting_ru: Optional[int] = None,
                  device_type_id: Optional[int] = None,
                  parent_device_id: Optional[int] = None,
                  slot_number: Optional[int] = None,
                  notes: str = "", user_id: Optional[int] = None) -> Device:
    d = Device(rack_id=rack_id, name=name, system_id=system_id,
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
        setattr(device, k, v or None if k in ("serial", "notes") else v)
    write_audit(db, user_id, "wide", "device", device.id, "update",
                detail=f"{device.name} rack_id={device.rack_id}")
    db.commit()
    db.refresh(device)
    return device


def delete_device(db: Session, device: Device, user_id: Optional[int] = None) -> None:
    write_audit(db, user_id, "wide", "device", device.id, "delete",
                detail=f"{device.name} rack_id={device.rack_id}")
    db.delete(device)
    db.commit()


# ── Switches ──────────────────────────────────────────────────────────────

def list_switches(db: Session, rack_id: Optional[int] = None) -> list[Switch]:
    q = db.query(Switch).options(joinedload(Switch.rack))
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
    query = db.query(Rack).filter(Rack.name.ilike(f"%{q}%"))
    if dc_id:
        query = query.filter(Rack.datacenter_id == dc_id)
    rows = query.order_by(Rack.name).limit(limit).all()
    return [{"id": r.id, "label": r.name, "name": r.name, "dc_id": r.datacenter_id} for r in rows]


def autocomplete_systems(db: Session, q: str, limit: int = 10) -> list[dict]:
    rows = db.query(System).filter(System.name.ilike(f"%{q}%")).order_by(System.name).limit(limit).all()
    return [{"id": r.id, "label": r.name, "name": r.name, "type": r.system_type} for r in rows]


def autocomplete_devices(db: Session, q: str, rack_id: Optional[int] = None, limit: int = 10) -> list[dict]:
    query = db.query(Device).options(joinedload(Device.rack)).filter(Device.name.ilike(f"%{q}%"))
    if rack_id:
        query = query.filter(Device.rack_id == rack_id)
    rows = query.order_by(Device.name).limit(limit).all()
    return [{"id": r.id, "label": r.name, "name": r.name,
             "serial": r.serial or "", "rack": r.rack.name,
             "rack_u": r.starting_ru,
             "system": r.system.name if r.system else ""} for r in rows]


def autocomplete_switches(db: Session, q: str, role: Optional[str] = None, limit: int = 10) -> list[dict]:
    query = db.query(Switch).options(joinedload(Switch.rack)).filter(Switch.name.ilike(f"%{q}%"))
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
                        slot_count: Optional[int] = None, notes: str = "",
                        user_id: Optional[int] = None) -> DeviceType:
    if db.query(DeviceType).filter(
        func.lower(DeviceType.manufacturer) == manufacturer.lower(),
        func.lower(DeviceType.model) == model.lower()
    ).first():
        raise ValueError(f"Device type '{manufacturer} {model}' already exists.")
    dt = DeviceType(manufacturer=manufacturer, model=model, category=category,
                    rack_u=rack_u, slot_count=slot_count, notes=notes or None)
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
