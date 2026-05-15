from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.auth import authenticate, hash_password, get_user_by_username

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Dependency — returns the User or raises 401."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from app.models.user import User
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_roles(*roles: str):
    """Dependency factory — enforces role membership."""
    def _check(request: Request, db: Session = Depends(get_db)):
        user = get_current_user(request, db)
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _check


def _tpl(name: str, ctx: dict, status_code: int = 200):
    """Wrapper so we only update one place if TemplateResponse API changes again."""
    request = ctx["request"]
    return templates.TemplateResponse(request=request, name=name, context=ctx, status_code=status_code)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    return _tpl("auth/login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate(db, username, password)
    if not user:
        return _tpl(
            "auth/login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=401,
        )
    request.session["user_id"] = user.id
    if user.force_password_change:
        return RedirectResponse("/change-password", status_code=302)
    return RedirectResponse("/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=302)
    return _tpl("auth/change_password.html", {"request": request, "error": None})


@router.post("/change-password")
async def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    from app.models.user import User
    from app.services.auth import verify_password

    user = db.get(User, user_id)
    ctx = {"request": request}

    if not verify_password(current_password, user.password_hash):
        return _tpl("auth/change_password.html", {**ctx, "error": "Current password is incorrect"}, 400)
    if new_password != confirm_password:
        return _tpl("auth/change_password.html", {**ctx, "error": "New passwords do not match"}, 400)
    if len(new_password) < 10:
        return _tpl("auth/change_password.html", {**ctx, "error": "Password must be at least 10 characters"}, 400)

    user.password_hash = hash_password(new_password)
    user.force_password_change = False
    db.commit()
    return RedirectResponse("/", status_code=302)
