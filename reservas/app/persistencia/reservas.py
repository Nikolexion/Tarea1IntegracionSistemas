from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import class_row

ESTADO_ACTIVA = "ACTIVA"


@dataclass(frozen=True)
class ReservaGuardada:
    id: int
    referencia: UUID
    estado: str
    sala_id: int
    sala_nombre: str
    fecha: date
    hora_inicio: str
    hora_fin: str
    titular_id: int
    creada_por_id: int
    creada_en: datetime
    cancelada_en: datetime | None


_COLUMNAS = """
    id, referencia, estado, sala_id, sala_nombre, fecha,
    to_char(hora_inicio, 'HH24:MI') AS hora_inicio, to_char(hora_fin, 'HH24:MI') AS hora_fin,
    titular_id, creada_por_id, creada_en, cancelada_en
"""

_FILTRO_TITULAR = "%(titular)s::bigint IS NULL OR titular_id = %(titular)s"


# Escritura

async def insertar(
    conexion: AsyncConnection,
    referencia: UUID,
    sala_id: int,
    sala_nombre: str,
    fecha: date,
    hora_inicio: str,
    hora_fin: str,
    titular_id: int,
    creada_por_id: int,
) -> ReservaGuardada:
    cursor = conexion.cursor(row_factory=class_row(ReservaGuardada))
    await cursor.execute(
        f"""
        INSERT INTO reservas (referencia, estado, sala_id, sala_nombre, fecha,
                              hora_inicio, hora_fin, titular_id, creada_por_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING {_COLUMNAS}
        """,
        (referencia, ESTADO_ACTIVA, sala_id, sala_nombre, fecha,
         hora_inicio, hora_fin, titular_id, creada_por_id),
    )
    return await cursor.fetchone()


# Cola de liberaciones

async def encolar_liberacion(
    conexion: AsyncConnection, referencia: UUID, sala_id: int, fecha: date, hora_inicio: str,
    hora_fin: str,
) -> None:
    await conexion.execute(
        """
        INSERT INTO liberaciones_pendientes (referencia, sala_id, fecha, hora_inicio, hora_fin)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (referencia, sala_id, fecha, hora_inicio, hora_fin),
    )


# Lectura

async def obtener_por_id(conexion: AsyncConnection, reserva_id: int) -> ReservaGuardada | None:
    cursor = conexion.cursor(row_factory=class_row(ReservaGuardada))
    await cursor.execute(f"SELECT {_COLUMNAS} FROM reservas WHERE id = %s", (reserva_id,))
    return await cursor.fetchone()


async def listar(
    conexion: AsyncConnection, titular_id: int | None, limit: int, offset: int
) -> tuple[list[ReservaGuardada], int]:
    parametros = {"titular": titular_id, "limit": limit, "offset": offset}
    cursor = conexion.cursor(row_factory=class_row(ReservaGuardada))
    await cursor.execute(
        f"""
        SELECT {_COLUMNAS} FROM reservas WHERE {_FILTRO_TITULAR}
        ORDER BY creada_en DESC, id DESC LIMIT %(limit)s OFFSET %(offset)s
        """,
        parametros,
    )
    pagina = await cursor.fetchall()
    cursor_total = await conexion.execute(
        f"SELECT count(*) FROM reservas WHERE {_FILTRO_TITULAR}", parametros
    )
    (total,) = await cursor_total.fetchone()
    return pagina, total
