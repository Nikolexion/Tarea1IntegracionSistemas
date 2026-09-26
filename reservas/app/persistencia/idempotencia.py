"""Tabla `claves_idempotencia` con SQL explícito"""

from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.types.json import Jsonb

ESTADO_EN_CURSO = "EN_CURSO"
ESTADO_COMPLETADA = "COMPLETADA"
SEGUNDOS_ABANDONO = 60  # EN_CURSO más antigua que esto se considera abandonada


@dataclass(frozen=True)
class ClaveGuardada:
    hash_cuerpo: str
    estado: str
    cuerpo_respuesta: dict[str, Any] | None




async def tomar(conexion: AsyncConnection, usuario_id: int, clave: str, hash_cuerpo: str) -> bool:
    """Inserta la clave EN_CURSO, o retoma una abandonada con el mismo cuerpo. True si se tomó.

    Si la clave ya existe, ON CONFLICT bloquea su fila hasta el fin de la transacción: dos
    peticiones no pueden retomarla a la vez y la fila no cambia antes de leerla con `obtener`
    """
    cursor = await conexion.execute(
        """
        INSERT INTO claves_idempotencia (usuario_id, clave, hash_cuerpo, estado)
        VALUES (%(usuario)s, %(clave)s, %(hash)s, %(en_curso)s)
        ON CONFLICT (usuario_id, clave) DO UPDATE SET creada_en = now()
        WHERE claves_idempotencia.estado = %(en_curso)s
          AND claves_idempotencia.hash_cuerpo = %(hash)s
          AND claves_idempotencia.creada_en < now() - make_interval(secs => %(abandono)s)
        RETURNING 1
        """,
        {"usuario": usuario_id, "clave": clave, "hash": hash_cuerpo,
         "en_curso": ESTADO_EN_CURSO, "abandono": SEGUNDOS_ABANDONO},
    )
    return await cursor.fetchone() is not None


async def completar(
    conexion: AsyncConnection, usuario_id: int, clave: str, cuerpo: dict[str, Any]
) -> None:
    await conexion.execute(
        """
        UPDATE claves_idempotencia SET estado = %s, codigo_http = 201, cuerpo_respuesta = %s
        WHERE usuario_id = %s AND clave = %s
        """,
        (ESTADO_COMPLETADA, Jsonb(cuerpo), usuario_id, clave),
    )


async def borrar_en_curso(conexion: AsyncConnection, usuario_id: int, clave: str) -> None:
    await conexion.execute(
        "DELETE FROM claves_idempotencia WHERE usuario_id = %s AND clave = %s AND estado = %s",
        (usuario_id, clave, ESTADO_EN_CURSO),
    )




async def obtener(conexion: AsyncConnection, usuario_id: int, clave: str) -> ClaveGuardada | None:
    cursor = conexion.cursor(row_factory=class_row(ClaveGuardada))
    await cursor.execute(
        """
        SELECT hash_cuerpo, estado, cuerpo_respuesta FROM claves_idempotencia
        WHERE usuario_id = %s AND clave = %s
        """,
        (usuario_id, clave),
    )
    return await cursor.fetchone()
