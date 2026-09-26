from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Path, Request, Response

from app.api.enlaces import enlaces_reserva, ruta_reserva
from app.api.esquemas import CancelacionReserva, ListaReservas, Reserva, ReservaNueva
from app.api.paginacion import ParametrosPagina, sobre_pagina
from app.auth.dependencias import IdentidadObligatoria
from app.auth.tokens import Identidad
from app.dominio import reservas as dominio_reservas
from app.espacios_gateway.cliente import Espacios
from app.persistencia.conexion import Conexion
from app.persistencia.reservas import ReservaGuardada

router = APIRouter(prefix="/v1/reservas", tags=["Reservas"])

ReservaId = Annotated[int, Path(ge=1)]


def a_respuesta(reserva: ReservaGuardada, quien_consulta: Identidad) -> Reserva:
    return Reserva(**asdict(reserva), enlaces=enlaces_reserva(reserva, quien_consulta))


@router.post("", status_code=201, response_model_exclude_none=True)
async def crear_reserva(
    datos: ReservaNueva,
    request: Request,
    response: Response,
    identidad: IdentidadObligatoria,
    espacios: Espacios,
) -> Reserva:
    franja = (datos.sala_id, datos.fecha, datos.hora_inicio, datos.hora_fin)
    reserva = await dominio_reservas.crear(
        request.app.state.pool, espacios, franja, datos.titular_id, identidad
    )
    response.headers["Location"] = ruta_reserva(reserva.id)
    return a_respuesta(reserva, identidad)


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
    # FastAPI lee como JSON `application/merge-patch+json` (RFC 7396); solo se valida.
    _cambio: CancelacionReserva,
    identidad: IdentidadObligatoria,
    conexion: Conexion,
) -> Reserva:
    return a_respuesta(await dominio_reservas.cancelar(conexion, reserva_id, identidad), identidad)
