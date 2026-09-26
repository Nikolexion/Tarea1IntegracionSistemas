"""`Idempotency-Key` en `POST /v1/reservas`

Mismo esquema que test_reservas.py: Espacios real, sala 1 (2 puestos) y una fecha futura al azar
Las claves de las cuentas de prueba las borra `app_iniciada` al terminar
"""

import random
from datetime import date, timedelta

import pytest

from app.api.esquemas import ReservaNueva
from app.dominio.idempotencia import hash_cuerpo
from app.espacios_gateway.cliente import EspaciosNoDisponible


@pytest.fixture
def datos():
    fecha = (date.today() + timedelta(days=random.randint(60, 3000))).isoformat()
    return {"sala_id": 1, "fecha": fecha, "hora_inicio": "10:00", "hora_fin": "11:00"}


async def _reservar(cliente, cuenta, datos, clave):
    headers = {**cuenta.autorizacion, "Idempotency-Key": clave}
    return await cliente.post("/v1/reservas", json=datos, headers=headers)


async def _insertar_en_curso(app, cuenta, clave, datos, antiguedad: str) -> None:
    async with app.state.pool.connection() as conexion:
        await conexion.execute(
            """
            INSERT INTO claves_idempotencia (usuario_id, clave, hash_cuerpo, estado, creada_en)
            VALUES (%s, %s, %s, 'EN_CURSO', now() - %s::interval)
            """,
            (cuenta.id, clave, hash_cuerpo(ReservaNueva(**datos)), antiguedad),
        )


async def test_misma_clave_y_cuerpo_repite_la_respuesta(cliente_api, crear_cuenta, datos):
    cuenta = await crear_cuenta()

    primera = await _reservar(cliente_api, cuenta, datos, "clave-1")
    segunda = await _reservar(cliente_api, cuenta, datos, "clave-1")

    assert primera.status_code == segunda.status_code == 201
    # Mismo JSON; JSONB no conserva el orden de las llaves dentro de `_links`
    assert segunda.json() == primera.json()
    assert segunda.headers["location"] == primera.headers["location"]
    listado = await cliente_api.get("/v1/reservas", headers=cuenta.autorizacion)
    assert listado.json()["total"] == 1
    disponibilidad = await cliente_api.get(
        "/v1/salas/1/disponibilidad",
        params={k: datos[k] for k in ("fecha", "hora_inicio", "hora_fin")},
        headers=cuenta.autorizacion,
    )
    assert disponibilidad.json()["puestos_libres"] == 1  # un solo puesto ocupado en Espacios


async def test_misma_clave_con_otro_cuerpo_responde_422(cliente_api, crear_cuenta, datos):
    cuenta = await crear_cuenta()
    await _reservar(cliente_api, cuenta, datos, "clave-1")

    otra = await _reservar(cliente_api, cuenta, {**datos, "hora_fin": "12:00"}, "clave-1")

    assert otra.status_code == 422
    assert otra.json()["type"] == "/problemas/idempotencia-reutilizada"


async def test_clave_en_curso_reciente_responde_409_y_la_abandonada_se_retoma(
    cliente_api, crear_cuenta, datos, app_iniciada
):
    cuenta = await crear_cuenta()
    await _insertar_en_curso(app_iniciada, cuenta, "reciente", datos, "5 seconds")
    await _insertar_en_curso(app_iniciada, cuenta, "abandonada", datos, "2 minutes")

    reciente = await _reservar(cliente_api, cuenta, datos, "reciente")
    abandonada = await _reservar(cliente_api, cuenta, datos, "abandonada")

    assert reciente.status_code == 409
    assert reciente.json()["type"] == "/problemas/idempotencia-en-curso"
    assert abandonada.status_code == 201


async def test_tras_un_503_el_reintento_con_la_misma_clave_reserva(
    cliente_api, crear_cuenta, datos, app_iniciada, monkeypatch
):
    cuenta = await crear_cuenta()

    async def ocupar_no_disponible(*args):
        raise EspaciosNoDisponible("Espacios caído")

    monkeypatch.setattr(app_iniciada.state.espacios, "ocupar_puesto", ocupar_no_disponible)
    fallida = await _reservar(cliente_api, cuenta, datos, "clave-1")
    monkeypatch.undo()
    reintento = await _reservar(cliente_api, cuenta, datos, "clave-1")

    assert fallida.status_code == 503  # no se guarda: la clave se borra
    assert reintento.status_code == 201
