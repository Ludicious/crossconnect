"""
Admin panel router — all routes require admin role.
"""
import json
import sqlite3
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.db import get_db
from app.routers.auth import get_current_user
from app.models.user import User
import app.services.auth as auth_svc
import app.services.backup as backup_svc
import app.services.recycle_bin as rb_svc
from app.services.settings import get_all_settings, get_bool_setting, upsert_setting

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

# In-memory staging for restore confirmation (token → file bytes).
# Cleared on app restart — acceptable for an admin-only operation.
_PENDING_RESTORES: dict[str, bytes] = {}

VALID_ROLES = {"admin", "architect", "dc_tech", "viewer"}

TUNING_EDITABLE_KEYS = {
    "cable_slack_inches_per_end",
    "cable_standard_lengths_m",
    "max_rack_ru",
    "audit_level",
    "port_adjacency_threshold",
    "excel_import_skip_sheets",
    "excel_import_column_map",
    "recycle_bin_enabled",
    "backup_directory",
}


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")


# ── Dashboard ─────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def admin_index(request: Request, db: Session = Depends(get_db),
                      user=Depends(get_current_user)):
    _require_admin(user)
    user_count = db.query(User).count()
    deleted_counts = rb_svc.get_deleted_counts(db)
    total_deleted = sum(deleted_counts.values())
    last_backup = backup_svc.get_last_backup_time(db)
    recycle_bin_enabled = get_bool_setting(db, "recycle_bin_enabled")
    restored = request.query_params.get("restored")
    return templates.TemplateResponse(request=request, name="admin/index.html", context={
        "user": user,
        "user_count": user_count,
        "deleted_counts": deleted_counts,
        "total_deleted": total_deleted,
        "last_backup": last_backup,
        "recycle_bin_enabled": recycle_bin_enabled,
        "restored": restored,
    })


# ── Users ─────────────────────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request, db: Session = Depends(get_db),
                      user=Depends(get_current_user)):
    _require_admin(user)
    users = auth_svc.list_users(db)
    error = request.query_params.get("error")
    success = request.query_params.get("success")
    return templates.TemplateResponse(request=request, name="admin/users.html", context={
        "user": user,
        "users": users,
        "valid_roles": sorted(VALID_ROLES),
        "error": error,
        "success": success,
    })


@router.post("/users/create")
async def admin_users_create(request: Request, db: Session = Depends(get_db),
                              user=Depends(get_current_user)):
    _require_admin(user)
    form = await request.form()
    username = (form.get("username") or "").strip()
    display_name = (form.get("display_name") or "").strip()
    role = (form.get("role") or "viewer").strip()
    password = (form.get("password") or "").strip()

    if not username or not display_name or not password:
        return RedirectResponse(
            "/admin/users?error=Username%2C+display+name%2C+and+password+are+required.",
            status_code=302)
    if role not in VALID_ROLES:
        return RedirectResponse(f"/admin/users?error=Invalid+role.", status_code=302)
    if auth_svc.get_user_by_username(db, username):
        return RedirectResponse(
            f"/admin/users?error=Username+already+exists.", status_code=302)
    auth_svc.create_user(db, username=username, display_name=display_name,
                         password=password, role=role)
    return RedirectResponse("/admin/users?success=User+created.", status_code=302)


@router.post("/users/{user_id}/role")
async def admin_users_role(user_id: int, request: Request, db: Session = Depends(get_db),
                            user=Depends(get_current_user)):
    _require_admin(user)
    form = await request.form()
    new_role = (form.get("role") or "").strip()
    if new_role not in VALID_ROLES:
        return RedirectResponse("/admin/users?error=Invalid+role.", status_code=302)
    target = auth_svc.get_user(db, user_id)
    if not target:
        raise HTTPException(404, "User not found.")
    target.role = new_role
    db.commit()
    return RedirectResponse("/admin/users?success=Role+updated.", status_code=302)


@router.post("/users/{user_id}/deactivate")
async def admin_users_deactivate(user_id: int, request: Request,
                                  db: Session = Depends(get_db),
                                  user=Depends(get_current_user)):
    _require_admin(user)
    if user_id == user.id:
        return RedirectResponse(
            "/admin/users?error=Cannot+deactivate+your+own+account.", status_code=302)
    target = auth_svc.get_user(db, user_id)
    if not target:
        raise HTTPException(404, "User not found.")
    target.is_active = False
    db.commit()
    return RedirectResponse("/admin/users?success=User+deactivated.", status_code=302)


