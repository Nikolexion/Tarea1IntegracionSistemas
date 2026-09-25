import logging
from http import HTTPStatus
from typing import Any, NamedTuple

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class Problema(NamedTuple):
    status: int
    tipo: str 
    titulo: str
    detalle: str | None = None 
    headers: dict[str, str] | None = None


PROBLEMAS: dict[type[Exception], Problema] = {}


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
    return respuesta_problema(request, exc.status_code, "about:blank", titulo, detalle, exc.headers)


async def manejar_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    errores = exc.errors()
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
    app.add_exception_handler(Exception, manejar_no_controlado)
