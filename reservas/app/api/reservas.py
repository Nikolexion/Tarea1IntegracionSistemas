"""Reservas: `/v1/reservas`."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Header, Path, Request, Response

from app.api.enlaces import enlaces_reserva, ruta_reserva
from app.api.esquemas import CancelacionReserva, ListaReservas, Reserva, ReservaNueva
from app.api.paginacion import ParametrosPagina, sobre_pagina
from app.auth.dependencias import IdentidadObligatoria
from app.auth.tokens import Identidad
from app.cache.disponibilidad import Cache
from app.dominio import idempotencia
from app.dominio import reservas as dominio_reservas
from app.espacios_gateway.cliente import Espacios
from app.persistencia.conexion import Conexion
from app.persistencia.reservas import ReservaGuardada

router = APIRouter(prefix="/v1/reservas", tags=["Reservas"])

ReservaId = Annotated[int, Path(ge=1)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=255)]


def a_respuesta(reserva: ReservaGuardada, quien_consulta: Identidad) -> Reserva:
    # `Reserva` no declara `referencia` (detalle interno de la integración), así que se descarta
    return Reserva(**asdict(reserva), enlaces=enlaces_reserva(reserva, quien_consulta))


# Sin la dependencia `Conexion`: el dominio no retiene una conexión mientras espera a Espacios
@router.post("", status_code=201, response_model_exclude_none=True)
async def crear_reserva(
    datos: ReservaNueva,
    request: Request,
    response: Response,
    identidad: IdentidadObligatoria,
    espacios: Espacios,
    cache: Cache,
    idempotency_key: IdempotencyKey = None,
) -> Reserva:
    pool = request.app.state.pool
    franja = (datos.sala_id, datos.fecha, datos.hora_inicio, datos.hora_fin)
    if idempotency_key is None:
        reserva = await dominio_reservas.crear(
            pool, espacios, cache, franja, datos.titular_id, identidad
        )
        response.headers["Location"] = ruta_reserva(reserva.id)
        return a_respuesta(reserva, identidad)

    hash_cuerpo = idempotencia.hash_cuerpo(datos)
    clave = idempotencia.Clave(identidad.usuario_id, idempotency_key, hash_cuerpo)
    cuerpo = await idempotencia.registrar(pool, clave)
    if cuerpo is None:  # primera vez (o clave abandonada): se reserva de verdad
        cuerpo = await _crear_y_completar(
            pool, espacios, cache, franja, datos.titular_id, identidad, clave
        )
    # Original y repetida salen del mismo cuerpo guardado, así que son idénticas
    response.headers["Location"] = ruta_reserva(cuerpo["id"])
    return Reserva.model_validate(cuerpo)


async def _crear_y_completar(
    pool, espacios, cache, franja, titular_id, identidad, clave
) -> dict:
    """Crea la reserva guardando su cuerpo en la clave; ante cualquier error borra la clave"""
    guardado: dict = {}

    async def completar(conexion, reserva: ReservaGuardada) -> None:
        respuesta = a_respuesta(reserva, identidad)
        guardado.update(respuesta.model_dump(mode="json", by_alias=True, exclude_none=True))
        await idempotencia.completar(conexion, clave, guardado)

    try:
        await dominio_reservas.crear(
            pool, espacios, cache, franja, titular_id, identidad, completar
        )
    except Exception:
        await idempotencia.descartar(pool, clave)
        raise
    return guardado


@router.get("", response_model_exclude_none=True)
async def listar_reservas(
    request: Request, identidad: IdentidadObligatoria, pagina: ParametrosPagina, conexion: Conexion
) -> ListaReservas:
    filas, total = await dominio_reservas.listar(conexion, identidad, pagina.limit, pagina.offset)
    items = [a_respuesta(fila, identidad) for fila in filas]
    return ListaReservas(**sobre_pagina(items, total, pagina, request.url.path))


@router.get("/{reserva_id}", response_model_exclude_none=True)
async def obtener_reserva(
    reserva_id: ReservaId, identidad: IdentidadObligatoria, conexion: Conexion
) -> Reserva:
    return a_respuesta(await dominio_reservas.obtener(conexion, reserva_id, identidad), identidad)


@router.patch("/{reserva_id}", response_model_exclude_none=True)
async def cancelar_reserva(
    reserva_id: ReservaId,
    # FastAPI lee como JSON `application/merge-patch+json` (RFC 7396); solo se valida
    _cambio: CancelacionReserva,
    identidad: IdentidadObligatoria,
    conexion: Conexion,
) -> Reserva:
    return a_respuesta(await dominio_reservas.cancelar(conexion, reserva_id, identidad), identidad)
