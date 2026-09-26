"""Fixtures contra la base real (espacios-db en 127.0.0.1:5433); cada prueba borra lo que crea."""

import asyncio
import itertools

import grpc
import pytest

from app.generado import espacios_pb2_grpc
from app.repositorio import RepositorioEspacios, crear_pool
from app.servicio import ServicioEspacios
from app.servidor import crear_servidor
from tests.datos import DB_URL_PRUEBAS, PREFIJO_REFERENCIA

_ids_de_sala = itertools.count(9000)  # ids altos para no chocar con la semilla


def pytest_asyncio_loop_factories(config, item):
    # psycopg asíncrono no funciona con el bucle por defecto de Windows (Proactor).
    return {"selector": asyncio.SelectorEventLoop}


@pytest.fixture
async def pool():
    pool = crear_pool(DB_URL_PRUEBAS)
    await pool.open(wait=True)
    yield pool
    async with pool.connection() as conexion:
        await conexion.execute("DELETE FROM ocupaciones WHERE referencia LIKE %s", (PREFIJO_REFERENCIA + "%",))
    await pool.close()


@pytest.fixture
async def repositorio(pool):
    return RepositorioEspacios(pool, "America/Santiago")


@pytest.fixture
async def crear_sala(pool):
    """Función que crea una sala de prueba con la capacidad dada y devuelve su id."""
    creadas = []

    async def borrar(conexion, sala_id: int) -> None:
        await conexion.execute("DELETE FROM ocupaciones WHERE sala_id = %s", (sala_id,))
        await conexion.execute("DELETE FROM salas WHERE id = %s", (sala_id,))

    async def crear(capacidad: int) -> int:
        sala_id = next(_ids_de_sala)
        async with pool.connection() as conexion:
            await borrar(conexion, sala_id)  # restos de una ejecución interrumpida
            await conexion.execute(
                "INSERT INTO salas (id, nombre, capacidad) VALUES (%s, %s, %s)",
                (sala_id, f"Sala de prueba {sala_id}", capacidad),
            )
        creadas.append(sala_id)
        return sala_id

    yield crear
    async with pool.connection() as conexion:
        for sala_id in creadas:
            await borrar(conexion, sala_id)


@pytest.fixture
async def cliente_grpc(repositorio):
    """Stub conectado a un servidor gRPC real levantado en este mismo proceso"""
    servidor, puerto = crear_servidor(ServicioEspacios(repositorio, latencia_artificial_ms=0), "127.0.0.1:0")
    await servidor.start()
    async with grpc.aio.insecure_channel(f"127.0.0.1:{puerto}") as canal:
        yield espacios_pb2_grpc.EspaciosStub(canal)
    await servidor.stop(0)
