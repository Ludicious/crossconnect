from typing import Optional
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.db import get_db
from app.routers.auth import get_current_user
from app.models.connection import Connection
from app.models.work_order import WorkOrder
from app.models.inventory import Datacenter, Rack, Switch
import app.services.inventory as inv_svc

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="app/templates")


def _tpl(request, name, ctx, status_code=200):
    return templates.TemplateResponse(request=request, name=name,
                                       context=ctx, status_code=status_code)


@router.get("/", response_class=HTMLResponse)
async def reports_index(request: Request, user=Depends(get_current_user),
                         db: Session = Depends(get_db)):
    datacenters = inv_svc.list_datacenters(db)
    return _tpl(request, "reports/index.html",
                {"request": request, "user": user, "datacenters": datacenters})


@router.get("/connections", response_class=HTMLResponse)
async def connection_report(
    request: Request,
    dc_id: str = Query(default=""),
    rack_id: str = Query(default=""),
    switch_id: str = Query(default=""),
    wo_id: str = Query(default=""),
    install_status: str = Query(default=""),
    fabric: str = Query(default=""),
    action: str = Query(default=""),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dc_id_int     = int(dc_id)      if dc_id.strip()      else None
    rack_id_int   = int(rack_id)    if rack_id.strip()    else None
    switch_id_int = int(switch_id)  if switch_id.strip()  else None
    wo_id_int     = int(wo_id)      if wo_id.strip()      else None
    install_status_val = install_status.strip() or None
    fabric_val         = fabric.strip() or None
    action_val         = action.strip() or None

    # Build connection query with filters
    q = (db.query(Connection)
         .join(WorkOrder)
         .filter(Connection.deleted_at.is_(None))
         .filter(WorkOrder.status.in_(["issued", "in_progress", "complete"]))
         .options(joinedload(Connection.work_order).joinedload(WorkOrder.datacenter)))

    if dc_id_int:
        q = q.filter(WorkOrder.datacenter_id == dc_id_int)
    if wo_id_int:
        q = q.filter(Connection.work_order_id == wo_id_int)
    if install_status_val:
        q = q.filter(Connection.install_status == install_status_val)
    if fabric_val:
        q = q.filter(Connection.fabric == fabric_val)
    if action_val:
        q = q.filter(Connection.action == action_val)
    if rack_id_int:
        q = q.filter(
            or_(Connection.device_rack_id == rack_id_int,
                Connection.switch_rack_id == rack_id_int)
        )
    if switch_id_int:
        q = q.filter(Connection.switch_id == switch_id_int)

    connections = q.order_by(WorkOrder.id, Connection.id).all()

    # Filter controls
    datacenters = inv_svc.list_datacenters(db)
    work_orders = (db.query(WorkOrder)
                   .filter(WorkOrder.status.in_(["issued","in_progress","complete"]))
                   .order_by(WorkOrder.name).all())

    return _tpl(request, "reports/connections.html", {
        "request": request, "user": user,
        "connections": connections,
        "datacenters": datacenters,
        "work_orders": work_orders,
        "filter_dc_id": dc_id_int,
        "filter_wo_id": wo_id_int,
        "filter_install_status": install_status_val,
        "filter_fabric": fabric_val,
        "filter_action": action_val,
        "INSTALL_STATUSES": ["pending", "done", "blocked", "change_required"],
        "ACTIONS": ["A", "R", "C"],
        "FABRICS": ["A", "B"],
    })
