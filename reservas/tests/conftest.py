import asyncio
import os
import sys
import uuid
from dataclasses import dataclass

import httpx
import psycopg
import pytest

URL_BASE_PRUEBAS = "postgresql://reservas:reservas_dev@127.0.0.1:5434/reservas"
DIRECCION_ESPACIOS = "127.0.0.1:50051"
SECRETO_PRUEBAS = "secreto-solo-para-pruebas-de-reservas"
PREFIJO_EMAIL_PRUEBA = "prueba-api-"
PASSWORD_PRUEBA = "contrasena-de-prueba"

os.environ.update({
    "RESERVAS_DB_URL": URL_BASE_PRUEBAS,
    "ESPACIOS_DIRECCION": DIRECCION_ESPACIOS,
    "ESPACIOS_DEADLINE_MS": "1000",
    "JWT_SECRETO": SECRETO_PRUEBAS,
    "JWT_MINUTOS_VALIDEZ": "60",
})

os.environ.pop("ADMIN_EMAIL_INICIAL", None)
os.environ.pop("ADMIN_PASSWORD_INICIAL", None)

from app.auth.contrasenas import generar_hash  
from app.auth.tokens import emitir_token  
from app.main import crear_app  
from app.persistencia.usuarios import crear_usuario  


def pytest_asyncio_loop_factories(config, item):
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"predeterminado": asyncio.new_event_loop}


def email_de_prueba() -> str:
    return f"{PREFIJO_EMAIL_PRUEBA}{uuid.uuid4().hex[:12]}@example.com"


def crear_cliente(app) -> httpx.AsyncClient:
    """Cliente HTTP en memoria; recibe el 500 en vez de propagar la excepción a la prueba"""
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transporte, base_url="http://prueba")


@pytest.fixture
async def conexion_prueba():
    """Conexión cuya transacción se revierte al terminar"""
    async with await psycopg.AsyncConnection.connect(URL_BASE_PRUEBAS) as conexion:
        yield conexion
        await conexion.rollback()


@pytest.fixture
async def app_iniciada():
    """Aplicación con el pool abierto; al terminar borra las cuentas de prueba"""
    app = crear_app()
    async with app.router.lifespan_context(app):
        yield app
        async with app.state.pool.connection() as conexion:
            await conexion.execute(
                "DELETE FROM usuarios WHERE email LIKE %s", (PREFIJO_EMAIL_PRUEBA + "%",)
            )


@pytest.fixture
async def cliente_api(app_iniciada):
    async with crear_cliente(app_iniciada) as cliente:
        yield cliente


@dataclass(frozen=True)
class CuentaDePrueba:
    id: int
    email: str
    token: str

    @property
    def autorizacion(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture
def crear_cuenta(app_iniciada):
    """Crea una cuenta directo en la base, con su token, sin pasar por los endpoints probados"""
    hashes: list[str] = []

    async def _crear(rol: str = "usuario") -> CuentaDePrueba:
        if not hashes:  # bcrypt es lento: un solo hash por prueba
            hashes.append(await generar_hash(PASSWORD_PRUEBA))
        async with app_iniciada.state.pool.connection() as conexion:
            usuario = await crear_usuario(conexion, "Prueba", email_de_prueba(), hashes[0], rol)
        token = emitir_token(usuario.id, rol, SECRETO_PRUEBAS, 60)
        return CuentaDePrueba(usuario.id, usuario.email, token)

    return _crear
