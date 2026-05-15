from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.routers.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def admin_index(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="stub.html",
        context={"request": request, "user": user, "section": "Admin", "phase": 10})
