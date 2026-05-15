"""
Inventory service — all DB reads/writes for inventory entities.
Raises ValueError for business-rule violations (duplicate names, etc.)
"""
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from app.models.inventory import Datacenter, DCContact, Rack, System, Device, Switch, PatchPanel


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
                      has_grid_system: bool = False, notes: str = "") -> Datacenter:
    if db.query(Datacenter).filter(func.lower(Datacenter.name) == name.lower()).first():
        raise ValueError(f"Datacenter named '{name}' already exists.")
    if db.query(Datacenter).filter(func.lower(Datacenter.code) == code.upper().lower()).first():
        raise ValueError(f"Datacenter code '{code}' is already in use.")
    dc = Datacenter(name=name, code=code.upper(), address=address or None,
                    has_grid_system=has_grid_system, notes=notes or None)
    db.add(dc)
    db.commit()
    db.refresh(dc)
    return dc


def update_datacenter(db: Session, dc: Datacenter, **kwargs) -> Datacenter:
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
    db.commit()
    db.refresh(dc)
    return dc


def delete_datacenter(db: Session, dc: Datacenter) -> None:
    if dc.work_orders:
        raise ValueError("Cannot delete datacenter with existing work orders.")
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
                total_ru: int = 42, notes: str = "") -> Rack:
    if db.query(Rack).filter(Rack.datacenter_id == dc_id,
                              func.lower(Rack.name) == name.lower()).first():
        raise ValueError(f"Rack '{name}' already exists in this datacenter.")
    rack = Rack(datacenter_id=dc_id, name=name,
                grid_position=grid_position or None,
                total_ru=total_ru, notes=notes or None)
    db.add(rack)
    db.commit()
    db.refresh(rack)
    return rack


def update_rack(db: Session, rack: Rack, **kwargs) -> Rack:
    if "name" in kwargs and kwargs["name"] != rack.name:
        if db.query(Rack).filter(
            Rack.datacenter_id == rack.datacenter_id,
            func.lower(Rack.name) == kwargs["name"].lower(),
            Rack.id != rack.id
        ).first():
            raise ValueError(f"Rack '{kwargs['name']}' already exists in this datacenter.")
    for k, v in kwargs.items():
        setattr(rack, k, v or None if k in ("grid_position", "notes") else v)
    db.commit()
    db.refresh(rack)
    return rack


def delete_rack(db: Session, rack: Rack) -> None:
    if rack.devices or rack.switches or rack.patch_panels:
        raise ValueError("Cannot delete rack that contains devices, switches, or patch panels.")
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
                  notes: str = "") -> System:
    if db.query(System).filter(func.lower(System.name) == name.lower()).first():
        raise ValueError(f"System named '{name}' already exists.")
    s = System(name=name, system_type=system_type, notes=notes or None)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def update_system(db: Session, system: System, **kwargs) -> System:
    if "name" in kwargs and kwargs["name"] != system.name:
        if db.query(System).filter(
            func.lower(System.name) == kwargs["name"].lower(),
            System.id != system.id
        ).first():
            raise ValueError(f"System named '{kwargs['name']}' already exists.")
    for k, v in kwargs.items():
        setattr(system, k, v or None if k == "notes" else v)
    db.commit()
    db.refresh(system)
    return system


def delete_system(db: Session, system: System) -> None:
    if any(d.system_id == system.id for d in system.devices):
        raise ValueError("Cannot delete system with existing devices. Reassign or delete them first.")
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
                  notes: str = "") -> Device:
    d = Device(rack_id=rack_id, name=name, system_id=system_id,
               serial=serial or None, starting_ru=starting_ru,
               notes=notes or None)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def update_device(db: Session, device: Device, **kwargs) -> Device:
    for k, v in kwargs.items():
        setattr(device, k, v or None if k in ("serial", "notes") else v)
    db.commit()
    db.refresh(device)
    return device


def delete_device(db: Session, device: Device) -> None:
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
                  notes: str = "") -> Switch:
    sw = Switch(rack_id=rack_id, name=name, switch_role=switch_role,
                serial=serial or None, starting_ru=starting_ru, notes=notes or None)
    db.add(sw)
    db.commit()
    db.refresh(sw)
    return sw


def update_switch(db: Session, switch: Switch, **kwargs) -> Switch:
    for k, v in kwargs.items():
        setattr(switch, k, v or None if k in ("serial", "notes") else v)
    db.commit()
    db.refresh(switch)
    return switch


def delete_switch(db: Session, switch: Switch) -> None:
    db.delete(switch)
    db.commit()


# ── Patch Panels ──────────────────────────────────────────────────────────

def list_patch_panels(db: Session, rack_id: int) -> list[PatchPanel]:
    return db.query(PatchPanel).filter(PatchPanel.rack_id == rack_id).order_by(PatchPanel.name).all()


def create_patch_panel(db: Session, rack_id: int, name: str,
                       starting_ru: Optional[int] = None, notes: str = "") -> PatchPanel:
    pp = PatchPanel(rack_id=rack_id, name=name, starting_ru=starting_ru, notes=notes or None)
    db.add(pp)
    db.commit()
    db.refresh(pp)
    return pp


def update_patch_panel(db: Session, pp: PatchPanel, **kwargs) -> PatchPanel:
    for k, v in kwargs.items():
        setattr(pp, k, v or None if k == "notes" else v)
    db.commit()
    db.refresh(pp)
    return pp


def delete_patch_panel(db: Session, pp: PatchPanel) -> None:
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
             "serial": r.serial or "", "rack": r.rack.name} for r in rows]


def autocomplete_switches(db: Session, q: str, role: Optional[str] = None, limit: int = 10) -> list[dict]:
    query = db.query(Switch).options(joinedload(Switch.rack)).filter(Switch.name.ilike(f"%{q}%"))
    if role:
        query = query.filter(Switch.switch_role == role)
    rows = query.order_by(Switch.name).limit(limit).all()
    return [{"id": r.id, "label": f"{r.name} ({r.switch_role})", "name": r.name,
             "role": r.switch_role, "serial": r.serial or "", "rack": r.rack.name} for r in rows]
