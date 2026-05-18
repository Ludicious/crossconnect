from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.routers.auth import get_current_user
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit", tags=["audit"])
templates = Jinja2Templates(directory="app/templates")


def _tpl(name: str, ctx: dict, status_code: int = 200):
    request = ctx["request"]
    return templates.TemplateResponse(request=request, name=name, context=ctx,
                                       status_code=status_code)


@router.get("/", response_class=HTMLResponse)
async def audit_log(
    request: Request,
    entity_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog).options(joinedload(AuditLog.user))

    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if date_from:
        try:
            q = q.filter(AuditLog.timestamp >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(AuditLog.timestamp <= datetime.fromisoformat(date_to + "T23:59:59"))
        except ValueError:
            pass

    total = q.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    entries = q.order_by(AuditLog.timestamp.desc()).offset(offset).limit(per_page).all()
    users = db.query(User).filter(User.is_active == True).order_by(User.display_name).all()

    entity_types = [r[0] for r in db.query(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type).all()]

    return _tpl("audit/index.html", {
        "request": request, "user": user,
        "entries": entries,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "users": users,
        "entity_types": entity_types,
        "filter_entity_type": entity_type,
        "filter_user_id": user_id,
        "filter_action": action,
        "filter_date_from": date_from,
        "filter_date_to": date_to,
    })
