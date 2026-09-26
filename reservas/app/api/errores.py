"""Todas las respuestas de error como Problem Details, `application/problem+json` (RFC 9457)"""

import logging
from http import HTTPStatus
from typing import Any, NamedTuple

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.dependencias import SinToken
from app.auth.tokens import TokenInvalido
from app.dominio.errores import (
    CredencialesInvalidas,
    DatosInvalidos,
    EmailYaRegistrado,
    IdempotenciaEnCurso,
    IdempotenciaReutilizada,
    NoEncontrado,
    SinPermiso,
    SinPuestos,
)
from app.espacios_gateway.cliente import (
    DatosRechazados,
    EspaciosNoDisponible,
    EspaciosSinRespuesta,
    ErrorInesperadoEspacios,
    SalaNoEncontrada,
)

logger = logging.getLogger(__name__)


# Tabla de problemas propios

class Problema(NamedTuple):
    status: int
    tipo: str  # se publica como `type: /problemas/<tipo>`
    titulo: str
    detalle: str | None = None  # None: se usa el mensaje de la excepción
    headers: dict[str, str] | None = None


# Toda respuesta 401 indica el esquema esperado (RFC 6750); con token inválido, además el error
BEARER = {"WWW-Authenticate": "Bearer"}
BEARER_INVALIDO = {"WWW-Authenticate": 'Bearer error="invalid_token"'}
REINTENTAR = {"Retry-After": "5"}  # segundos sugeridos antes de reintentar un 503

PROBLEMAS: dict[type[Exception], Problema] = {
    SinToken: Problema(
        401, "no-autenticado", "No autenticado",
        "Esta operación requiere un token de acceso (header Authorization: Bearer).", BEARER,
    ),
    TokenInvalido: Problema(
        401, "no-autenticado", "No autenticado",
        "El token de acceso no es válido o expiró.", BEARER_INVALIDO,
    ),
    # Mismo mensaje exista o no el email, para no revelar qué cuentas hay.
    CredencialesInvalidas: Problema(
        401, "credenciales-invalidas", "Credenciales inválidas",
        "El email o la contraseña no son correctos.", BEARER,
    ),
    SinPermiso: Problema(403, "sin-permiso", "Sin permiso"),
    NoEncontrado: Problema(404, "no-encontrado", "Recurso no encontrado"),
    SalaNoEncontrada: Problema(404, "no-encontrado", "Recurso no encontrado", "La sala no existe."),
    EmailYaRegistrado: Problema(
        409, "email-registrado", "Email ya registrado", "Ya existe una cuenta con ese email."
    ),
    SinPuestos: Problema(
        409, "sin-puestos", "Sin puestos disponibles",
        "La sala no tiene puestos libres en esa franja.",
    ),
    IdempotenciaEnCurso: Problema(
        409, "idempotencia-en-curso", "Petición en curso",
        "Otra petición con la misma Idempotency-Key todavía se está procesando.",
    ),
    DatosInvalidos: Problema(422, "datos-invalidos", "Datos inválidos"),
    IdempotenciaReutilizada: Problema(
        422, "idempotencia-reutilizada", "Idempotency-Key reutilizada",
        "La Idempotency-Key ya se usó con un cuerpo distinto.",
    ),
    DatosRechazados: Problema(422, "datos-invalidos", "Datos inválidos"),  # mensaje de Espacios
    EspaciosNoDisponible: Problema(
        503, "espacios-no-disponible", "Servicio de espacios no disponible",
        "El servicio de espacios no está disponible y no se realizó la operación. "
        "Intente nuevamente en unos segundos.", REINTENTAR,
    ),
    EspaciosSinRespuesta: Problema(
        504, "espacios-sin-respuesta", "Servicio de espacios sin respuesta",
        "El servicio de espacios no respondió a tiempo; el resultado de la operación es incierto.",
    ),
    # Pool de conexiones agotado.
    PoolTimeout: Problema(
        503, "servicio-saturado", "Servicio saturado",
        "El servicio está atendiendo demasiadas peticiones. Intente nuevamente en unos segundos.",
        REINTENTAR,
    ),
}


def respuesta_problema(
    request: Request,
    status: int,
    tipo: str,
    titulo: str,
    detalle: str | None = None,
    headers: dict[str, str] | None = None,
    **extensiones: Any,
) -> JSONResponse:
    cuerpo: dict[str, Any] = {"type": tipo, "title": titulo, "status": status}
    if detalle:
        cuerpo["detail"] = detalle
    cuerpo["instance"] = request.url.path
    cuerpo.update(extensiones)
    return JSONResponse(
        cuerpo, status_code=status, headers=headers, media_type="application/problem+json"
    )


def _frase_estandar(status: int) -> str:
    """Título de los errores `about:blank`: la frase del código ("Not Found" para 404)."""
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Error"



async def manejar_problema(request: Request, exc: Exception) -> JSONResponse:
    problema = PROBLEMAS[type(exc)]
    return respuesta_problema(
        request, problema.status, f"/problemas/{problema.tipo}", problema.titulo,
        problema.detalle or str(exc), problema.headers,
    )


async def manejar_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """404 de ruta, 405, etc.: sin significado propio, así que `about:blank` (RFC 9457)."""
    titulo = _frase_estandar(exc.status_code)
    detalle = exc.detail if exc.detail != titulo else None
    # Se conservan los headers que exige el código (p. ej. Allow en un 405)
    return respuesta_problema(request, exc.status_code, "about:blank", titulo, detalle, exc.headers)


async def manejar_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    errores = exc.errors()
    # FastAPI informa el JSON ilegible como un error de validación más, pero es 400
    if any(error["type"] == "json_invalid" for error in errores):
        return respuesta_problema(
            request, 400, "/problemas/json-mal-formado", "JSON mal formado",
            "El cuerpo de la petición no es JSON válido.",
        )
    return respuesta_problema(
        request, 422, "/problemas/datos-invalidos", "Datos inválidos",
        "Uno o más campos no cumplen el formato esperado.",
        errores=[
            {"campo": _nombre_campo(error["loc"]), "mensaje": error["msg"]} for error in errores
        ],
    )


def _nombre_campo(ubicacion: tuple[Any, ...]) -> str:
    """("body", "fecha") → "fecha"; si solo está el origen (cuerpo ausente), se conserva."""
    return ".".join(str(parte) for parte in ubicacion[1:] or ubicacion)


async def manejar_no_controlado(request: Request, exc: Exception) -> JSONResponse:
    # El detalle queda solo en el log: enviarlo al cliente filtraría información interna
    logger.error("Error no controlado en %s %s", request.method, request.url.path, exc_info=exc)
    return respuesta_problema(
        request, 500, "about:blank", _frase_estandar(500),
        "Ocurrió un error inesperado. Intente nuevamente más tarde.",
    )


def registrar_manejadores(app: FastAPI) -> None:
    for excepcion in PROBLEMAS:
        app.add_exception_handler(excepcion, manejar_problema)
    app.add_exception_handler(StarletteHTTPException, manejar_http)
    app.add_exception_handler(RequestValidationError, manejar_validacion)
    app.add_exception_handler(ErrorInesperadoEspacios, manejar_no_controlado)
    app.add_exception_handler(Exception, manejar_no_controlado)