# ── Tuning ────────────────────────────────────────────────────────────────

@router.get("/tuning", response_class=HTMLResponse)
async def admin_tuning_get(request: Request, db: Session = Depends(get_db),
                            user=Depends(get_current_user)):
    _require_admin(user)
    settings = get_all_settings(db)
    saved = request.query_params.get("saved")
    error = request.query_params.get("error")
    return templates.TemplateResponse(request=request, name="admin/tuning.html", context={
        "user": user,
        "settings": settings,
        "saved": saved,
        "error": error,
    })


@router.post("/tuning")
async def admin_tuning_post(request: Request, db: Session = Depends(get_db),
                             user=Depends(get_current_user)):
    _require_admin(user)
    form = await request.form()
    errors: list[str] = []

    col_map = (form.get("excel_import_column_map") or "").strip()
    if col_map:
        try:
            json.loads(col_map)
        except json.JSONDecodeError as e:
            errors.append(f"excel_import_column_map: invalid JSON — {e}")

    lengths_raw = (form.get("cable_standard_lengths_m") or "").strip()
    if lengths_raw:
        try:
            [float(x.strip()) for x in lengths_raw.split(",") if x.strip()]
        except ValueError:
            errors.append("cable_standard_lengths_m: must be comma-separated numbers")

    threshold_raw = (form.get("port_adjacency_threshold") or "").strip()
    if threshold_raw:
        try:
            v = int(threshold_raw)
            if v <= 0:
                raise ValueError()
        except ValueError:
            errors.append("port_adjacency_threshold: must be a positive integer")

    if errors:
        from urllib.parse import quote
        msg = quote("; ".join(errors))
        return RedirectResponse(f"/admin/tuning?error={msg}", status_code=302)

    for key in TUNING_EDITABLE_KEYS:
        val = form.get(key)
        if val is not None:
            upsert_setting(db, key, val.strip())
    db.commit()
    return RedirectResponse("/admin/tuning?saved=1", status_code=302)


# ── Recycle Bin ───────────────────────────────────────────────────────────

VALID_TABS = {"connections", "work_orders", "devices", "racks", "switches"}


@router.get("/recycle-bin", response_class=HTMLResponse)
async def admin_recycle_bin(request: Request, db: Session = Depends(get_db),
                             user=Depends(get_current_user)):
    _require_admin(user)
    tab = request.query_params.get("tab", "connections")
    if tab not in VALID_TABS:
        tab = "connections"

    recycle_bin_enabled = get_bool_setting(db, "recycle_bin_enabled")
    deleted_counts = rb_svc.get_deleted_counts(db)

    deleted_connections = rb_svc.list_deleted_connections(db) if tab == "connections" else []
    deleted_work_orders = rb_svc.list_deleted_work_orders(db) if tab == "work_orders" else []
    deleted_devices = rb_svc.list_deleted_devices(db) if tab == "devices" else []
    deleted_racks = rb_svc.list_deleted_racks(db) if tab == "racks" else []
    deleted_switches = rb_svc.list_deleted_switches(db) if tab == "switches" else []

    return templates.TemplateResponse(request=request, name="admin/recycle_bin.html", context={
        "user": user,
        "tab": tab,
        "recycle_bin_enabled": recycle_bin_enabled,
        "deleted_connections": deleted_connections,
        "deleted_work_orders": deleted_work_orders,
        "deleted_devices": deleted_devices,
        "deleted_racks": deleted_racks,
        "deleted_switches": deleted_switches,
        "deleted_counts": deleted_counts,
    })


@router.post("/recycle-bin/restore/{entity_type}/{item_id}")
async def admin_recycle_bin_restore(entity_type: str, item_id: int,
                                     db: Session = Depends(get_db),
                                     user=Depends(get_current_user)):
    _require_admin(user)
    try:
        if entity_type == "connections":
            rb_svc.restore_connection(db, item_id)
        elif entity_type == "work_orders":
            rb_svc.restore_work_order(db, item_id)
        elif entity_type == "devices":
            rb_svc.restore_device(db, item_id)
        elif entity_type == "racks":
            rb_svc.restore_rack(db, item_id)
        elif entity_type == "switches":
            rb_svc.restore_switch(db, item_id)
        else:
            raise HTTPException(400, f"Unknown entity type: {entity_type}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/admin/recycle-bin?tab={entity_type}", status_code=302)


