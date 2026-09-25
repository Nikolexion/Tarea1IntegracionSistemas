from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import cargar_configuracion
from app.persistencia.conexion import abrir_pool


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    configuracion = cargar_configuracion()
    app.state.pool = pool = await abrir_pool(configuracion.reservas_db_url)
    try:
        yield
    finally:
        await pool.close()


def crear_app() -> FastAPI:
    app = FastAPI(title="CoLabora — API de Reservas", version="1.0.0", lifespan=ciclo_de_vida)
    return app


app = crear_app()
