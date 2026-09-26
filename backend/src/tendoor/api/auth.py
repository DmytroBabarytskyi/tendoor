"""A4.1 Автентифікація. Access-токен — у тілі відповіді (зберігається в пам'яті клієнта),
refresh-токен — у httpOnly cookie, недоступному JavaScript."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from tendoor.api.deps import CurrentUser, client_ip, container
from tendoor.services.auth import AuthError, Session, TooManyAttempts
from tendoor.services.registration import RegistrationError

router = APIRouter(prefix="/auth", tags=["A4 Доступ"])

REFRESH_COOKIE = "tendoor_refresh"
COOKIE_PATH = "/api/auth"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class LoginIn(BaseModel):
    # без перевірки формату: вхід не має відмовляти через синтаксис адреси, лише через невірні дані
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(max_length=256)


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    role: Literal["auditor", "analyst"]
    password: str = Field(max_length=256)
    justification: str | None = Field(default=None, max_length=1000)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


def _respond(request: Request, response: Response, session: Session) -> TokenOut:
    c = container(request)
    response.set_cookie(
        REFRESH_COOKIE,
        session.refresh_token,
        max_age=c.tokens.refresh_ttl_seconds,
        httponly=True,
        secure=c.settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )
    return TokenOut(
        access_token=session.access_token,
        expires_in=c.tokens.access_ttl_seconds,
        user=UserOut.model_validate(session.user, from_attributes=True),
    )


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, response: Response):
    try:
        session = await container(request).auth.login(body.email, body.password, client_ip(request))
    except TooManyAttempts as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, str(exc), headers={"Retry-After": str(exc.retry_after)}
        ) from exc
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return _respond(request, response, session)


@router.post("/refresh", response_model=TokenOut)
async def refresh(request: Request, response: Response):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сесію не знайдено")
    try:
        session = await container(request).auth.refresh(token)
    except AuthError as exc:
        response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return _respond(request, response, session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(user: CurrentUser, request: Request, response: Response):
    await container(request).auth.logout(user, client_ip(request))
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.post("/change-password", response_model=TokenOut)
async def change_password(body: ChangePasswordIn, user: CurrentUser, request: Request, response: Response):
    try:
        session = await container(request).auth.change_password(user, body.old_password, body.new_password)
    except AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return _respond(request, response, session)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, request: Request) -> dict:
    """Заявка на доступ: увійти можна після погодження адміністратором."""
    try:
        r = await container(request).registrations.submit(
            str(body.email), body.full_name, body.role, body.password, body.justification
        )
    except RegistrationError as exc:
        code = status.HTTP_409_CONFLICT if exc.conflict else status.HTTP_422_UNPROCESSABLE_CONTENT
        raise HTTPException(code, str(exc)) from exc
    return {
        "id": r["id"],
        "status": r["status"],
        "message": "Заявку надіслано. Увійти можна після погодження.",
    }
