from datetime import datetime, timedelta, timezone

import jwt

ROL_USUARIO = "usuario"
ROL_ADMINISTRADOR = "administrador"

ALGORITMO = "HS256"


def emitir_token(usuario_id: int, rol: str, secreto: str, minutos_validez: int) -> str:
    ahora = datetime.now(timezone.utc)
    claims = {
        "sub": str(usuario_id),
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos_validez),
    }
    return jwt.encode(claims, secreto, algorithm=ALGORITMO)
