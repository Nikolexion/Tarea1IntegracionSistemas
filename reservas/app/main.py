import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth
from app.api.errores import registrar_manejadores
from app.config import cargar_configuracion
from app.dominio.usuarios import crear_administrador_inicial
from app.persistencia.conexion import abrir_pool

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")

@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    configuracion = cargar_configuracion()
    app.state.configuracion = configuracion
    app.state.pool = pool = await abrir_pool(configuracion.reservas_db_url)
    try:
        async with pool.connection() as conexion:
            await crear_administrador_inicial(
                conexion, configuracion.admin_email_inicial, configuracion.admin_password_inicial
            )
        yield
    finally:
        await pool.close()


def crear_app() -> FastAPI:
    app = FastAPI(title="CoLabora API de Reservas", version="1.0.0", lifespan=ciclo_de_vida)
    registrar_manejadores(app)
    app.include_router(auth.router)
    return app


app = crear_app()
