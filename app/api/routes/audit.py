from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.domain.models import User
from app.infra import db
from app.repositories import audit as audit_repo

router = APIRouter(prefix="/audit")


class AuditOut(BaseModel):
    id: str
    action: str
    resource_type: str | None
    resource_id: str | None
    details: dict
    created_at: str


@router.get("", response_model=list[AuditOut])
async def list_audit(
    session: AsyncSession = Depends(db.get_session),
    _admin: User = Depends(require_admin),
):
    entries = await audit_repo.list_recent(session, limit=200)
    return [
        AuditOut(
            id=str(e.id),
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            details=e.details,
            created_at=e.created_at.isoformat(),
        )
        for e in entries
    ]
