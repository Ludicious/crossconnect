from sqlalchemy.orm import Session
from app.models.settings import AppSetting


def get_bool_setting(db: Session, key: str, default: bool = True) -> bool:
    """Read a boolean app_setting. 'true'/'1'/'yes' = True, else False."""
    row = db.get(AppSetting, key)
    if row is None:
        return default
    return row.value.lower() in ("true", "1", "yes")


def get_all_settings(db: Session) -> dict[str, str]:
    """Return all app_settings as a key→value dict."""
    rows = db.query(AppSetting).order_by(AppSetting.key).all()
    return {r.key: r.value for r in rows}


def upsert_setting(db: Session, key: str, value: str) -> None:
    """Create or update a single app_setting. Does NOT commit."""
    row = db.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
