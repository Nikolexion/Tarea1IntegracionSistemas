"""Caché de la grilla de disponibilidad en Redis, patrón cache-aside"""

import logging
from datetime import date
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

from app.generado import espacios_pb2 as pb

logger = logging.getLogger(__name__)

# Corto: si Redis no responde, sale más barato ir directo a Espacios
TIEMPO_ESPERA_SEGUNDOS = 0.2



class CacheDisponibilidad:
    """Guarda la respuesta de ListarDisponibilidad por fecha. Un error de Redis nunca se
    propaga: se registra y se sigue como si la clave no estuviera."""

    def __init__(self, cliente: Redis | None, ttl_segundos: int):
        # TTL 0 desactiva la caché: no se toca Redis
        self._cliente = cliente if ttl_segundos > 0 else None
        self._ttl = ttl_segundos

    async def cerrar(self) -> None:
        if self._cliente is not None:
            await self._cliente.aclose()

    async def obtener(self, fecha: date) -> tuple[pb.ListarDisponibilidadResponse | None, bool]:
        """Devuelve (respuesta guardada o None, si Redis respondió)."""
        if self._cliente is None:
            return None, False
        try:
            guardado = await self._cliente.get(_clave(fecha))
        except RedisError as error:
            logger.warning("Caché no disponible al leer %s: %s", fecha, error)
            return None, False
        if guardado is None:
            return None, True
        return pb.ListarDisponibilidadResponse.FromString(guardado), True

    async def guardar(self, fecha: date, respuesta: pb.ListarDisponibilidadResponse) -> None:
        if self._cliente is None:
            return
        try:
            await self._cliente.set(_clave(fecha), respuesta.SerializeToString(), ex=self._ttl)
        except RedisError as error:
            logger.warning("Caché no disponible al guardar %s: %s", fecha, error)

    async def invalidar(self, fecha: date) -> None:
        """Borra la clave: la próxima consulta vuelve a preguntarle a Espacios."""
        if self._cliente is None:
            return
        try:
            await self._cliente.delete(_clave(fecha))
        except RedisError as error:
            logger.warning("Caché no disponible al invalidar %s: %s", fecha, error)


def _clave(fecha: date) -> str:
    return f"disponibilidad:{fecha.isoformat()}"


def abrir_cache(redis_url: str, ttl_segundos: int) -> CacheDisponibilidad:
    """No se conecta todavía: Reservas arranca aunque Redis esté caído."""
    if ttl_segundos == 0:
        return CacheDisponibilidad(None, 0)
    cliente = Redis.from_url(
        redis_url,
        socket_connect_timeout=TIEMPO_ESPERA_SEGUNDOS,
        socket_timeout=TIEMPO_ESPERA_SEGUNDOS,
        # Sin reintentos: por defecto redis-py reintenta con espera y alargaría cada falla
        retry=Retry(NoBackoff(), 0),
    )
    return CacheDisponibilidad(cliente, ttl_segundos)


# Dependencia de FastAPI

def _cache(request: Request) -> CacheDisponibilidad:
    return request.app.state.cache


Cache = Annotated[CacheDisponibilidad, Depends(_cache)]
