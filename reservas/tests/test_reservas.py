import random
from datetime import date, timedelta

import pytest

from app.espacios_gateway.cliente import EspaciosSinRespuesta
from app.persistencia import reservas as persistencia_reservas


@pytest.fixture
def fecha():
    return (date.today() + timedelta(days=random.randint(60, 3000))).isoformat()


async def _reservar(cliente, cuenta, fecha, **cambios):
    datos = {"sala_id": 1, "fecha": fecha, "hora_inicio": "10:00", "hora_fin": "11:00", **cambios}
    return await cliente.post("/v1/reservas", json=datos, headers=cuenta.autorizacion)


async def _cancelar(cliente, cuenta, reserva_id):
    return await cliente.patch(
        f"/v1/reservas/{reserva_id}",
        content='{"estado": "CANCELADA"}',
        headers={**cuenta.autorizacion, "Content-Type": "application/merge-patch+json"},
    )


async def _contar_liberaciones(app, referencia=None, reserva_id=None) -> int:
    async with app.state.pool.connection() as conexion:
        cursor = await conexion.execute(
            """
            SELECT count(*) FROM liberaciones_pendientes l LEFT JOIN reservas r USING (referencia)
            WHERE l.referencia = %s OR r.id = %s
            """,
            (referencia, reserva_id),
        )
        (total,) = await cursor.fetchone()
        return total


def _simular_timeout_al_ocupar(app, monkeypatch) -> list[str]:
    """Espacios no responde al ocupar; devuelve la lista donde quedan las referencias usadas"""
    referencias: list[str] = []

    async def ocupar_sin_respuesta(sala_id, fecha, hora_inicio, hora_fin, referencia):
        referencias.append(referencia)
        raise EspaciosSinRespuesta("deadline vencido")

    monkeypatch.setattr(app.state.espacios, "ocupar_puesto", ocupar_sin_respuesta)
    return referencias


# Crear

async def test_reservar_hasta_llenar_la_sala(cliente_api, crear_cuenta, fecha):
    cuenta = await crear_cuenta()

    primera = await _reservar(cliente_api, cuenta, fecha)
    segunda = await _reservar(cliente_api, cuenta, fecha)
    tercera = await _reservar(cliente_api, cuenta, fecha)

    assert primera.status_code == 201
    cuerpo = primera.json()
    assert primera.headers["location"] == f"/v1/reservas/{cuerpo['id']}"
    assert (cuerpo["estado"], cuerpo["sala_nombre"]) == ("ACTIVA", "Sala 1")
    assert cuerpo["titular_id"] == cuerpo["creada_por_id"] == cuenta.id
    assert cuerpo["_links"]["cancelar"] == {
        "href": f"/v1/reservas/{cuerpo['id']}", "method": "PATCH", "body": {"estado": "CANCELADA"}
    }
    assert segunda.status_code == 201
    assert tercera.status_code == 409 
    assert tercera.json()["type"] == "/problemas/sin-puestos"


async def test_solo_el_administrador_reserva_para_otro(cliente_api, crear_cuenta, fecha):
    usuario = await crear_cuenta()
    otro = await crear_cuenta()
    administrador = await crear_cuenta("administrador")

    del_usuario = await _reservar(cliente_api, usuario, fecha, titular_id=otro.id)
    del_administrador = await _reservar(cliente_api, administrador, fecha, titular_id=usuario.id)

    assert del_usuario.status_code == 403
    assert del_administrador.status_code == 201
    assert del_administrador.json()["titular_id"] == usuario.id
    assert del_administrador.json()["creada_por_id"] == administrador.id


# --- Ver y cancelar ---

async def test_reserva_ajena_no_se_ve_ni_se_lista(cliente_api, crear_cuenta, fecha):
    duena = await crear_cuenta()
    otra = await crear_cuenta()
    reserva_id = (await _reservar(cliente_api, duena, fecha)).json()["id"]
    await _reservar(cliente_api, otra, fecha)

    ajena = await cliente_api.get(f"/v1/reservas/{reserva_id}", headers=otra.autorizacion)
    listado = await cliente_api.get("/v1/reservas", headers=duena.autorizacion)

    assert ajena.status_code == 404
    assert listado.json()["total"] == 1
    assert [item["id"] for item in listado.json()["items"]] == [reserva_id]


async def test_cancelar_es_idempotente_y_encola_una_sola_liberacion(
    cliente_api, crear_cuenta, fecha, app_iniciada
):
    cuenta = await crear_cuenta()
    reserva_id = (await _reservar(cliente_api, cuenta, fecha)).json()["id"]

    primera = await _cancelar(cliente_api, cuenta, reserva_id)
    segunda = await _cancelar(cliente_api, cuenta, reserva_id)

    assert primera.status_code == segunda.status_code == 200
    assert primera.json()["estado"] == "CANCELADA"
    assert primera.json()["cancelada_en"] is not None
    assert "cancelar" not in primera.json()["_links"]
    assert await _contar_liberaciones(app_iniciada, reserva_id=reserva_id) == 1


# Compensaciones

async def test_timeout_al_ocupar_responde_504_y_encola_la_liberacion(
    cliente_api, crear_cuenta, fecha, app_iniciada, monkeypatch
):
    cuenta = await crear_cuenta()
    referencias = _simular_timeout_al_ocupar(app_iniciada, monkeypatch)

    respuesta = await _reservar(cliente_api, cuenta, fecha)

    assert respuesta.status_code == 504
    assert await _contar_liberaciones(app_iniciada, referencia=referencias[0]) == 1
    async with app_iniciada.state.pool.connection() as conexion:
        await conexion.execute(
            "DELETE FROM liberaciones_pendientes WHERE referencia = %s", (referencias[0],)
        )


async def test_timeout_sin_poder_encolar_responde_504_y_lo_registra(
    cliente_api, crear_cuenta, fecha, app_iniciada, monkeypatch, caplog
):
    cuenta = await crear_cuenta()
    referencias = _simular_timeout_al_ocupar(app_iniciada, monkeypatch)

    async def encolar_con_falla(*args):
        raise RuntimeError("falla simulada al encolar")

    monkeypatch.setattr(persistencia_reservas, "encolar_liberacion", encolar_con_falla)

    respuesta = await _reservar(cliente_api, cuenta, fecha)

    assert respuesta.status_code == 504 
    assert referencias[0] in caplog.text


async def test_falla_al_guardar_responde_500_y_libera_el_puesto(
    cliente_api, crear_cuenta, fecha, app_iniciada, monkeypatch
):
    cuenta = await crear_cuenta()
    espacios = app_iniciada.state.espacios
    liberar_real = espacios.liberar_puesto
    liberadas: list[str] = []

    async def insertar_con_falla(*args):
        raise RuntimeError("falla simulada al guardar")

    async def liberar_espiado(referencia):
        liberadas.append(referencia)
        return await liberar_real(referencia) 

    monkeypatch.setattr(persistencia_reservas, "insertar", insertar_con_falla)
    monkeypatch.setattr(espacios, "liberar_puesto", liberar_espiado)

    respuesta = await _reservar(cliente_api, cuenta, fecha)

    assert respuesta.status_code == 500
    assert len(liberadas) == 1
