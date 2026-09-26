from datetime import date, timedelta

FECHA_FUTURA = (date.today() + timedelta(days=30)).isoformat()
FECHA_PASADA = (date.today() - timedelta(days=1)).isoformat()


async def test_grilla_agrupa_por_sala_y_ofrece_reservar_solo_en_franjas_futuras(
    cliente_api, crear_cuenta
):
    cuenta = await crear_cuenta()

    futura = await cliente_api.get(
        "/v1/salas", params={"fecha": FECHA_FUTURA}, headers=cuenta.autorizacion
    )
    pasada = await cliente_api.get(
        "/v1/salas", params={"fecha": FECHA_PASADA}, headers=cuenta.autorizacion
    )

    salas = futura.json()["salas"]
    assert [sala["id"] for sala in salas] == [1, 2, 3, 4]
    assert all(len(sala["franjas"]) == 12 for sala in salas)
    assert salas[0]["franjas"][0]["_links"]["reservar"] == {
        "href": "/v1/reservas",
        "method": "POST",
        "body": {"sala_id": 1, "fecha": FECHA_FUTURA, "hora_inicio": "08:00", "hora_fin": "09:00"},
    }
    franjas_pasadas = [franja for sala in pasada.json()["salas"] for franja in sala["franjas"]]
    assert all(franja["_links"] == {} for franja in franjas_pasadas)


async def test_consulta_de_una_sala_con_self_y_reservar(cliente_api, crear_cuenta):
    cuenta = await crear_cuenta()
    parametros = {"fecha": FECHA_FUTURA, "hora_inicio": "09:00", "hora_fin": "10:00"}

    respuesta = await cliente_api.get(
        "/v1/salas/1/disponibilidad", params=parametros, headers=cuenta.autorizacion
    )

    enlaces = respuesta.json()["_links"]
    assert enlaces["self"]["href"] == (
        f"/v1/salas/1/disponibilidad?fecha={FECHA_FUTURA}&hora_inicio=09:00&hora_fin=10:00"
    )
    assert enlaces["reservar"]["body"] == {"sala_id": 1, **parametros}
