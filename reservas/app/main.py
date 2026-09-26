import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI

from app.api import auth, reservas, salas, usuarios
from app.api.errores import registrar_manejadores
from app.config import cargar_configuracion
from app.dominio.usuarios import crear_administrador_inicial
from app.espacios_gateway.cliente import ClienteEspacios
from app.persistencia.conexion import abrir_pool

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")

RUTA_CONTRATO = Path(__file__).resolve().parents[2] / "contratos" / "openapi.yaml"

@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    configuracion = cargar_configuracion()
    app.state.configuracion = configuracion
    app.state.pool = pool = await abrir_pool(configuracion.reservas_db_url)
    app.state.espacios = espacios = ClienteEspacios(
        configuracion.espacios_direccion, configuracion.espacios_deadline_ms
    )
    try:
        async with pool.connection() as conexion:
            await crear_administrador_inicial(
                conexion, configuracion.admin_email_inicial, configuracion.admin_password_inicial
            )
        yield
    finally:
        await espacios.cerrar()
        await pool.close()

@cache
def contrato_openapi() -> dict[str, Any]:
    with RUTA_CONTRATO.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)

def crear_app() -> FastAPI:
    app = FastAPI(title="CoLabora API de Reservas", version="1.0.0", lifespan=ciclo_de_vida)
    registrar_manejadores(app)
    for modulo in (auth, reservas, usuarios, salas):
        app.include_router(modulo.router)
    app.openapi = contrato_openapi
    return app


app = crear_app()
