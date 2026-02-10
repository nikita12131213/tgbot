from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.db import SessionLocal, init_db
from app.repository import dashboard_stats, list_rooms, moderate_user, room_with_messages

app = FastAPI(title="Anonymous Chat Admin")
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()


def auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    if credentials.username != settings.admin_username or credentials.password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Basic"})
    return credentials.username


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request, _: str = Depends(auth)):
    with SessionLocal() as session:
        stats = dashboard_stats(session)
        rooms = list_rooms(session)
    return templates.TemplateResponse("index.html", {"request": request, "stats": stats, "rooms": rooms})


@app.get("/rooms/{room_id}", response_class=HTMLResponse)
def room_view(room_id: int, request: Request, _: str = Depends(auth)):
    with SessionLocal() as session:
        room = room_with_messages(session, room_id)
        if not room:
            raise HTTPException(404, "Room not found")
        messages = sorted(room.messages, key=lambda m: m.created_at)
        members = [m.user_hash for m in room.members]
    return templates.TemplateResponse(
        "room.html",
        {"request": request, "room": room, "messages": messages, "members": members},
    )


@app.post("/ban")
def ban(user_hash: str = Form(...), _: str = Depends(auth)):
    with SessionLocal() as session:
        moderate_user(session, user_hash=user_hash, banned=True)
        session.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/unban")
def unban(user_hash: str = Form(...), _: str = Depends(auth)):
    with SessionLocal() as session:
        moderate_user(session, user_hash=user_hash, banned=False)
        session.commit()
    return RedirectResponse(url="/", status_code=303)
