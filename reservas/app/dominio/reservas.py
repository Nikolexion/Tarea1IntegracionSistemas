"""Reglas de las reservas: crear con compensación, ver, listar y cancelar"""

import logging
from collections.abc import Awaitable, Callable
from datetime import date
from uuid import UUID, uuid4

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.auth.tokens import ROL_ADMINISTRADOR, Identidad
from app.cache.disponibilidad import CacheDisponibilidad
from app.dominio.errores import DatosInvalidos, NoEncontrado, SinPermiso, SinPuestos
from app.espacios_gateway.cliente import (
    ClienteEspacios,
    EspaciosSinRespuesta,
    ErrorInesperadoEspacios,
    SalaNoEncontrada,
)
from app.generado import espacios_pb2 as pb
from app.persistencia import reservas, usuarios
from app.persistencia.reservas import ESTADO_ACTIVA, ReservaGuardada

logger = logging.getLogger(__name__)

Franja = tuple[int, date, str, str]  # sala_id, fecha, hora_inicio, hora_fin
AlGuardar = Callable[[AsyncConnection, ReservaGuardada], Awaitable[None]]



# Recibe el pool y no una conexión: la llamada a Espacios se hace sin conexión tomada y cada escritura usa su propia transacción corta
async def crear(
    pool: AsyncConnectionPool,
    espacios: ClienteEspacios,
    cache: CacheDisponibilidad,
    franja: Franja,
    titular_id: int | None,
    quien_llama: Identidad,
    al_guardar: AlGuardar | None = None,
) -> ReservaGuardada:
    """`al_guardar` corre en la transacción que inserta la reserva"""
    sala_id, fecha, hora_inicio, hora_fin = franja
    titular_id = await _titular_efectivo(pool, titular_id, quien_llama)
    # Se genera antes de guardar: sirve para compensar aunque la reserva nunca se guarde
    referencia = uuid4()

    try:
        respuesta = await espacios.ocupar_puesto(
            sala_id, fecha.isoformat(), hora_inicio, hora_fin, str(referencia)
        )
    except SalaNoEncontrada:
        # La sala viene en el cuerpo, no en la URL: 422 y no 404
        raise DatosInvalidos(f"No existe una sala con id {sala_id} (sala_id).") from None
    except EspaciosSinRespuesta:
        # Resultado incierto: se encola la liberación y se responde 504 aunque el encolado falle
        await _encolar_liberacion(pool, referencia, franja)
        raise

    if respuesta.resultado == pb.RESULTADO_OCUPACION_SIN_PUESTOS:
        raise SinPuestos()
    if respuesta.resultado != pb.RESULTADO_OCUPACION_OCUPADO:
        # 500 sin compensar
        raise ErrorInesperadoEspacios(f"OcuparPuesto devolvió el resultado {respuesta.resultado}")
    # Espacios ocupó un puesto: la grilla guardada de esa fecha quedó vieja
    await cache.invalidar(fecha)

    try:
        async with pool.connection() as conexion:
            reserva = await reservas.insertar(
                conexion, referencia, sala_id, respuesta.sala_nombre, fecha, hora_inicio,
                hora_fin, titular_id, quien_llama.usuario_id,
            )
            if al_guardar is not None:
                await al_guardar(conexion, reserva)
            return reserva
    except Exception:
        logger.exception("Se ocupó el puesto %s pero no se pudo guardar la reserva", referencia)
        await _compensar(pool, espacios, referencia, franja)
        raise  # el manejador global responde 500


async def _titular_efectivo(
    pool: AsyncConnectionPool, titular_id: int | None, quien_llama: Identidad
) -> int:
    """Por defecto, quien reserva; solo un administrador puede indicar a otro usuario."""
    if titular_id is None or titular_id == quien_llama.usuario_id:
        return quien_llama.usuario_id
    if quien_llama.rol != ROL_ADMINISTRADOR:
        raise SinPermiso("Solo un administrador puede reservar a nombre de otro usuario.")
    async with pool.connection() as conexion:
        if await usuarios.obtener_por_id(conexion, titular_id) is None:
            raise DatosInvalidos(f"No existe un usuario con id {titular_id} (titular_id).")
    return titular_id


async def _compensar(
    pool: AsyncConnectionPool, espacios: ClienteEspacios, referencia: UUID, franja: Franja
) -> None:
    """Libera directo en Espacios y, si falla, encola la liberación (ADR-010 punto 4). No lanza."""
    try:
        await espacios.liberar_puesto(str(referencia))
        logger.info("Compensación: puesto %s liberado directo en Espacios", referencia)
    except Exception:
        logger.exception("Compensación: no se pudo liberar directo %s; se encola", referencia)
        await _encolar_liberacion(pool, referencia, franja)


async def _encolar_liberacion(pool: AsyncConnectionPool, referencia: UUID, franja: Franja) -> None:
    """Encola en una transacción propia. No lanza: si falla, se registra para liberar a mano."""
    try:
        async with pool.connection() as conexion:
            await reservas.encolar_liberacion(conexion, referencia, *franja)
    except Exception:
        # Riesgo residual aceptado en ADR-010: el puesto puede quedar ocupado sin reserva
        logger.exception("No se pudo encolar la liberación de %s: liberarla a mano", referencia)



async def obtener(
    conexion: AsyncConnection, reserva_id: int, quien_llama: Identidad, bloquear: bool = False
) -> ReservaGuardada:
    """La reserva si es del titular o llama un administrador; ajena → no encontrada (ADR-007)."""
    reserva = await reservas.obtener_por_id(conexion, reserva_id, bloquear)
    es_visible = reserva is not None and (
        reserva.titular_id == quien_llama.usuario_id or quien_llama.rol == ROL_ADMINISTRADOR
    )
    if not es_visible:
        raise NoEncontrado(f"No existe una reserva con id {reserva_id}.")
    return reserva


async def listar(
    conexion: AsyncConnection, quien_llama: Identidad, limit: int, offset: int
) -> tuple[list[ReservaGuardada], int]:
    """Un usuario ve solo las suyas (como titular); un administrador, todas."""
    titular_id = None if quien_llama.rol == ROL_ADMINISTRADOR else quien_llama.usuario_id
    return await reservas.listar(conexion, titular_id, limit, offset)



async def cancelar(
    conexion: AsyncConnection, reserva_id: int, quien_llama: Identidad
) -> ReservaGuardada:
    """Marca CANCELADA y encola la liberación en la misma transacción, sin llamar a Espacios
    (ADR-010 punto 5). Si ya estaba cancelada no hace nada (idempotente)."""
    reserva = await obtener(conexion, reserva_id, quien_llama, bloquear=True)
    if reserva.estado != ESTADO_ACTIVA:
        return reserva
    cancelada = await reservas.cancelar(conexion, reserva_id)
    await reservas.encolar_liberacion(
        conexion, reserva.referencia, reserva.sala_id, reserva.fecha,
        reserva.hora_inicio, reserva.hora_fin,
    )
    return cancelada
