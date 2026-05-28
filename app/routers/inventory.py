import csv
import io
import json

from fastapi import APIRouter, Request, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.routers.auth import get_current_user, require_roles
import app.services.inventory as svc
from app.services.settings import get_setting

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
                                    has_grid_system=has_grid_system, notes=notes, user_id=user.id)
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
        svc.update_datacenter(db, dc, user_id=user.id, name=name, code=code, address=address,
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
        svc.delete_datacenter(db, dc, user_id=user.id)
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
                                total_ru=total_ru, notes=notes, user_id=user.id)
        return RedirectResponse(f"/inventory/racks/{rack.id}", status_code=302)
    except ValueError as e:
        return _tpl(request, "inventory/rack_form.html",
                    {"request": request, "user": user, "dc": dc, "rack": None, "error": str(e)}, 400)


# ── Rack CSV import ───────────────────────────────────────────────────────

_RACK_CSV_HEADERS = ["datacenter_code", "name", "row_label", "rack_number", "notes"]

def _parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    return [row for row in reader]

@router.get("/racks/import-template")
async def rack_import_template(user=Depends(get_current_user)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_RACK_CSV_HEADERS)
    w.writerow(["DC1", "DC1-A01", "A", "01", "Example rack"])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="rack_import_template.csv"'},
    )


@router.get("/racks/import", response_class=HTMLResponse)
async def rack_import_get(
    request: Request, user=Depends(get_current_user), db: Session = Depends(get_db),
    dc_code: Optional[str] = Query(None),
):
    _arch_or_admin(request, db)
    return _tpl(request, "inventory/rack_import.html", {
        "request": request, "user": user,
        "preview": None, "result": None,
        "prefill_dc": dc_code or "",
    })


@router.post("/racks/import", response_class=HTMLResponse)
async def rack_import_post(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    file: Optional[UploadFile] = File(None),
    raw_json: Optional[str] = Form(None),
    confirmed: Optional[str] = Form(None),
):
    _arch_or_admin(request, db)

    if confirmed and raw_json:
        rows = json.loads(raw_json)
        result = svc.bulk_create_racks(db, rows, user_id=user.id)
        return _tpl(request, "inventory/rack_import.html", {
            "request": request, "user": user,
            "preview": None, "result": result, "prefill_dc": "",
        })

    # Parse uploaded file for preview
    if not file or not file.filename:
        return _tpl(request, "inventory/rack_import.html", {
            "request": request, "user": user,
            "preview": None, "result": None, "prefill_dc": "",
            "error": "No file uploaded.",
        }, 400)

    text = (await file.read()).decode("utf-8-sig", errors="replace")
    rows = _parse_csv(text)
    if not rows:
        return _tpl(request, "inventory/rack_import.html", {
            "request": request, "user": user,
            "preview": None, "result": None, "prefill_dc": "",
            "error": "CSV is empty or header-only.",
        }, 400)

    # Validate rows for preview (no commits)
    preview_rows = []
    for i, row in enumerate(rows):
        dc_code = svc._s(row.get("datacenter_code", ""))
        name    = svc._s(row.get("name", ""))
        status, reason = "ok", ""
        if not dc_code or not name:
            status, reason = "error", "Missing datacenter_code or name"
        elif not svc.get_datacenter_by_code(db, dc_code):
            status, reason = "error", f"Datacenter '{dc_code}' not found"
        elif svc.get_rack_by_name(db, svc.get_datacenter_by_code(db, dc_code).id, name):
            status, reason = "skip", f"Rack '{name}' already exists"
        preview_rows.append({**row, "_row": i + 1, "_status": status, "_reason": reason})

    return _tpl(request, "inventory/rack_import.html", {
        "request": request, "user": user,
        "preview": preview_rows,
        "raw_json": json.dumps(rows),
        "result": None,
        "prefill_dc": "",
    })


# ── Device CSV import ─────────────────────────────────────────────────────

_DEVICE_CSV_HEADERS = [
    "datacenter_code", "rack_name", "starting_ru", "device_name",
    "serial", "system_name", "node_label", "device_type_model", "notes",
]


