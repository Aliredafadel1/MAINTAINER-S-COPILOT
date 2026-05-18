from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.domain.models import User
from app.infra import db
from app.repositories import widgets as widget_repo

router = APIRouter(prefix="/widgets")


class WidgetCreate(BaseModel):
    name: str
    allowed_origins: list[str] = []
    config: dict = {}


class WidgetOut(BaseModel):
    id: str
    name: str
    allowed_origins: list[str]
    config: dict
    is_active: bool


@router.post("", response_model=WidgetOut, status_code=201)
async def create_widget(
    req: WidgetCreate,
    session: AsyncSession = Depends(db.get_session),
    current_user: User = Depends(get_current_user),
):
    widget = await widget_repo.create(
        session,
        owner_id=current_user.id,
        name=req.name,
        allowed_origins=req.allowed_origins,
        config=req.config,
    )
    await session.commit()
    return WidgetOut(
        id=str(widget.id),
        name=widget.name,
        allowed_origins=widget.allowed_origins,
        config=widget.config,
        is_active=widget.is_active,
    )


@router.get("", response_model=list[WidgetOut])
async def list_widgets(
    session: AsyncSession = Depends(db.get_session),
    current_user: User = Depends(get_current_user),
):
    widgets = await widget_repo.list_for_owner(session, current_user.id)
    return [
        WidgetOut(
            id=str(w.id),
            name=w.name,
            allowed_origins=w.allowed_origins,
            config=w.config,
            is_active=w.is_active,
        )
        for w in widgets
    ]


@router.get("/{widget_id}/config")
async def widget_config(
    widget_id: UUID,
    response: Response,
    session: AsyncSession = Depends(db.get_session),
):
    """Public endpoint the embedded iframe calls to fetch its config.
    Sets CSP frame-ancestors based on the widget's allowed_origins."""
    widget = await widget_repo.get(session, widget_id)
    if widget is None or not widget.is_active:
        from app.domain.exceptions import NotFoundError

        raise NotFoundError("Widget not found")

    origins = widget.allowed_origins or ["'none'"]
    csp = "frame-ancestors " + " ".join(origins)
    response.headers["Content-Security-Policy"] = csp
    response.headers["Access-Control-Allow-Origin"] = origins[0] if origins else "*"

    return {"widget_id": str(widget.id), "config": widget.config}
