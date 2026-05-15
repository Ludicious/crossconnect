from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.routers.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def reports_index(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="stub.html",
        context={"request": request, "user": user, "section": "Reports", "phase": 5})
