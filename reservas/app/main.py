"""API REST de Reservas. Se ejecuta desde `reservas/` con: uvicorn app.main:app"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI

from app.api import auth, reservas, salas, usuarios
from app.api.errores import registrar_manejadores
from app.cache.disponibilidad import abrir_cache
from app.cola.procesador import procesar_cola
from app.config import cargar_configuracion
from app.dominio.usuarios import crear_administrador_inicial
from app.espacios_gateway.cliente import ClienteEspacios
from app.persistencia.conexion import abrir_pool

# uvicorn solo configura sus propios loggers, sin esto no se verían los INFO de la aplicación.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")

# En local es <repo>/contratos; en la imagen Docker (código en /servicio/app), /contratos
RUTA_CONTRATO = Path(__file__).resolve().parents[2] / "contratos" / "openapi.yaml"


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    configuracion = cargar_configuracion()
    app.state.configuracion = configuracion
    app.state.pool = pool = await abrir_pool(configuracion.reservas_db_url)
    # No se conecta todavía: Reservas arranca aunque Espacios esté caído
    app.state.espacios = espacios = ClienteEspacios(
        configuracion.espacios_direccion, configuracion.espacios_deadline_ms
    )
    app.state.cache = cache = abrir_cache(
        configuracion.redis_url, configuracion.cache_ttl_segundos
    )
    # Cola de liberaciones, se cancela antes de cerrar el canal y el pool
    cola = asyncio.create_task(procesar_cola(pool, espacios, cache))
    try:
        async with pool.connection() as conexion:
            await crear_administrador_inicial(
                conexion, configuracion.admin_email_inicial, configuracion.admin_password_inicial
            )
        yield
    finally:
        cola.cancel()
        with suppress(asyncio.CancelledError):
            await cola
        await espacios.cerrar()
        await cache.cerrar()
        await pool.close()


@cache
def contrato_openapi() -> dict[str, Any]:
    with RUTA_CONTRATO.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)


def crear_app() -> FastAPI:
    """Crea la aplicación; las pruebas la usan para obtener instancias independientes."""
    app = FastAPI(title="CoLabora — API de Reservas", version="1.0.0", lifespan=ciclo_de_vida)
    registrar_manejadores(app)
    for modulo in (auth, usuarios, salas, reservas):
        app.include_router(modulo.router)
    # /docs y /openapi.json sirven el contrato escrito primero, no el esquema que FastAPI genera
    # desde el código: el contrato es la fuente de verdad
    app.openapi = contrato_openapi
    return app


app = crear_app()
