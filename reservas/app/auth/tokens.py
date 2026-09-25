from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

ROL_USUARIO = "usuario"
ROL_ADMINISTRADOR = "administrador"

ALGORITMO = "HS256"

@dataclass(frozen=True)
class Identidad:

    usuario_id: int
    rol: str


class TokenInvalido(Exception):
    """El token está mal formado, fue manipulado, expiró o no trae los claims esperados."""

def emitir_token(usuario_id: int, rol: str, secreto: str, minutos_validez: int) -> str:
    ahora = datetime.now(timezone.utc)
    claims = {
        "sub": str(usuario_id),
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos_validez),
    }
    return jwt.encode(claims, secreto, algorithm=ALGORITMO)

def validar_token(token: str, secreto: str) -> Identidad:
    try:
        claims = jwt.decode(
            token, secreto, algorithms=[ALGORITMO],
            options={"require": ["sub", "rol", "iat", "exp"]},
        )
    except jwt.InvalidTokenError as error:
        raise TokenInvalido(str(error)) from error

    sub, rol = claims["sub"], claims["rol"]
    if not isinstance(sub, str) or not sub.isdigit() or rol not in (ROL_USUARIO, ROL_ADMINISTRADOR):
        raise TokenInvalido("claims sub o rol no válidos")
    return Identidad(usuario_id=int(sub), rol=rol)
