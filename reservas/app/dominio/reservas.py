import logging
from datetime import date
from uuid import UUID, uuid4

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.auth.tokens import ROL_ADMINISTRADOR, Identidad
from app.dominio.errores import DatosInvalidos, NoEncontrado, SinPermiso, SinPuestos
from app.espacios_gateway.cliente import (
    ClienteEspacios,
    EspaciosSinRespuesta,
    ErrorInesperadoEspacios,
    SalaNoEncontrada,
)
from app.generado import espacios_pb2 as pb
from app.persistencia import reservas, usuarios
from app.persistencia.reservas import ReservaGuardada

logger = logging.getLogger(__name__)

Franja = tuple[int, date, str, str]  # sala_id, fecha, hora_inicio, hora_fin


# Crear


async def crear(
    pool: AsyncConnectionPool,
    espacios: ClienteEspacios,
    franja: Franja,
    titular_id: int | None,
    quien_llama: Identidad,
) -> ReservaGuardada:
    sala_id, fecha, hora_inicio, hora_fin = franja
    titular_id = await _titular_efectivo(pool, titular_id, quien_llama)
    referencia = uuid4()

    try:
        respuesta = await espacios.ocupar_puesto(
            sala_id, fecha.isoformat(), hora_inicio, hora_fin, str(referencia)
        )
    except SalaNoEncontrada:
        raise DatosInvalidos(f"No existe una sala con id {sala_id} (sala_id).") from None
    except EspaciosSinRespuesta:
        await _encolar_liberacion(pool, referencia, franja)
        raise

    if respuesta.resultado == pb.RESULTADO_OCUPACION_SIN_PUESTOS:
        raise SinPuestos()
    if respuesta.resultado != pb.RESULTADO_OCUPACION_OCUPADO:
        raise ErrorInesperadoEspacios(f"OcuparPuesto devolvió el resultado {respuesta.resultado}")

    try:
        async with pool.connection() as conexion:
            return await reservas.insertar(
                conexion, referencia, sala_id, respuesta.sala_nombre, fecha, hora_inicio,
                hora_fin, titular_id, quien_llama.usuario_id,
            )
    except Exception:
        logger.exception("Se ocupó el puesto %s pero no se pudo guardar la reserva", referencia)
        await _compensar(pool, espacios, referencia, franja)
        raise 


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
        logger.exception("No se pudo encolar la liberación de %s: liberarla a mano", referencia)


# Consultar

async def obtener(
    conexion: AsyncConnection, reserva_id: int, quien_llama: Identidad
) -> ReservaGuardada:
    reserva = await reservas.obtener_por_id(conexion, reserva_id)
    es_visible = reserva is not None and (
        reserva.titular_id == quien_llama.usuario_id or quien_llama.rol == ROL_ADMINISTRADOR
    )
    if not es_visible:
        raise NoEncontrado(f"No existe una reserva con id {reserva_id}.")
    return reserva


async def listar(
    conexion: AsyncConnection, quien_llama: Identidad, limit: int, offset: int
) -> tuple[list[ReservaGuardada], int]:
    titular_id = None if quien_llama.rol == ROL_ADMINISTRADOR else quien_llama.usuario_id
    return await reservas.listar(conexion, titular_id, limit, offset)
