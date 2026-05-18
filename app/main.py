from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth as auth_router
from app.routers import inventory as inventory_router
from app.routers import work_orders as work_orders_router
from app.routers import reports as reports_router
from app.routers import admin as admin_router
from app.routers import audit as audit_router
from app.routers import analytics as analytics_router
from app.db import get_db

app = FastAPI(title=settings.app_title, version=settings.app_version, docs_url="/api/docs")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=settings.session_max_age,
    https_only=False,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(auth_router.router, tags=["auth"])
app.include_router(inventory_router.router)
app.include_router(work_orders_router.router)
app.include_router(reports_router.router)
app.include_router(admin_router.router)
app.include_router(audit_router.router)
app.include_router(analytics_router.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "version": settings.app_version}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db=Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    from app.models.user import User
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        return RedirectResponse("/login", status_code=302)
    if user.force_password_change:
        return RedirectResponse("/change-password", status_code=302)
    return templates.TemplateResponse(
        request=request, name="dashboard.html", context={"request": request, "user": user}
    )