@router.get("/devices/import-template")
async def device_import_template(user=Depends(get_current_user)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_DEVICE_CSV_HEADERS)
    w.writerow(["DC1", "DC1-A01", "1", "dc1-storage-01", "SN12345",
                "FlashSystem-01", "Node A", "FlashSystem 9200", "Primary node"])
    w.writerow(["DC1", "DC1-A01", "3", "dc1-storage-02", "",
                "FlashSystem-01", "Node B", "", ""])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="device_import_template.csv"'},
    )


@router.get("/devices/import", response_class=HTMLResponse)
async def device_import_get(
    request: Request, user=Depends(get_current_user), db: Session = Depends(get_db),
):
    _arch_or_admin(request, db)
    return _tpl(request, "inventory/device_import.html", {
        "request": request, "user": user,
        "preview": None, "result": None,
    })


@router.post("/devices/import", response_class=HTMLResponse)
async def device_import_post(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    file: Optional[UploadFile] = File(None),
    raw_json: Optional[str] = Form(None),
    confirmed: Optional[str] = Form(None),
):
    _arch_or_admin(request, db)

    if confirmed and raw_json:
        rows = json.loads(raw_json)
        result = svc.bulk_create_devices(db, rows, user_id=user.id)
        return _tpl(request, "inventory/device_import.html", {
            "request": request, "user": user,
            "preview": None, "result": result,
        })

    if not file or not file.filename:
        return _tpl(request, "inventory/device_import.html", {
            "request": request, "user": user,
            "preview": None, "result": None,
            "error": "No file uploaded.",
        }, 400)

    text = (await file.read()).decode("utf-8-sig", errors="replace")
    rows = _parse_csv(text)
    if not rows:
        return _tpl(request, "inventory/device_import.html", {
            "request": request, "user": user,
            "preview": None, "result": None,
            "error": "CSV is empty or header-only.",
        }, 400)

    # Validate for preview
    preview_rows = []
    for i, row in enumerate(rows):
        dc_code     = svc._s(row.get("datacenter_code", ""))
        rack_name   = svc._s(row.get("rack_name", ""))
        device_name = svc._s(row.get("device_name", ""))
        status, reason, warn = "ok", "", ""

        if not dc_code or not rack_name or not device_name:
            status, reason = "error", "Missing datacenter_code, rack_name, or device_name"
        else:
            dc = svc.get_datacenter_by_code(db, dc_code)
            if not dc:
                status, reason = "error", f"Datacenter '{dc_code}' not found"
            else:
                rack = svc.get_rack_by_name(db, dc.id, rack_name)
                if not rack:
                    status, reason = "error", f"Rack '{rack_name}' not found in {dc_code}"
                else:
                    from app.models.inventory import Device
                    from sqlalchemy import func as _f
                    dup = db.query(Device).filter(
                        Device.rack_id == rack.id,
                        _f.lower(Device.name) == device_name.lower(),
                        Device.deleted_at.is_(None),
                    ).first()
                    if dup:
                        status, reason = "skip", f"Device '{device_name}' already exists in {rack_name}"
                    else:
                        dt_model = svc._s(row.get("device_type_model", ""))
                        if dt_model and not svc.get_device_type_by_model(db, dt_model):
                            warn = f"Device type '{dt_model}' not found — will import without type"

        preview_rows.append({**row, "_row": i + 1, "_status": status,
                              "_reason": reason, "_warn": warn})

    return _tpl(request, "inventory/device_import.html", {
        "request": request, "user": user,
        "preview": preview_rows,
        "raw_json": json.dumps(rows),
        "result": None,
    })


