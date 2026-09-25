"""Спільні залежності API: контейнер, поточний користувач, перевірка ролей (RBAC)."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tendoor.infra.security import TokenError
from tendoor.repositories.base import UserData

_bearer = HTTPBearer(auto_error=False)


def container(request: Request):
    return request.app.state.container


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def current_user(
    request: Request, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> UserData:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Потрібна автентифікація", headers={"WWW-Authenticate": "Bearer"}
    )
    if creds is None:
        raise unauthorized
    c = container(request)
    try:
        claims = c.tokens.decode(creds.credentials, "access")
    except TokenError as exc:
        unauthorized.detail = str(exc).capitalize()
        raise unauthorized from exc
    user = await c.users.get(claims.user_id)
    # роль і блокування перевіряються за БД, а не лише за токеном — зміни діють одразу
    if user is None or not user.is_active or user.token_version != claims.token_version:
        raise unauthorized
    return user


CurrentUser = Annotated[UserData, Depends(current_user)]


def require_roles(*roles: str):
    async def _check(user: CurrentUser) -> UserData:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостатньо прав для цієї дії")
        return user

    return _check


AdminUser = Annotated[UserData, Depends(require_roles("admin"))]
AnalystUser = Annotated[UserData, Depends(require_roles("admin", "analyst"))]
