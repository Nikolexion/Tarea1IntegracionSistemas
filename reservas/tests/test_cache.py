"""Caché de la grilla. Redis no se expone al host: se usa un doble en memoria con la
misma interfaz mínima, y Espacios y la base reales."""

import random
from datetime import date, timedelta

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.cache.disponibilidad import CacheDisponibilidad
from app.cola.procesador import procesar_ciclo



class RedisEnMemoria:
    """Solo las operaciones que usa la caché; ignora el vencimiento."""

    def __init__(self):
        self.datos: dict[str, bytes] = {}

    async def get(self, clave):
        return self.datos.get(clave)

    async def set(self, clave, valor, ex):
        self.datos[clave] = valor

    async def delete(self, clave):
        self.datos.pop(clave, None)

    async def aclose(self):
        pass


class RedisCaido:
    async def get(self, *args, **kwargs):
        raise RedisConnectionError("Redis caído (simulado)")

    set = delete = get



@pytest.fixture
def fecha():
    return (date.today() + timedelta(days=random.randint(60, 3000))).isoformat()


@pytest.fixture
def llamadas_a_espacios(app_iniciada, monkeypatch):
    """Cuenta las llamadas a ListarDisponibilidad (sigue llamando al Espacios real)."""
    espacios = app_iniciada.state.espacios
    listar_real = espacios.listar_disponibilidad
    llamadas = []

    async def listar_contando(fecha):
        llamadas.append(fecha)
        return await listar_real(fecha)

    monkeypatch.setattr(espacios, "listar_disponibilidad", listar_contando)
    return llamadas


def usar_cache(app, cliente, ttl_segundos=30):
    app.state.cache = CacheDisponibilidad(cliente, ttl_segundos)


async def _grilla(cliente_api, cuenta, fecha):
    return await cliente_api.get("/v1/salas", params={"fecha": fecha}, headers=cuenta.autorizacion)



async def test_la_segunda_consulta_sale_de_la_cache(
    app_iniciada, cliente_api, crear_cuenta, llamadas_a_espacios, fecha
):
    redis = RedisEnMemoria()
    usar_cache(app_iniciada, redis)
    cuenta = await crear_cuenta()

    primera = await _grilla(cliente_api, cuenta, fecha)
    segunda = await _grilla(cliente_api, cuenta, fecha)

    assert segunda.json() == primera.json()
    assert llamadas_a_espacios == [fecha]
    assert f"disponibilidad:{fecha}" in redis.datos


async def test_una_reserva_invalida_la_grilla_de_su_fecha(
    app_iniciada, cliente_api, crear_cuenta, fecha
):
    redis = RedisEnMemoria()
    usar_cache(app_iniciada, redis)
    cuenta = await crear_cuenta()
    await _grilla(cliente_api, cuenta, fecha)

    datos = {"sala_id": 1, "fecha": fecha, "hora_inicio": "10:00", "hora_fin": "11:00"}
    respuesta = await cliente_api.post("/v1/reservas", json=datos, headers=cuenta.autorizacion)

    assert respuesta.status_code == 201
    assert f"disponibilidad:{fecha}" not in redis.datos


async def test_la_cola_invalida_la_grilla_al_liberar(
    app_iniciada, cliente_api, crear_cuenta, fecha
):
    redis = RedisEnMemoria()
    usar_cache(app_iniciada, redis)
    cuenta = await crear_cuenta()
    datos = {"sala_id": 1, "fecha": fecha, "hora_inicio": "10:00", "hora_fin": "11:00"}
    reserva = await cliente_api.post("/v1/reservas", json=datos, headers=cuenta.autorizacion)
    await cliente_api.patch(
        f"/v1/reservas/{reserva.json()['id']}",
        content='{"estado": "CANCELADA"}',
        headers={**cuenta.autorizacion, "Content-Type": "application/merge-patch+json"},
    )
    # Cancelar no invalida: la grilla se guarda después de cancelar y sigue ahí
    await _grilla(cliente_api, cuenta, fecha)
    assert f"disponibilidad:{fecha}" in redis.datos

    estado = app_iniciada.state
    await procesar_ciclo(estado.pool, estado.espacios, estado.cache)

    assert f"disponibilidad:{fecha}" not in redis.datos


async def test_con_redis_caido_la_grilla_responde_igual(
    app_iniciada, cliente_api, crear_cuenta, llamadas_a_espacios, fecha
):
    usar_cache(app_iniciada, RedisCaido())
    cuenta = await crear_cuenta()

    respuesta = await _grilla(cliente_api, cuenta, fecha)

    assert respuesta.status_code == 200
    assert llamadas_a_espacios == [fecha]


async def test_con_ttl_cero_no_se_usa_la_cache(
    app_iniciada, cliente_api, crear_cuenta, llamadas_a_espacios, fecha
):
    redis = RedisEnMemoria()
    usar_cache(app_iniciada, redis, ttl_segundos=0)
    cuenta = await crear_cuenta()

    await _grilla(cliente_api, cuenta, fecha)
    await _grilla(cliente_api, cuenta, fecha)

    assert llamadas_a_espacios == [fecha, fecha]
    assert redis.datos == {}
