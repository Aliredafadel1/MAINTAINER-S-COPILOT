from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.domain.models import User
from app.infra import db
from app.services import auth as auth_svc

router = APIRouter(prefix="/auth")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    req: RegisterRequest, session: AsyncSession = Depends(db.get_session)
):
    user = await auth_svc.register(session, req.email, req.password)
    await session.commit()
    token = auth_svc.create_token(user.id, user.is_admin)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, session: AsyncSession = Depends(db.get_session)):
    token = await auth_svc.login(session, req.email, req.password)
    return TokenResponse(access_token=token)


@router.post("/invite", response_model=TokenResponse, status_code=201)
async def invite(
    req: RegisterRequest,
    session: AsyncSession = Depends(db.get_session),
    _admin: User = Depends(require_admin),
):
    """Admin-only: create a new user account and return their token."""
    user = await auth_svc.register(session, req.email, req.password)
    await session.commit()
    token = auth_svc.create_token(user.id, user.is_admin)
    return TokenResponse(access_token=token)
