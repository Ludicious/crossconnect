"""
Audit logging service.
write_audit() piggybacks on the caller's db.commit() — never commits itself.
Never raises — a bad audit write must not break the operation being recorded.
"""
import sys
from typing import Optional
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.settings import AppSetting

LEVEL_ORDER = ["none", "work_orders", "medium", "wide"]


def get_audit_level(db: Session) -> str:
    row = db.get(AppSetting, "audit_level")
    return row.value if row else "medium"


def write_audit(
    db: Session,
    user_id: Optional[int],
    required_level: str,
    entity_type: str,
    entity_id: Optional[int],
    action: str,
    detail: Optional[str] = None,
    field_name: Optional[str] = None,
    old_value=None,
    new_value=None,
) -> None:
    try:
        current = get_audit_level(db)
        ci = LEVEL_ORDER.index(current) if current in LEVEL_ORDER else LEVEL_ORDER.index("medium")
        ri = LEVEL_ORDER.index(required_level) if required_level in LEVEL_ORDER else LEVEL_ORDER.index("medium")
        if current == "none" or ci < ri:
            return
        db.add(AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            detail=detail,
        ))
    except Exception as e:
        print(f"[audit] write_audit failed: {e}", file=sys.stderr)