@router.get("/racks/{rack_id}", response_class=HTMLResponse)
async def rack_detail(rack_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rack = svc.get_rack(db, rack_id)
    if not rack:
        raise HTTPException(404)
    max_ru = int(get_setting(db, "max_rack_ru") or 42)
    elevation = svc.get_rack_elevation(db, rack_id, max_ru=max_ru)
    return _tpl(request, "inventory/rack_detail.html", {
        "request": request, "user": user, "rack": rack,
        "elevation": elevation, "max_ru": max_ru,
    })


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
        svc.update_rack(db, rack, user_id=user.id, name=name, grid_position=grid_position, total_ru=total_ru, notes=notes)
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
        svc.delete_rack(db, rack, user_id=user.id)
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
    system_id: Optional[int] = Form(None), node_label: str = Form(""),
    starting_ru: Optional[int] = Form(None),
    device_type_id: Optional[int] = Form(None),
    parent_device_id: Optional[int] = Form(None),
    slot_number: Optional[int] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    rack = svc.get_rack(db, rack_id)
    if not rack:
        raise HTTPException(404)
    try:
        svc.create_device(db, rack_id=rack_id, name=name, system_id=system_id or None,
                          node_label=node_label or None,
                          serial=serial, starting_ru=starting_ru,
                          device_type_id=device_type_id or None,
                          parent_device_id=parent_device_id or None,
                          slot_number=slot_number, notes=notes, user_id=user.id)
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
    system_id: Optional[int] = Form(None), node_label: str = Form(""),
    starting_ru: Optional[int] = Form(None),
    device_type_id: Optional[int] = Form(None),
    parent_device_id: Optional[int] = Form(None),
    slot_number: Optional[int] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    device = svc.get_device(db, device_id)
    if not device:
        raise HTTPException(404)
    svc.update_device(db, device, user_id=user.id, name=name, serial=serial,
                      system_id=system_id or None, node_label=node_label or None,
                      starting_ru=starting_ru,
                      device_type_id=device_type_id or None,
                      parent_device_id=parent_device_id or None,
                      slot_number=slot_number, notes=notes)
    return RedirectResponse(f"/inventory/racks/{device.rack_id}", status_code=302)


@router.post("/devices/{device_id}/delete")
async def device_delete(device_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _arch_or_admin(request, db)
    device = svc.get_device(db, device_id)
    if not device:
        raise HTTPException(404)
    rack_id = device.rack_id
    svc.delete_device(db, device, user_id=user.id)
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
    switch_type_id: Optional[int] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    rack = svc.get_rack(db, rack_id)
    if not rack:
        raise HTTPException(404)
    svc.create_switch(db, rack_id=rack_id, name=name, switch_role=switch_role,
                      serial=serial, starting_ru=starting_ru,
                      switch_type_id=switch_type_id or None, notes=notes, user_id=user.id)
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
    switch_type_id: Optional[int] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    sw = svc.get_switch(db, switch_id)
    if not sw:
        raise HTTPException(404)
    svc.update_switch(db, sw, user_id=user.id, name=name, serial=serial, switch_role=switch_role,
                      starting_ru=starting_ru, switch_type_id=switch_type_id or None, notes=notes)
    return RedirectResponse(f"/inventory/racks/{sw.rack_id}", status_code=302)


@router.post("/switches/{switch_id}/delete")
async def switch_delete(switch_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _arch_or_admin(request, db)
    sw = svc.get_switch(db, switch_id)
    if not sw:
        raise HTTPException(404)
    rack_id = sw.rack_id
    svc.delete_switch(db, sw, user_id=user.id)
    return RedirectResponse(f"/inventory/racks/{rack_id}", status_code=302)


# ── Patch panels ──────────────────────────────────────────────────────────

@router.post("/racks/{rack_id}/patch-panels/new")
async def pp_create(
    rack_id: int, request: Request,
    name: str = Form(...), starting_ru: Optional[int] = Form(None), notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    svc.create_patch_panel(db, rack_id=rack_id, name=name, starting_ru=starting_ru,
                           notes=notes, user_id=user.id)
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
    svc.update_patch_panel(db, pp, user_id=user.id, name=name, starting_ru=starting_ru, notes=notes)
    return RedirectResponse(f"/inventory/racks/{pp.rack_id}", status_code=302)


@router.post("/patch-panels/{pp_id}/delete")
async def pp_delete(pp_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _arch_or_admin(request, db)
    from app.models.inventory import PatchPanel
    pp = db.get(PatchPanel, pp_id)
    if not pp:
        raise HTTPException(404)
    rack_id = pp.rack_id
    svc.delete_patch_panel(db, pp, user_id=user.id)
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
    name: str = Form(...), system_type: str = Form(""), notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    try:
        s = svc.create_system(db, name=name, system_type=system_type, notes=notes, user_id=user.id)
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
    name: str = Form(...), system_type: str = Form(""), notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    system = svc.get_system(db, system_id)
    if not system:
        raise HTTPException(404)
    try:
        svc.update_system(db, system, user_id=user.id, name=name, system_type=system_type, notes=notes)
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
        svc.delete_system(db, system, user_id=user.id)
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


# ── Device Types ──────────────────────────────────────────────────────────

@router.get("/device-types", response_class=HTMLResponse)
async def dt_list(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    dts = svc.list_device_types(db)
    return _tpl(request, "inventory/device_type_list.html",
                {"request": request, "user": user, "device_types": dts})


@router.get("/device-types/new", response_class=HTMLResponse)
async def dt_new(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    return _tpl(request, "inventory/device_type_form.html",
                {"request": request, "user": user, "dt": None, "error": None})


@router.post("/device-types/new")
async def dt_create(
    request: Request,
    manufacturer: str = Form(...), model: str = Form(...),
    category: str = Form("server"), rack_u: Optional[int] = Form(None),
    slot_count: Optional[int] = Form(None), notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    try:
        dt = svc.create_device_type(db, manufacturer=manufacturer, model=model,
                                     category=category, rack_u=rack_u,
                                     slot_count=slot_count, notes=notes, user_id=user.id)
        return RedirectResponse(f"/inventory/device-types", status_code=302)
    except ValueError as e:
        return _tpl(request, "inventory/device_type_form.html",
                    {"request": request, "user": user, "dt": None, "error": str(e)}, 400)


@router.get("/device-types/{dt_id}/edit", response_class=HTMLResponse)
async def dt_edit(dt_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    dt = svc.get_device_type(db, dt_id)
    if not dt:
        raise HTTPException(404)
    return _tpl(request, "inventory/device_type_form.html",
                {"request": request, "user": user, "dt": dt, "error": None})


@router.post("/device-types/{dt_id}/edit")
async def dt_update(
    dt_id: int, request: Request,
    manufacturer: str = Form(...), model: str = Form(...),
    category: str = Form("server"), rack_u: Optional[int] = Form(None),
    slot_count: Optional[int] = Form(None), notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    dt = svc.get_device_type(db, dt_id)
    if not dt:
        raise HTTPException(404)
    try:
        svc.update_device_type(db, dt, user_id=user.id, manufacturer=manufacturer, model=model,
                                category=category, rack_u=rack_u,
                                slot_count=slot_count, notes=notes)
        return RedirectResponse("/inventory/device-types", status_code=302)
    except ValueError as e:
        return _tpl(request, "inventory/device_type_form.html",
                    {"request": request, "user": user, "dt": dt, "error": str(e)}, 400)


@router.post("/device-types/{dt_id}/delete")
async def dt_delete(dt_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _arch_or_admin(request, db)
    dt = svc.get_device_type(db, dt_id)
    if not dt:
        raise HTTPException(404)
    try:
        svc.delete_device_type(db, dt, user_id=user.id)
        return RedirectResponse("/inventory/device-types", status_code=302)
    except ValueError as e:
        dts = svc.list_device_types(db)
        return _tpl(request, "inventory/device_type_list.html",
                    {"request": request, "user": user, "device_types": dts, "error": str(e)}, 400)


@router.get("/autocomplete/device-types")
async def ac_device_types(q: str = Query(""), category: Optional[str] = Query(None),
                           db: Session = Depends(get_db), user=Depends(get_current_user)):
    return JSONResponse(svc.autocomplete_device_types(db, q, category))


# ── Detail JSON endpoints (for grid autocomplete fill) ────────────────────

@router.get("/api/switches/{switch_id}")
async def switch_detail_json(switch_id: int, db: Session = Depends(get_db),
                              user=Depends(get_current_user)):
    sw = svc.get_switch(db, switch_id)
    if not sw:
        raise HTTPException(404)
    return {
        "id": sw.id, "name": sw.name, "serial": sw.serial or "",
        "role": sw.switch_role, "rack": sw.rack.name,
        "rack_u": sw.starting_ru,
    }


@router.get("/api/devices/{device_id}")
async def device_detail_json(device_id: int, db: Session = Depends(get_db),
                              user=Depends(get_current_user)):
    d = svc.get_device(db, device_id)
    if not d:
        raise HTTPException(404)
    return {
        "id": d.id, "name": d.name, "serial": d.serial or "",
        "rack": d.rack.name, "rack_u": d.starting_ru,
        "system": d.system.name if d.system else "",
        "node_label": d.node_label or "",
    }
