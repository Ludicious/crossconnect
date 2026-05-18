from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.routers.auth import get_current_user, require_roles
import app.services.inventory as inv_svc
from app.services.analytics import (
    get_rack_elevation,
    get_port_adjacency_warnings,
    get_port_utilization,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])
templates = Jinja2Templates(directory="app/templates")


def _tpl(request, name, ctx, status_code=200):
    return templates.TemplateResponse(
        request=request, name=name, context=ctx, status_code=status_code
    )


@router.get("/rack/{rack_id}", response_class=HTMLResponse)
async def rack_elevation(
    rack_id: int,
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = get_rack_elevation(db, rack_id)
    if not data:
        raise HTTPException(404, "Rack not found")
    return _tpl(request, "analytics/rack_elevation.html", {
        "request": request, "user": user,
        "rack": data["rack"],
        "slots": data["slots"],
        "unpositioned": data["unpositioned"],
        "summary": data["summary"],
    })


@router.get("/port-adjacency", response_class=HTMLResponse)
async def port_adjacency(
    request: Request,
    wo_id: Optional[int] = Query(None),
    dc_id: Optional[int] = Query(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_roles("architect", "admin")(request, db)
    warnings = get_port_adjacency_warnings(db, wo_id=wo_id, dc_id=dc_id)
    datacenters = inv_svc.list_datacenters(db)
    from app.services.work_orders import list_work_orders
    work_orders = list_work_orders(db)

    # Read current threshold for display
    from app.models.settings import AppSetting
    setting = db.get(AppSetting, "port_adjacency_threshold")
    threshold = int(setting.value) if setting else 4

    return _tpl(request, "analytics/port_adjacency.html", {
        "request": request, "user": user,
        "warnings": warnings,
        "datacenters": datacenters,
        "work_orders": work_orders,
        "filter_wo_id": wo_id,
        "filter_dc_id": dc_id,
        "threshold": threshold,
    })


@router.get("/port-utilization", response_class=HTMLResponse)
async def port_utilization(
    request: Request,
    dc_id: Optional[int] = Query(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_roles("architect", "admin")(request, db)
    rows = get_port_utilization(db, dc_id=dc_id)
    datacenters = inv_svc.list_datacenters(db)
    return _tpl(request, "analytics/port_utilization.html", {
        "request": request, "user": user,
        "rows": rows,
        "datacenters": datacenters,
        "filter_dc_id": dc_id,
    })
