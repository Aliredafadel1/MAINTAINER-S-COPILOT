from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import AuthError, ConflictError
from app.infra import vault
from app.repositories import users as users_repo

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

TOKEN_EXPIRE_HOURS = 24
ALGORITHM = "HS256"


def _secret() -> str:
    return vault.get("JWT_SECRET")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def create_token(user_id: UUID, is_admin: bool) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "adm": is_admin, "exp": expire}
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except JWTError:
        raise AuthError("Invalid or expired token")


async def register(
    session: AsyncSession, email: str, password: str, is_admin: bool = False
):
    existing = await users_repo.get_by_email(session, email)
    if existing:
        raise ConflictError("Email already registered")
    # First user ever becomes admin automatically
    if not is_admin and await users_repo.count(session) == 0:
        is_admin = True
    hashed = hash_password(password)
    return await users_repo.create(
        session, email=email, hashed_password=hashed, is_admin=is_admin
    )


async def login(session: AsyncSession, email: str, password: str) -> str:
    user = await users_repo.get_by_email(session, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Invalid credentials")
    return create_token(user.id, user.is_admin)
