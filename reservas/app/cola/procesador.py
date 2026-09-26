"""Tarea en segundo plano que procesa la cola de liberaciones pendientes"""

import asyncio
import logging

from psycopg_pool import AsyncConnectionPool

from app.cache.disponibilidad import CacheDisponibilidad
from app.espacios_gateway.cliente import ClienteEspacios, EspaciosNoDisponible
from app.persistencia import reservas

logger = logging.getLogger(__name__)

INTERVALO_SEGUNDOS = 5
MAXIMO_POR_CICLO = 50
LARGO_MAXIMO_ERROR = 200


async def procesar_cola(
    pool: AsyncConnectionPool, espacios: ClienteEspacios, cache: CacheDisponibilidad
) -> None:
    """Procesa un ciclo cada INTERVALO_SEGUNDOS hasta que se cancela al detener la app"""
    while True:
        await asyncio.sleep(INTERVALO_SEGUNDOS)
        try:
            await procesar_ciclo(pool, espacios, cache)
        except Exception:
            # P. ej. la base de Reservas caída: se reintenta en el próximo ciclo
            logger.exception("Falló un ciclo de la cola de liberaciones")


async def procesar_ciclo(
    pool: AsyncConnectionPool, espacios: ClienteEspacios, cache: CacheDisponibilidad
) -> None:
    """Intenta liberar hasta MAXIMO_POR_CICLO pendientes, de la más antigua a la más nueva."""
    # Cada acceso a la base usa una transacción corta: la llamada a Espacios se hace sin
    # conexión tomada
    async with pool.connection() as conexion:
        pendientes = await reservas.leer_liberaciones_pendientes(conexion, MAXIMO_POR_CICLO)

    for pendiente in pendientes:
        try:
            respuesta = await espacios.liberar_puesto(str(pendiente.referencia))
        except Exception as error:
            descripcion = f"{type(error).__name__}: {error}"[:LARGO_MAXIMO_ERROR]
            async with pool.connection() as conexion:
                await reservas.registrar_fallo_liberacion(conexion, pendiente.id, descripcion)
            logger.warning(
                "No se pudo liberar %s (intento %d): %s",
                pendiente.referencia, pendiente.intentos + 1, descripcion,
            )
            if isinstance(error, EspaciosNoDisponible):
                # Si Espacios no está disponible para esta fila, tampoco lo estará para las
                # siguientes: se corta el ciclo y se reintenta todo en el próximo
                break
            continue

        # Cualquier resultado cuenta como éxito: LiberarPuesto es idempotente
        async with pool.connection() as conexion:
            await reservas.borrar_liberacion(conexion, pendiente.id)
        logger.info("Liberación de %s procesada (resultado %d)", pendiente.referencia,
                    respuesta.resultado)
        # La grilla de esa fecha ya no refleja el puesto liberado
        await cache.invalidar(pendiente.fecha)
