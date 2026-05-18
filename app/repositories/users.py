from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import User


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def create(
    session: AsyncSession, email: str, hashed_password: str, is_admin: bool = False
) -> User:
    user = User(email=email, hashed_password=hashed_password, is_admin=is_admin)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def count(session: AsyncSession) -> int:
    from sqlalchemy import func

    result = await session.execute(select(func.count()).select_from(User))
    return result.scalar_one()
