from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.routers.auth import get_current_user, require_roles
import app.services.inventory as svc

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = Jinja2Templates(directory="app/templates")


def _tpl(request, name, ctx, status_code=200):
    return templates.TemplateResponse(request=request, name=name, context=ctx, status_code=status_code)


def _arch_or_admin(request, db):
    return require_roles("architect", "admin")(request, db)


# ── Inventory home ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def inventory_index(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    dcs = svc.list_datacenters(db)
    systems = svc.list_systems(db)
    return _tpl(request, "inventory/index.html", {"request": request, "user": user, "datacenters": dcs, "systems": systems})


# ── Datacenters ───────────────────────────────────────────────────────────

@router.get("/datacenters/new", response_class=HTMLResponse)
async def dc_new(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    return _tpl(request, "inventory/dc_form.html", {"request": request, "user": user, "dc": None, "error": None})


@router.post("/datacenters/new")
async def dc_create(
    request: Request,
    name: str = Form(...),
    code: str = Form(...),
    address: str = Form(""),
    has_grid_system: bool = Form(False),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    try:
        dc = svc.create_datacenter(db, name=name, code=code, address=address,
                                    has_grid_system=has_grid_system, notes=notes)
        return RedirectResponse(f"/inventory/datacenters/{dc.id}", status_code=302)
    except ValueError as e:
        return _tpl(request, "inventory/dc_form.html",
                    {"request": request, "user": user, "dc": None, "error": str(e)}, 400)


@router.get("/datacenters/{dc_id}", response_class=HTMLResponse)
async def dc_detail(dc_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    dc = svc.get_datacenter(db, dc_id)
    if not dc:
        raise HTTPException(404, "Datacenter not found")
    racks = svc.list_racks(db, dc_id)
    return _tpl(request, "inventory/dc_detail.html", {"request": request, "user": user, "dc": dc, "racks": racks})


@router.get("/datacenters/{dc_id}/edit", response_class=HTMLResponse)
async def dc_edit(dc_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    dc = svc.get_datacenter(db, dc_id)
    if not dc:
        raise HTTPException(404)
    return _tpl(request, "inventory/dc_form.html", {"request": request, "user": user, "dc": dc, "error": None})


@router.post("/datacenters/{dc_id}/edit")
async def dc_update(
    dc_id: int, request: Request,
    name: str = Form(...), code: str = Form(...),
    address: str = Form(""), has_grid_system: bool = Form(False),
    notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    dc = svc.get_datacenter(db, dc_id)
    if not dc:
        raise HTTPException(404)
    try:
        svc.update_datacenter(db, dc, name=name, code=code, address=address,
                               has_grid_system=has_grid_system, notes=notes)
        return RedirectResponse(f"/inventory/datacenters/{dc_id}", status_code=302)
    except ValueError as e:
        return _tpl(request, "inventory/dc_form.html",
                    {"request": request, "user": user, "dc": dc, "error": str(e)}, 400)


@router.post("/datacenters/{dc_id}/contacts")
async def dc_save_contacts(
    dc_id: int, request: Request,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    dc = svc.get_datacenter(db, dc_id)
    if not dc:
        raise HTTPException(404)
    form = await request.form()
    # Contacts come in as: contact_name_0, contact_role_0, contact_email_0, contact_phone_0, ...
    contacts = []
    i = 0
    while f"contact_name_{i}" in form:
        contacts.append({
            "name": form.get(f"contact_name_{i}", ""),
            "role": form.get(f"contact_role_{i}", ""),
            "email": form.get(f"contact_email_{i}", ""),
            "phone": form.get(f"contact_phone_{i}", ""),
        })
        i += 1
    svc.upsert_contacts(db, dc, contacts)
    return RedirectResponse(f"/inventory/datacenters/{dc_id}", status_code=302)


@router.post("/datacenters/{dc_id}/delete")
async def dc_delete(dc_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _arch_or_admin(request, db)
    dc = svc.get_datacenter(db, dc_id)
    if not dc:
        raise HTTPException(404)
    try:
        svc.delete_datacenter(db, dc)
        return RedirectResponse("/inventory", status_code=302)
    except ValueError as e:
        racks = svc.list_racks(db, dc_id)
        return _tpl(request, "inventory/dc_detail.html",
                    {"request": request, "user": user, "dc": dc, "racks": racks, "error": str(e)}, 400)


# ── Racks ─────────────────────────────────────────────────────────────────

@router.get("/datacenters/{dc_id}/racks/new", response_class=HTMLResponse)
async def rack_new(dc_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    dc = svc.get_datacenter(db, dc_id)
    if not dc:
        raise HTTPException(404)
    return _tpl(request, "inventory/rack_form.html", {"request": request, "user": user, "dc": dc, "rack": None, "error": None})


@router.post("/datacenters/{dc_id}/racks/new")
async def rack_create(
    dc_id: int, request: Request,
    name: str = Form(...), grid_position: str = Form(""),
    total_ru: int = Form(42), notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    dc = svc.get_datacenter(db, dc_id)
    if not dc:
        raise HTTPException(404)
    try:
        rack = svc.create_rack(db, dc_id=dc_id, name=name, grid_position=grid_position,
                                total_ru=total_ru, notes=notes)
        return RedirectResponse(f"/inventory/racks/{rack.id}", status_code=302)
    except ValueError as e:
        return _tpl(request, "inventory/rack_form.html",
                    {"request": request, "user": user, "dc": dc, "rack": None, "error": str(e)}, 400)


@router.get("/racks/{rack_id}", response_class=HTMLResponse)
async def rack_detail(rack_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rack = svc.get_rack(db, rack_id)
    if not rack:
        raise HTTPException(404)
    return _tpl(request, "inventory/rack_detail.html", {"request": request, "user": user, "rack": rack})


@router.get("/racks/{rack_id}/edit", response_class=HTMLResponse)
async def rack_edit(rack_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    rack = svc.get_rack(db, rack_id)
    if not rack:
        raise HTTPException(404)
    return _tpl(request, "inventory/rack_form.html",
                {"request": request, "user": user, "dc": rack.datacenter, "rack": rack, "error": None})


@router.post("/racks/{rack_id}/edit")
async def rack_update(
    rack_id: int, request: Request,
    name: str = Form(...), grid_position: str = Form(""),
    total_ru: int = Form(42), notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    rack = svc.get_rack(db, rack_id)
    if not rack:
        raise HTTPException(404)
    try:
        svc.update_rack(db, rack, name=name, grid_position=grid_position, total_ru=total_ru, notes=notes)
        return RedirectResponse(f"/inventory/racks/{rack_id}", status_code=302)
    except ValueError as e:
        return _tpl(request, "inventory/rack_form.html",
                    {"request": request, "user": user, "dc": rack.datacenter, "rack": rack, "error": str(e)}, 400)


@router.post("/racks/{rack_id}/delete")
async def rack_delete(rack_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _arch_or_admin(request, db)
    rack = svc.get_rack(db, rack_id)
    if not rack:
        raise HTTPException(404)
    dc_id = rack.datacenter_id
    try:
        svc.delete_rack(db, rack)
        return RedirectResponse(f"/inventory/datacenters/{dc_id}", status_code=302)
    except ValueError as e:
        return _tpl(request, "inventory/rack_detail.html",
                    {"request": request, "user": user, "rack": rack, "error": str(e)}, 400)


# ── Devices (inside rack context) ─────────────────────────────────────────

@router.get("/racks/{rack_id}/devices/new", response_class=HTMLResponse)
async def device_new(rack_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    rack = svc.get_rack(db, rack_id)
    if not rack:
        raise HTTPException(404)
    systems = svc.list_systems(db)
    return _tpl(request, "inventory/device_form.html",
                {"request": request, "user": user, "rack": rack, "device": None, "systems": systems, "error": None})


@router.post("/racks/{rack_id}/devices/new")
async def device_create(
    rack_id: int, request: Request,
    name: str = Form(...), serial: str = Form(""),
    system_id: Optional[int] = Form(None), starting_ru: Optional[int] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    rack = svc.get_rack(db, rack_id)
    if not rack:
        raise HTTPException(404)
    try:
        svc.create_device(db, rack_id=rack_id, name=name, system_id=system_id or None,
                          serial=serial, starting_ru=starting_ru, notes=notes)
        return RedirectResponse(f"/inventory/racks/{rack_id}", status_code=302)
    except ValueError as e:
        systems = svc.list_systems(db)
        return _tpl(request, "inventory/device_form.html",
                    {"request": request, "user": user, "rack": rack, "device": None, "systems": systems, "error": str(e)}, 400)


@router.get("/devices/{device_id}/edit", response_class=HTMLResponse)
async def device_edit(device_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    device = svc.get_device(db, device_id)
    if not device:
        raise HTTPException(404)
    systems = svc.list_systems(db)
    return _tpl(request, "inventory/device_form.html",
                {"request": request, "user": user, "rack": device.rack, "device": device, "systems": systems, "error": None})


@router.post("/devices/{device_id}/edit")
async def device_update(
    device_id: int, request: Request,
    name: str = Form(...), serial: str = Form(""),
    system_id: Optional[int] = Form(None), starting_ru: Optional[int] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    device = svc.get_device(db, device_id)
    if not device:
        raise HTTPException(404)
    svc.update_device(db, device, name=name, serial=serial, system_id=system_id or None,
                      starting_ru=starting_ru, notes=notes)
    return RedirectResponse(f"/inventory/racks/{device.rack_id}", status_code=302)


@router.post("/devices/{device_id}/delete")
async def device_delete(device_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _arch_or_admin(request, db)
    device = svc.get_device(db, device_id)
    if not device:
        raise HTTPException(404)
    rack_id = device.rack_id
    svc.delete_device(db, device)
    return RedirectResponse(f"/inventory/racks/{rack_id}", status_code=302)


# ── Switches ──────────────────────────────────────────────────────────────

@router.get("/racks/{rack_id}/switches/new", response_class=HTMLResponse)
async def switch_new(rack_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    rack = svc.get_rack(db, rack_id)
    if not rack:
        raise HTTPException(404)
    return _tpl(request, "inventory/switch_form.html",
                {"request": request, "user": user, "rack": rack, "switch": None, "error": None})


@router.post("/racks/{rack_id}/switches/new")
async def switch_create(
    rack_id: int, request: Request,
    name: str = Form(...), serial: str = Form(""),
    switch_role: str = Form("LAN"), starting_ru: Optional[int] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    rack = svc.get_rack(db, rack_id)
    if not rack:
        raise HTTPException(404)
    svc.create_switch(db, rack_id=rack_id, name=name, switch_role=switch_role,
                      serial=serial, starting_ru=starting_ru, notes=notes)
    return RedirectResponse(f"/inventory/racks/{rack_id}", status_code=302)


@router.get("/switches/{switch_id}/edit", response_class=HTMLResponse)
async def switch_edit(switch_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    sw = svc.get_switch(db, switch_id)
    if not sw:
        raise HTTPException(404)
    return _tpl(request, "inventory/switch_form.html",
                {"request": request, "user": user, "rack": sw.rack, "switch": sw, "error": None})


@router.post("/switches/{switch_id}/edit")
async def switch_update(
    switch_id: int, request: Request,
    name: str = Form(...), serial: str = Form(""),
    switch_role: str = Form("LAN"), starting_ru: Optional[int] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    sw = svc.get_switch(db, switch_id)
    if not sw:
        raise HTTPException(404)
    svc.update_switch(db, sw, name=name, serial=serial, switch_role=switch_role,
                      starting_ru=starting_ru, notes=notes)
    return RedirectResponse(f"/inventory/racks/{sw.rack_id}", status_code=302)


@router.post("/switches/{switch_id}/delete")
async def switch_delete(switch_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _arch_or_admin(request, db)
    sw = svc.get_switch(db, switch_id)
    if not sw:
        raise HTTPException(404)
    rack_id = sw.rack_id
    svc.delete_switch(db, sw)
    return RedirectResponse(f"/inventory/racks/{rack_id}", status_code=302)


# ── Patch panels ──────────────────────────────────────────────────────────

@router.post("/racks/{rack_id}/patch-panels/new")
async def pp_create(
    rack_id: int, request: Request,
    name: str = Form(...), starting_ru: Optional[int] = Form(None), notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    svc.create_patch_panel(db, rack_id=rack_id, name=name, starting_ru=starting_ru, notes=notes)
    return RedirectResponse(f"/inventory/racks/{rack_id}", status_code=302)


@router.post("/patch-panels/{pp_id}/edit")
async def pp_update(
    pp_id: int, request: Request,
    name: str = Form(...), starting_ru: Optional[int] = Form(None), notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    from app.models.inventory import PatchPanel
    pp = db.get(PatchPanel, pp_id)
    if not pp:
        raise HTTPException(404)
    svc.update_patch_panel(db, pp, name=name, starting_ru=starting_ru, notes=notes)
    return RedirectResponse(f"/inventory/racks/{pp.rack_id}", status_code=302)


@router.post("/patch-panels/{pp_id}/delete")
async def pp_delete(pp_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _arch_or_admin(request, db)
    from app.models.inventory import PatchPanel
    pp = db.get(PatchPanel, pp_id)
    if not pp:
        raise HTTPException(404)
    rack_id = pp.rack_id
    svc.delete_patch_panel(db, pp)
    return RedirectResponse(f"/inventory/racks/{rack_id}", status_code=302)


# ── Systems ───────────────────────────────────────────────────────────────

@router.get("/systems/new", response_class=HTMLResponse)
async def system_new(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    return _tpl(request, "inventory/system_form.html",
                {"request": request, "user": user, "system": None, "error": None})


@router.post("/systems/new")
async def system_create(
    request: Request,
    name: str = Form(...), system_type: str = Form("server"), notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    try:
        s = svc.create_system(db, name=name, system_type=system_type, notes=notes)
        return RedirectResponse(f"/inventory/systems/{s.id}", status_code=302)
    except ValueError as e:
        return _tpl(request, "inventory/system_form.html",
                    {"request": request, "user": user, "system": None, "error": str(e)}, 400)


@router.get("/systems/{system_id}", response_class=HTMLResponse)
async def system_detail(system_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    system = svc.get_system(db, system_id)
    if not system:
        raise HTTPException(404)
    return _tpl(request, "inventory/system_detail.html", {"request": request, "user": user, "system": system})


@router.get("/systems/{system_id}/edit", response_class=HTMLResponse)
async def system_edit(system_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    system = svc.get_system(db, system_id)
    if not system:
        raise HTTPException(404)
    return _tpl(request, "inventory/system_form.html",
                {"request": request, "user": user, "system": system, "error": None})


@router.post("/systems/{system_id}/edit")
async def system_update(
    system_id: int, request: Request,
    name: str = Form(...), system_type: str = Form("server"), notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    system = svc.get_system(db, system_id)
    if not system:
        raise HTTPException(404)
    try:
        svc.update_system(db, system, name=name, system_type=system_type, notes=notes)
        return RedirectResponse(f"/inventory/systems/{system_id}", status_code=302)
    except ValueError as e:
        return _tpl(request, "inventory/system_form.html",
                    {"request": request, "user": user, "system": system, "error": str(e)}, 400)


@router.post("/systems/{system_id}/delete")
async def system_delete(system_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _arch_or_admin(request, db)
    system = svc.get_system(db, system_id)
    if not system:
        raise HTTPException(404)
    try:
        svc.delete_system(db, system)
        return RedirectResponse("/inventory", status_code=302)
    except ValueError as e:
        return _tpl(request, "inventory/system_detail.html",
                    {"request": request, "user": user, "system": system, "error": str(e)}, 400)


# ── Autocomplete JSON endpoints ───────────────────────────────────────────

@router.get("/autocomplete/datacenters")
async def ac_datacenters(q: str = Query(""), db: Session = Depends(get_db), user=Depends(get_current_user)):
    return JSONResponse(svc.autocomplete_datacenters(db, q))


@router.get("/autocomplete/racks")
async def ac_racks(q: str = Query(""), dc_id: Optional[int] = Query(None),
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    return JSONResponse(svc.autocomplete_racks(db, q, dc_id))


@router.get("/autocomplete/systems")
async def ac_systems(q: str = Query(""), db: Session = Depends(get_db), user=Depends(get_current_user)):
    return JSONResponse(svc.autocomplete_systems(db, q))


@router.get("/autocomplete/devices")
async def ac_devices(q: str = Query(""), rack_id: Optional[int] = Query(None),
                     db: Session = Depends(get_db), user=Depends(get_current_user)):
    return JSONResponse(svc.autocomplete_devices(db, q, rack_id))


@router.get("/autocomplete/switches")
async def ac_switches(q: str = Query(""), role: Optional[str] = Query(None),
                      db: Session = Depends(get_db), user=Depends(get_current_user)):
    return JSONResponse(svc.autocomplete_switches(db, q, role))
