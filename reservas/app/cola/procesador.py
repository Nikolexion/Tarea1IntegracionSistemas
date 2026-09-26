import asyncio
import logging

from psycopg_pool import AsyncConnectionPool

from app.espacios_gateway.cliente import ClienteEspacios
from app.persistencia import reservas

logger = logging.getLogger(__name__)

INTERVALO_SEGUNDOS = 5
MAXIMO_POR_CICLO = 50
LARGO_MAXIMO_ERROR = 200


async def procesar_cola(pool: AsyncConnectionPool, espacios: ClienteEspacios) -> None:
    while True:
        await asyncio.sleep(INTERVALO_SEGUNDOS)
        try:
            await procesar_ciclo(pool, espacios)
        except Exception:
            logger.exception("Falló un ciclo de la cola de liberaciones")


async def procesar_ciclo(pool: AsyncConnectionPool, espacios: ClienteEspacios) -> None:
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
            continue

        async with pool.connection() as conexion:
            await reservas.borrar_liberacion(conexion, pendiente.id)
        logger.info("Liberación de %s procesada (resultado %d)", pendiente.referencia,
                    respuesta.resultado)
