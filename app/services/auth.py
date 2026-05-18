import secrets
from datetime import datetime
from typing import Optional

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.user import User

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.username).all()


def authenticate(db: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login = datetime.utcnow()
    db.commit()
    return user


def create_user(
    db: Session,
    username: str,
    display_name: str,
    password: str,
    role: str = "viewer",
    force_password_change: bool = False,
) -> User:
    user = User(
        username=username,
        display_name=display_name,
        password_hash=hash_password(password),
        role=role,
        force_password_change=force_password_change,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def generate_temp_password(length: int = 16) -> str:
    """Cryptographically random password, URL-safe characters."""
    return secrets.token_urlsafe(length)
