from uuid import UUID

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
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


@router.get("/{widget_id}/embed", response_class=HTMLResponse)
async def embed_widget(
    widget_id: UUID,
    widget_src: str = "http://localhost:8080",
    api_url: str = "http://localhost:8000",
    session: AsyncSession = Depends(db.get_session),
):
    """Serves the iframe page with CSP frame-ancestors from the widget's allowed_origins.
    The loader script (widget.js) points its iframe here so the browser enforces origin allowlisting."""
    widget = await widget_repo.get(session, widget_id)
    if widget is None or not widget.is_active:
        from app.domain.exceptions import NotFoundError

        raise NotFoundError("Widget not found")

    origins = widget.allowed_origins or []
    frame_ancestors = " ".join(origins) if origins else "'none'"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{ background: transparent; overflow: hidden; width: 100%; height: 100%; }}
  </style>
</head>
<body>
  <script
    src="/static/widget.iife.js"
    data-widget-id="{widget_id}"
    data-api-url="{api_url}"
  ></script>
</body>
</html>"""

    headers = {
        "Content-Security-Policy": f"frame-ancestors {frame_ancestors}",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return HTMLResponse(content=html_content, headers=headers)
