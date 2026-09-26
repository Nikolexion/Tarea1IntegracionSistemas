"""Reglas de `Idempotency-Key` en la creación de reservas"""

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

from app.dominio.errores import IdempotenciaEnCurso, IdempotenciaReutilizada
from app.persistencia import idempotencia
from app.persistencia.idempotencia import ESTADO_COMPLETADA

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Clave:
    usuario_id: int  # alcance por usuario
    valor: str
    hash_cuerpo: str


def hash_cuerpo(datos: BaseModel) -> str:
    """SHA-256 del cuerpo ya validado con llaves ordenadas: el orden o los espacios no cuentan."""
    texto = json.dumps(datos.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(texto.encode()).hexdigest()


async def registrar(pool: AsyncConnectionPool, clave: Clave) -> dict[str, Any] | None:
    """Toma la clave EN_CURSO (None: procesar) o devuelve la respuesta guardada para repetirla."""
    async with pool.connection() as conexion:
        if await idempotencia.tomar(conexion, clave.usuario_id, clave.valor, clave.hash_cuerpo):
            return None
        guardada = await idempotencia.obtener(conexion, clave.usuario_id, clave.valor)
    if guardada.hash_cuerpo != clave.hash_cuerpo:
        raise IdempotenciaReutilizada()
    if guardada.estado != ESTADO_COMPLETADA:
        raise IdempotenciaEnCurso()
    return guardada.cuerpo_respuesta


async def completar(conexion: AsyncConnection, clave: Clave, cuerpo: dict[str, Any]) -> None:
    """Guarda la respuesta 201; se llama en la transacción que inserta la reserva."""
    await idempotencia.completar(conexion, clave.usuario_id, clave.valor, cuerpo)


async def descartar(pool: AsyncConnectionPool, clave: Clave) -> None:
    """Tras un error la clave se borra y un reintento se ejecuta de nuevo. No lanza."""
    try:
        async with pool.connection() as conexion:
            await idempotencia.borrar_en_curso(conexion, clave.usuario_id, clave.valor)
    except Exception:
        # Queda EN_CURSO: a los 60 s se considera abandonada y se puede retomar
        logger.exception("No se pudo borrar la clave de idempotencia %s", clave.valor)
