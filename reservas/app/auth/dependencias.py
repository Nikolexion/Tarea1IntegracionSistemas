from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.tokens import ROL_ADMINISTRADOR, Identidad, TokenInvalido, validar_token
from app.dominio.errores import SinPermiso

esquema_bearer = HTTPBearer(auto_error=False)


class SinToken(Exception):
    """La petición no trae header Authorization."""


async def identidad_opcional(
    request: Request,
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
) -> Identidad | None:
    if credenciales is None:
        if "authorization" in request.headers:
            raise TokenInvalido("el header Authorization no es Bearer")
        return None
    return validar_token(credenciales.credentials, request.app.state.configuracion.jwt_secreto)


async def identidad_obligatoria(
    identidad: Identidad | None = Depends(identidad_opcional),
) -> Identidad:
    if identidad is None:
        raise SinToken()
    return identidad


async def exigir_administrador(
    identidad: Identidad = Depends(identidad_obligatoria),
) -> Identidad:
    if identidad.rol != ROL_ADMINISTRADOR:
        raise SinPermiso("Esta operación requiere rol administrador.")
    return identidad


IdentidadOpcional = Annotated[Identidad | None, Depends(identidad_opcional)]
IdentidadObligatoria = Annotated[Identidad, Depends(identidad_obligatoria)]
Administrador = Annotated[Identidad, Depends(exigir_administrador)]
