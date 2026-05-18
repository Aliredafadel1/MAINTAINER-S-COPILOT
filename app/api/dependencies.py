from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import AuthError, ForbiddenError
from app.domain.models import User
from app.infra import db
from app.repositories import users as users_repo
from app.services.auth import decode_token


async def get_current_user(
    authorization: str = Header(...),
    session: AsyncSession = Depends(db.get_session),
) -> User:
    if not authorization.startswith("Bearer "):
        raise AuthError("Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    payload = decode_token(token)
    user_id = UUID(payload["sub"])
    user = await users_repo.get_by_id(session, user_id)
    if user is None:
        raise AuthError("User not found")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise ForbiddenError("Admin access required")
    return current_user
