"""A4.2–A4.4: користувачі й ролі, параметри аналізу, журнал аудиту."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from tendoor.api.auth import UserOut
from tendoor.api.deps import AdminUser, CurrentUser, container
from tendoor.services.users import UserError

router = APIRouter(tags=["A4 Адміністрування"])


class UserCreateIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    role: str
    password: str


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class RoleOut(BaseModel):
    code: str
    name: str


class ConfigOut(BaseModel):
    key: str
    value: dict[str, Any]
    description: str | None
    updated_by: int | None
    updated_at: datetime


class ConfigIn(BaseModel):
    value: dict[str, Any]


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    user_email: str | None
    action: str
    entity: str
    entity_key: str | None
    payload: dict[str, Any] | None
    ip: str | None
    created_at: datetime


class AuditPage(BaseModel):
    total: int
    items: list[AuditOut]


def _user_error(exc: UserError) -> HTTPException:
    code = status.HTTP_409_CONFLICT if exc.conflict else status.HTTP_400_BAD_REQUEST
    return HTTPException(code, str(exc))


# ---------------------------------------------------------------- A4.2 користувачі


@router.get("/roles", response_model=list[RoleOut])
async def roles(_: CurrentUser, request: Request):
    return [RoleOut(code=c, name=n) for c, n in await container(request).users.roles()]


@router.get("/users", response_model=list[UserOut])
async def list_users(_: AdminUser, request: Request):
    return await container(request).users.list_all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreateIn, admin: AdminUser, request: Request):
    try:
        return await container(request).user_service.create(
            admin, body.email, body.full_name, body.role, body.password
        )
    except UserError as exc:
        raise _user_error(exc) from exc


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, body: UserUpdateIn, admin: AdminUser, request: Request):
    try:
        user = await container(request).user_service.update(
            admin, user_id, **body.model_dump(exclude_none=True)
        )
    except UserError as exc:
        raise _user_error(exc) from exc
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Користувача не знайдено")
    return user


# ---------------------------------------------------------------- A4.3 параметри аналізу


@router.get("/settings", response_model=list[ConfigOut])
async def list_settings(_: CurrentUser, request: Request):
    return await container(request).config.list_all()


@router.put("/settings/{key}", response_model=ConfigOut)
async def update_setting(key: str, body: ConfigIn, admin: AdminUser, request: Request):
    cfg = await container(request).config.set(admin.id, key, body.value)
    if cfg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Параметр не знайдено")
    return cfg


# ---------------------------------------------------------------- A4.4 журнал аудиту


@router.get("/audit-log", response_model=AuditPage)
async def audit_log(
    _: AdminUser,
    request: Request,
    entity: str | None = None,
    user_id: int | None = None,
    action: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    items, total = await container(request).audit.search(
        entity, user_id, action, min(limit, 200), max(offset, 0)
    )
    return AuditPage(total=total, items=items)
