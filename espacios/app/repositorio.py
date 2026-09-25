'''
Acceso a la base de Espacios
'''

from dataclasses import dataclass
from datetime import date, time
from enum import Enum

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


# --- tipos ---
@dataclass(frozen=True)
class Franja:
    fecha: date
    hora_inicio: time
    hora_fin: time

class ResultadoOcupacion(Enum):
    OCUPADO = "OCUPADO"
    SIN_PUESTOS = "SIN_PUESTOS"

@dataclass(frozen=True)
class Ocupacion:
    resultado: ResultadoOcupacion
    puestos_libres: int


# --- Errores de negocio ---
class SalaNoEncontrada(Exception):
    pass

class FranjaInvalida(Exception):
    pass

class FranjaIniciada(Exception):
    pass

# --- Pool de conexiones ---
def crear_pool(db_url:str) -> AsyncConnectionPool:
    return AsyncConnectionPool(
        db_url,
        open=False,
        kwargs={"autocommit": True, "row_factory": dict_row},
    )


# --- Repositorio ---
class RepositorioEspacios:
    def __init__(self, pool: AsyncConnectionPool, zona_horaria: str):
        self._pool = pool
        self._zona_horaria = zona_horaria

    async def verificar_zona_horaria(self) -> None:
        # Falla al arrancar si el postgreSQL no reconoce la zona configurada
        async with self._pool.connection() as conexion:
            sql = "SELECT 1 FROM pg_timezone_names WHERE name = %s"
            if await _fila(conexion, sql, (self._zona_horaria,)) is None:
                raise ValueError(f"Zona horaria desconocida: {self._zona_horaria!r}")

    async def consultar_disponibilidad(self, sala_id: int, franja: Franja)-> dict:
        # Sala con sus puestos libres en la franja
        async with self._pool.connection() as conexion:
            sala = await _buscar_sala(conexion, sala_id)
            await _validar_bloque(conexion, franja)
            ocupadas = await _contar_ocupadas(conexion, sala_id, franja)

        return {**sala, "puestos_libres": sala["capacidad"] - ocupadas}

    async def listar_disponibilidad(self, fecha:date) -> list[dict]:
        # Cada sala por cada bloque de la fecha, ordenado por sala y hora
        async with self._pool.connection() as conexion:
            cursor = await conexion.execute(_SQL_LISTAR, (fecha,))
            return await cursor.fetchall()

    async def ocupar(self, sala_id: int, franja: Franja, referencia: str) -> Ocupacion:
        # Verifica y ocupa en una sola transaccion
        async with self._pool.connection() as conexion, conexion.transaction():
            # FOR UPDATE: las ocupaciones de una misma sala hacen fila
            # y la segunda cuenta los puestos después de que la primera
            # confirmó
            sala = await _buscar_sala(conexion, sala_id, bloquear=True)
            await _validar_bloque(conexion, franja)
            if await self._franja_iniciada(conexion, franja):
                raise FranjaIniciada("La franja ya comenzó, no se puede ocupar")
            libres = sala["capacidad"] - await _contar_ocupadas(conexion, sala["id"], franja)
            if libres <= 0:
                return Ocupacion(ResultadoOcupacion.SIN_PUESTOS, 0)
            await _insertar_ocupacion(conexion, sala["id"], franja, referencia)
            return Ocupacion(ResultadoOcupacion.OCUPADO, libres - 1)

    async def _franja_iniciada(self, conexion: AsyncConnection, franja: Franja) -> bool:
        # La hora actual se toma de postgreSQL en la zona configurada: no depende
        # de la zona del container ni de la base de zonas horarias de python
        fila = await _fila(
            conexion,
            "SELECT (%s::date + %s::time) <= (now() AT TIME ZONE %s) AS iniciada",
            (franja.fecha, franja.hora_inicio, self._zona_horaria),
        )
        return fila["iniciada"]

# Consultas de apoyo
_SQL_SALA = "SELECT id, nombre, capacidad FROM salas WHERE id = %s"
_SQL_SALA_BLOQUEANDO = "SELECT id, nombre, capacidad FROM salas WHERE id = %s FOR UPDATE"

# Cross join, todas las salas por todos los bloques, el left join deja
# en cero las franjas sin ocupaciones
_SQL_LISTAR = """
    SELECT s.id, s.nombre, s.capacidad, b.hora_inicio, b.hora_fin,
        s.capacidad - count(o.referencia) AS puestos_libres
    FROM salas s
    CROSS JOIN bloques b
    LEFT JOIN ocupaciones o
        ON o.sala_id = s.id AND o.fecha = %s
        AND o.hora_inicio = b.hora_inicio AND o.estado = 'ACTIVA'
    GROUP BY s.id, b.hora_inicio
    ORDER BY s.id, b.hora_inicio
"""




async def _fila(conexion: AsyncConnection, sql: str, parametros: tuple) -> dict | None:
    cursor = await conexion.execute(sql, parametros)
    return await cursor.fetchone()

async def _buscar_sala(conexion: AsyncConnection, sala_id: int, bloquear: bool = False) -> dict:
    sala = await _fila(conexion, _SQL_SALA_BLOQUEANDO if bloquear else _SQL_SALA, (sala_id,))
    if sala is None:
        raise SalaNoEncontrada(f"La sala {sala_id} no existe")
    return sala

async def _validar_bloque(conexion: AsyncConnection, franja: Franja) -> None:
    sql = "SELECT 1 FROM bloques WHERE hora_inicio = %s AND hora_fin = %s"
    if await _fila(conexion, sql, (franja.hora_inicio, franja.hora_fin)) is None:
        raise FranjaInvalida("La franja no corresponde a un horario definido")

async def _contar_ocupadas(conexion: AsyncConnection, sala_id: int, franja: Franja) -> int:
    fila = await _fila(
        conexion,
        """
        SELECT count(*) AS ocupadas FROM ocupaciones
        WHERE sala_id = %s AND fecha = %s AND hora_inicio = %s AND estado = 'ACTIVA'
        """,
        (sala_id, franja.fecha, franja.hora_inicio),
    )
    return fila["ocupadas"]

async def _insertar_ocupacion(conexion: AsyncConnection, sala_id: int, franja: Franja, referencia: str) -> None:
    await conexion.execute(
        """
        INSERT INTO ocupaciones (referencia, estado, sala_id, fecha, hora_inicio, hora_fin)
        VALUES (%s, 'ACTIVA', %s, %s, %s, %s)
        """,
        (referencia, sala_id, franja.fecha, franja.hora_inicio, franja.hora_fin),
    )
