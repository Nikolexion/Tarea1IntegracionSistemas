"""Gateway hacia el Espacios real y traducción de sus errores a HTTP."""

import asyncio
import uuid
from datetime import date, timedelta

import grpc
import pytest
from psycopg_pool import PoolTimeout

from app.espacios_gateway.cliente import (
    ClienteEspacios,
    DatosRechazados,
    EspaciosNoDisponible,
    EspaciosSinRespuesta,
)
from app.generado import espacios_pb2 as pb
from app.generado import espacios_pb2_grpc
from tests.conftest import DIRECCION_ESPACIOS, crear_app, crear_cliente

FECHA_FUTURA = (date.today() + timedelta(days=7)).isoformat()


@pytest.fixture
async def abrir_cliente():
    """Crea clientes con la dirección y el deadline pedidos; los cierra al terminar."""
    clientes: list[ClienteEspacios] = []

    def _abrir(direccion: str = DIRECCION_ESPACIOS, deadline_ms: int = 1000) -> ClienteEspacios:
        clientes.append(ClienteEspacios(direccion, deadline_ms))
        return clientes[-1]

    yield _abrir
    for cliente in clientes:
        await cliente.cerrar()


async def test_funcionamiento_normal(abrir_cliente):
    espacios = abrir_cliente()
    referencia = str(uuid.uuid4())

    grilla = await espacios.listar_disponibilidad(FECHA_FUTURA)
    ocupacion = await espacios.ocupar_puesto(1, FECHA_FUTURA, "10:00", "11:00", referencia)
    liberacion = await espacios.liberar_puesto(referencia)

    assert len(grilla.disponibilidades) == 48  # 4 salas × 12 franjas
    assert ocupacion.resultado == pb.RESULTADO_OCUPACION_OCUPADO
    assert liberacion.resultado == pb.RESULTADO_LIBERACION_LIBERADO


async def test_espacios_caido_lanza_no_disponible(abrir_cliente):
    espacios = abrir_cliente("127.0.0.1:1")  # puerto donde no escucha nadie

    with pytest.raises(EspaciosNoDisponible):
        await espacios.listar_disponibilidad(FECHA_FUTURA)


class EspaciosLento(espacios_pb2_grpc.EspaciosServicer):
    """Servidor de prueba que tarda más que el deadline (un deadline mínimo contra el Espacios
    real no es confiable: a veces responde antes)."""

    async def ListarDisponibilidad(self, request, context):
        await asyncio.sleep(1)
        return pb.ListarDisponibilidadResponse()


async def test_espacios_lento_lanza_sin_respuesta(abrir_cliente):
    servidor = grpc.aio.server()
    espacios_pb2_grpc.add_EspaciosServicer_to_server(EspaciosLento(), servidor)
    puerto = servidor.add_insecure_port("127.0.0.1:0")
    await servidor.start()
    try:
        espacios = abrir_cliente(f"127.0.0.1:{puerto}", deadline_ms=100)
        # Con el canal ya conectado, un timeout sí es un resultado incierto (504).
        await espacios._canal.channel_ready()

        with pytest.raises(EspaciosSinRespuesta):
            await espacios.listar_disponibilidad(FECHA_FUTURA)
    finally:
        await servidor.stop(None)


@pytest.mark.parametrize(
    ("excepcion", "status", "tipo"),
    [
        (EspaciosNoDisponible("caído"), 503, "/problemas/espacios-no-disponible"),
        (EspaciosSinRespuesta("lento"), 504, "/problemas/espacios-sin-respuesta"),
        (DatosRechazados("la franja ya comenzó"), 422, "/problemas/datos-invalidos"),
        (PoolTimeout("sin conexiones libres"), 503, "/problemas/servicio-saturado"),
    ],
)
async def test_errores_se_traducen_a_http(excepcion, status, tipo):
    app = crear_app()

    @app.get("/prueba/falla")
    async def fallar():
        raise excepcion

    async with crear_cliente(app) as cliente:
        respuesta = await cliente.get("/prueba/falla")

    assert respuesta.status_code == status
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.json()["type"] == tipo
    if status == 503:
        assert respuesta.headers["retry-after"] == "5"
    if status == 422:
        assert respuesta.json()["detail"] == "la franja ya comenzó"