@router.post("/recycle-bin/delete/{entity_type}/{item_id}")
async def admin_recycle_bin_delete(entity_type: str, item_id: int,
                                    db: Session = Depends(get_db),
                                    user=Depends(get_current_user)):
    _require_admin(user)
    try:
        if entity_type == "connections":
            rb_svc.hard_delete_connection(db, item_id)
        elif entity_type == "work_orders":
            rb_svc.hard_delete_work_order(db, item_id)
        elif entity_type == "devices":
            rb_svc.hard_delete_device(db, item_id)
        elif entity_type == "racks":
            rb_svc.hard_delete_rack(db, item_id)
        elif entity_type == "switches":
            rb_svc.hard_delete_switch(db, item_id)
        else:
            raise HTTPException(400, f"Unknown entity type: {entity_type}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/admin/recycle-bin?tab={entity_type}", status_code=302)


@router.post("/recycle-bin/purge/{entity_type}")
async def admin_recycle_bin_purge(entity_type: str,
                                   db: Session = Depends(get_db),
                                   user=Depends(get_current_user)):
    _require_admin(user)
    try:
        rb_svc.purge_all(db, entity_type)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/admin/recycle-bin?tab={entity_type}", status_code=302)


# ── Backup ────────────────────────────────────────────────────────────────

@router.get("/backup", response_class=HTMLResponse)
async def admin_backup_get(request: Request, db: Session = Depends(get_db),
                            user=Depends(get_current_user)):
    _require_admin(user)
    last_backup = backup_svc.get_last_backup_time(db)
    is_sqlite = app_settings.database_url.startswith("sqlite")
    return templates.TemplateResponse(request=request, name="admin/backup.html", context={
        "user": user,
        "last_backup": last_backup,
        "is_sqlite": is_sqlite,
    })


@router.post("/backup/download")
async def admin_backup_download(request: Request, db: Session = Depends(get_db),
                                 user=Depends(get_current_user)):
    _require_admin(user)
    try:
        file_bytes = backup_svc.create_backup(db)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    now = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return Response(
        content=file_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="crossconnect-backup-{now}.db"'},
    )


@router.post("/backup/restore")
async def admin_backup_restore_upload(request: Request,
                                       file: UploadFile = File(...),
                                       db: Session = Depends(get_db),
                                       user=Depends(get_current_user)):
    _require_admin(user)
    file_bytes = await file.read()

    SQLITE_MAGIC = b"SQLite format 3\x00"
    if not file_bytes.startswith(SQLITE_MAGIC):
        raise HTTPException(400, "Uploaded file is not a valid SQLite database.")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        conn_check = sqlite3.connect(str(tmp_path))
        try:
            cur = conn_check.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
            )
            if not cur.fetchone():
                raise HTTPException(400, "Backup does not contain an alembic_version table.")
            cur.execute("SELECT version_num FROM alembic_version")
            row = cur.fetchone()
            backup_version = row[0] if row else "unknown"
        finally:
            conn_check.close()
    finally:
        tmp_path.unlink(missing_ok=True)

    with db.bind.connect() as live_conn:
        result = live_conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        current_version = result[0] if result else "unknown"

    token = str(uuid.uuid4())
    _PENDING_RESTORES[token] = file_bytes
    file_size_kb = len(file_bytes) // 1024

    return templates.TemplateResponse(request=request, name="admin/restore_confirm.html", context={
        "user": user,
        "token": token,
        "filename": file.filename or "backup.db",
        "file_size_kb": file_size_kb,
        "backup_version": backup_version,
        "current_version": current_version,
        "versions_match": backup_version == current_version,
    })


@router.post("/backup/restore-execute")
async def admin_backup_restore_execute(request: Request,
                                        token: str = Form(...),
                                        db: Session = Depends(get_db),
                                        user=Depends(get_current_user)):
    _require_admin(user)
    file_bytes = _PENDING_RESTORES.pop(token, None)
    if not file_bytes:
        raise HTTPException(
            400, "Restore session expired or invalid. Please upload the file again.")
    try:
        backup_svc.restore_backup(db, file_bytes)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    return RedirectResponse("/admin?restored=1", status_code=302)
