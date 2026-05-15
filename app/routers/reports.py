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
    dc_id: Optional[int] = Query(None),
    rack_id: Optional[int] = Query(None),
    switch_id: Optional[int] = Query(None),
    wo_id: Optional[int] = Query(None),
    install_status: Optional[str] = Query(None),
    fabric: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Build connection query with filters
    q = (db.query(Connection)
         .join(WorkOrder)
         .filter(Connection.deleted_at.is_(None))
         .filter(WorkOrder.status.in_(["issued", "in_progress", "complete"]))
         .options(joinedload(Connection.work_order).joinedload(WorkOrder.datacenter)))

    if dc_id:
        q = q.filter(WorkOrder.datacenter_id == dc_id)
    if wo_id:
        q = q.filter(Connection.work_order_id == wo_id)
    if install_status:
        q = q.filter(Connection.install_status == install_status)
    if fabric:
        q = q.filter(Connection.fabric == fabric)
    if action:
        q = q.filter(Connection.action == action)
    if rack_id:
        q = q.filter(
            or_(Connection.device_rack_id == rack_id,
                Connection.switch_rack_id == rack_id)
        )
    if switch_id:
        q = q.filter(Connection.switch_id == switch_id)

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
        "filter_dc_id": dc_id,
        "filter_wo_id": wo_id,
        "filter_install_status": install_status,
        "filter_fabric": fabric,
        "filter_action": action,
        "INSTALL_STATUSES": ["pending", "done", "blocked", "change_required"],
        "ACTIONS": ["A", "R", "C"],
        "FABRICS": ["A", "B"],
    })
