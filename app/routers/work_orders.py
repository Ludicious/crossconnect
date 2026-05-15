from datetime import date
from typing import Optional
import json

from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.routers.auth import get_current_user, require_roles
import app.services.work_orders as svc
import app.services.inventory as inv_svc
from app.models.work_order import VALID_WORK_TYPES

router = APIRouter(prefix="/work-orders", tags=["work_orders"])
templates = Jinja2Templates(directory="app/templates")


def _tpl(request, name, ctx, status_code=200):
    return templates.TemplateResponse(request=request, name=name,
                                       context=ctx, status_code=status_code)


def _arch_or_admin(request, db):
    return require_roles("architect", "admin")(request, db)


# ── Work order list ───────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def wo_list(
    request: Request,
    dc_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    work_orders = svc.list_work_orders(db, dc_id=dc_id, status=status)
    datacenters = inv_svc.list_datacenters(db)
    return _tpl(request, "work_orders/list.html", {
        "request": request, "user": user,
        "work_orders": work_orders, "datacenters": datacenters,
        "filter_dc_id": dc_id, "filter_status": status,
    })


# ── Create work order ─────────────────────────────────────────────────────

@router.get("/new", response_class=HTMLResponse)
async def wo_new(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    datacenters = inv_svc.list_datacenters(db)
    return _tpl(request, "work_orders/form.html", {
        "request": request, "user": user,
        "wo": None, "datacenters": datacenters,
        "work_types": list(VALID_WORK_TYPES), "error": None,
    })


@router.post("/new")
async def wo_create(
    request: Request,
    name: str = Form(...),
    datacenter_id: int = Form(...),
    work_type: str = Form("install"),
    target_date: Optional[str] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    try:
        td = date.fromisoformat(target_date) if target_date else None
        wo = svc.create_work_order(db, name=name, datacenter_id=datacenter_id,
                                    work_type=work_type, created_by=user.id,
                                    target_date=td, notes=notes)
        return RedirectResponse(f"/work-orders/{wo.id}", status_code=302)
    except ValueError as e:
        datacenters = inv_svc.list_datacenters(db)
        return _tpl(request, "work_orders/form.html", {
            "request": request, "user": user, "wo": None,
            "datacenters": datacenters, "work_types": list(VALID_WORK_TYPES), "error": str(e),
        }, 400)


# ── Work order detail / editor ────────────────────────────────────────────

@router.get("/{wo_id}", response_class=HTMLResponse)
async def wo_detail(
    wo_id: int, request: Request,
    user=Depends(get_current_user), db: Session = Depends(get_db),
):
    wo = svc.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(404)
    connections = svc.list_connections(db, wo_id)
    return _tpl(request, "work_orders/detail.html", {
        "request": request, "user": user, "wo": wo,
        "connections": connections,
        "CABLE_TYPES": ["RJ45", "LC_Fiber", "DAC", "other"],
        "PURPOSES": ["management", "data", "storage", "other"],
        "ACTIONS": ["A", "R", "C"],
        "FABRICS": ["", "A", "B"],
        "INSTALL_STATUSES": ["pending", "done", "blocked", "change_required"],
    })


# ── Edit work order metadata ──────────────────────────────────────────────

@router.get("/{wo_id}/edit", response_class=HTMLResponse)
async def wo_edit(wo_id: int, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _arch_or_admin(request, db)
    wo = svc.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(404)
    datacenters = inv_svc.list_datacenters(db)
    return _tpl(request, "work_orders/form.html", {
        "request": request, "user": user, "wo": wo,
        "datacenters": datacenters, "work_types": list(VALID_WORK_TYPES), "error": None,
    })


@router.post("/{wo_id}/edit")
async def wo_update(
    wo_id: int, request: Request,
    name: str = Form(...), datacenter_id: int = Form(...),
    work_type: str = Form("install"), target_date: Optional[str] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    wo = svc.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(404)
    td = date.fromisoformat(target_date) if target_date else None
    svc.update_work_order(db, wo, name=name, datacenter_id=datacenter_id,
                           work_type=work_type, target_date=td, notes=notes)
    return RedirectResponse(f"/work-orders/{wo_id}", status_code=302)


# ── Status transitions ────────────────────────────────────────────────────

@router.post("/{wo_id}/status")
async def wo_status(
    wo_id: int, request: Request,
    new_status: str = Form(...),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    wo = svc.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(404)
    try:
        svc.transition_status(db, wo, new_status, user)
        return RedirectResponse(f"/work-orders/{wo_id}", status_code=302)
    except ValueError as e:
        connections = svc.list_connections(db, wo_id)
        row_errors = getattr(e, "row_errors", [])
        return _tpl(request, "work_orders/detail.html", {
            "request": request, "user": user, "wo": wo,
            "connections": connections, "error": str(e),
            "validation_errors": row_errors,
            "CABLE_TYPES": ["RJ45", "LC_Fiber", "DAC", "other"],
            "PURPOSES": ["management", "data", "storage", "other"],
            "ACTIONS": ["A", "R", "C"], "FABRICS": ["", "A", "B"],
            "INSTALL_STATUSES": ["pending", "done", "blocked", "change_required"],
        }, 400)


@router.post("/{wo_id}/delete")
async def wo_delete(wo_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _arch_or_admin(request, db)
    wo = svc.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(404)
    try:
        svc.delete_work_order(db, wo)
        return RedirectResponse("/work-orders", status_code=302)
    except ValueError as e:
        connections = svc.list_connections(db, wo_id)
        return _tpl(request, "work_orders/detail.html", {
            "request": request, "user": user, "wo": wo,
            "connections": connections, "error": str(e),
            "CABLE_TYPES": ["RJ45", "LC_Fiber", "DAC", "other"],
            "PURPOSES": ["management", "data", "storage", "other"],
            "ACTIONS": ["A", "R", "C"], "FABRICS": ["", "A", "B"],
            "INSTALL_STATUSES": ["pending", "done", "blocked", "change_required"],
        }, 400)


# ── Connection CRUD (JSON responses for HTMX) ─────────────────────────────

@router.post("/{wo_id}/connections")
async def conn_create(
    wo_id: int, request: Request,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    """Create a single connection row from form data. Returns JSON."""
    _arch_or_admin(request, db)
    wo = svc.get_work_order(db, wo_id)
    if not wo or wo.status not in ("draft", "issued"):
        raise HTTPException(400, "Work order is not editable")
    form = await request.form()
    conn, errors, warnings = svc.create_connection(db, wo_id, dict(form), user.id)
    if errors:
        return JSONResponse({"ok": False, "errors": errors, "warnings": warnings}, 400)
    return JSONResponse({"ok": True, "id": conn.id, "warnings": warnings})


@router.post("/{wo_id}/connections/bulk")
async def conn_bulk(
    wo_id: int, request: Request,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    """Accept parsed rows as JSON body, bulk-insert."""
    _arch_or_admin(request, db)
    wo = svc.get_work_order(db, wo_id)
    if not wo or wo.status not in ("draft", "issued"):
        raise HTTPException(400, "Work order is not editable")
    body = await request.json()
    rows = body.get("rows", [])
    result = svc.bulk_create_connections(db, wo_id, rows, user.id)
    return JSONResponse(result)


@router.post("/{wo_id}/connections/{conn_id}/edit")
async def conn_update(
    wo_id: int, conn_id: int, request: Request,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    conn = svc.get_connection(db, conn_id)
    if not conn or conn.work_order_id != wo_id:
        raise HTTPException(404)
    wo = svc.get_work_order(db, wo_id)
    if wo.status not in ("draft", "issued"):
        raise HTTPException(400, "Work order is not editable")
    form = await request.form()
    conn, errors, warnings = svc.update_connection(db, conn, dict(form), user.id)
    if errors:
        return JSONResponse({"ok": False, "errors": errors, "warnings": warnings}, 400)
    return JSONResponse({"ok": True, "warnings": warnings})


@router.post("/{wo_id}/connections/{conn_id}/delete")
async def conn_delete(
    wo_id: int, conn_id: int, request: Request,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    _arch_or_admin(request, db)
    conn = svc.get_connection(db, conn_id)
    if not conn or conn.work_order_id != wo_id:
        raise HTTPException(404)
    svc.soft_delete_connection(db, conn, user.id)
    return JSONResponse({"ok": True})
