from pathlib import Path

import pytest
import yaml

from tests.conftest import PASSWORD_PRUEBA, email_de_prueba


async def _registrar(cliente, headers=None, **cambios):
    datos = {"nombre": "Ana Pérez", "email": email_de_prueba(), "password": PASSWORD_PRUEBA}
    return await cliente.post("/v1/usuarios", json={**datos, **cambios}, headers=headers)



async def test_registro_publico_ignora_el_rol_pedido(cliente_api):
    respuesta = await _registrar(cliente_api, rol="administrador")

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["rol"] == "usuario"
    assert respuesta.headers["location"] == f"/v1/usuarios/{cuerpo['id']}"
    assert "password" not in respuesta.text


async def test_administrador_crea_otro_administrador(cliente_api, crear_cuenta):
    administrador = await crear_cuenta("administrador")

    respuesta = await _registrar(cliente_api, administrador.autorizacion, rol="administrador")

    assert respuesta.status_code == 201
    assert respuesta.json()["rol"] == "administrador"


async def test_email_repetido_con_otras_mayusculas_responde_409(cliente_api):
    email = email_de_prueba()
    await _registrar(cliente_api, email=email)

    respuesta = await _registrar(cliente_api, email=email.upper())

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "/problemas/email-registrado"


@pytest.mark.parametrize(
    ("password", "status"),
    [("12345678", 201), ("1234567", 422), ("ñ" * 36, 201), ("ñ" * 37, 422)],
    ids=["8-caracteres", "7-caracteres", "72-bytes", "74-bytes"],
)
async def test_largo_de_contrasena_entre_8_caracteres_y_72_bytes(cliente_api, password, status):
    respuesta = await _registrar(cliente_api, password=password)

    assert respuesta.status_code == status
    if status == 422:
        assert [error["campo"] for error in respuesta.json()["errores"]] == ["password"]



async def test_usuario_no_puede_listar_cuentas(cliente_api, crear_cuenta):
    usuario = await crear_cuenta()

    respuesta = await cliente_api.get("/v1/usuarios", headers=usuario.autorizacion)

    assert respuesta.status_code == 403
    assert respuesta.json()["type"] == "/problemas/sin-permiso"


async def test_administrador_lista_con_enlaces_de_paginacion(cliente_api, crear_cuenta):
    administrador = await crear_cuenta("administrador")
    for _ in range(2):
        await crear_cuenta()

    respuesta = await cliente_api.get(
        "/v1/usuarios?limit=1&offset=1", headers=administrador.autorizacion
    )

    cuerpo = respuesta.json()
    assert len(cuerpo["items"]) == 1
    assert "password_hash" not in cuerpo["items"][0]
    assert cuerpo["_links"] == {
        "self": {"href": "/v1/usuarios?limit=1&offset=1", "method": "GET"},
        "siguiente": {"href": "/v1/usuarios?limit=1&offset=2", "method": "GET"},
        "anterior": {"href": "/v1/usuarios?limit=1&offset=0", "method": "GET"},
    }


async def test_cuenta_ajena_responde_404(cliente_api, crear_cuenta):
    usuario = await crear_cuenta()
    otro = await crear_cuenta()

    respuesta = await cliente_api.get(f"/v1/usuarios/{otro.id}", headers=usuario.autorizacion)

    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "/problemas/no-encontrado"



async def test_openapi_json_sirve_el_contrato(cliente_api):
    ruta = Path(__file__).resolve().parents[2] / "contratos" / "openapi.yaml"
    with ruta.open(encoding="utf-8") as archivo:
        contrato = yaml.safe_load(archivo)

    respuesta = await cliente_api.get("/openapi.json")

    assert respuesta.json() == contrato
