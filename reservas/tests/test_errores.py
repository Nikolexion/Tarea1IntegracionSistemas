import pytest
from pydantic import BaseModel, EmailStr

from tests.conftest import crear_app, crear_cliente

TIPO_PROBLEMA = "application/problem+json"


class DatosDePrueba(BaseModel):
    email: EmailStr
    cantidad: int


@pytest.fixture
async def cliente():
    app = crear_app()

    @app.post("/prueba/validacion")
    async def validar(datos: DatosDePrueba):
        return {"ok": True}

    @app.get("/prueba/fallo")
    async def fallar():
        raise RuntimeError("detalle interno que no debe salir: password=secreta")

    async with crear_cliente(app) as cliente:
        yield cliente


async def test_validacion_responde_422_con_errores_por_campo(cliente):
    respuesta = await cliente.post(
        "/prueba/validacion", json={"email": "no-es-un-email", "cantidad": "muchos"}
    )

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == TIPO_PROBLEMA
    cuerpo = respuesta.json()
    assert cuerpo["type"] == "/problemas/datos-invalidos"
    assert cuerpo["instance"] == "/prueba/validacion"
    assert {error["campo"] for error in cuerpo["errores"]} == {"email", "cantidad"}


async def test_json_mal_formado_responde_400(cliente):
    respuesta = await cliente.post(
        "/prueba/validacion", content=b'{"email": ', headers={"Content-Type": "application/json"}
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["type"] == "/problemas/json-mal-formado"
    assert "errores" not in respuesta.json()


async def test_ruta_inexistente_responde_404_about_blank(cliente):
    respuesta = await cliente.get("/v1/nada")

    assert respuesta.headers["content-type"] == TIPO_PROBLEMA
    assert respuesta.json() == {
        "type": "about:blank", "title": "Not Found", "status": 404, "instance": "/v1/nada"
    }


async def test_error_no_controlado_responde_500_sin_detalles(cliente, caplog):
    respuesta = await cliente.get("/prueba/fallo")

    assert respuesta.status_code == 500
    assert respuesta.json()["title"] == "Internal Server Error"
    assert "secreta" not in respuesta.text
    assert "secreta" in caplog.text  # el detalle sí queda en el log
