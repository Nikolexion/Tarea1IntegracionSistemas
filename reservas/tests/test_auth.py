import base64
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from tests.conftest import PASSWORD_PRUEBA, SECRETO_PRUEBAS, email_de_prueba


async def _login(cliente, email, password):
    return await cliente.post("/v1/auth/login", json={"email": email, "password": password})


def _token_manipulado(token: str) -> str:
    """Cambia el rol a administrador y conserva la firma original"""
    encabezado, _, firma = token.split(".")
    claims = {**jwt.decode(token, options={"verify_signature": False}), "rol": "administrador"}
    contenido = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{encabezado}.{contenido}.{firma}"


def _token_expirado(token: str) -> str:
    hace_dos_horas = datetime.now(timezone.utc) - timedelta(hours=2)
    claims = {"sub": "1", "rol": "usuario", "iat": hace_dos_horas, "exp": hace_dos_horas}
    return jwt.encode(claims, SECRETO_PRUEBAS, algorithm="HS256")


def _token_sin_firma(token: str) -> str:
    """Ataque de confusión de algoritmos"""
    ahora = datetime.now(timezone.utc)
    claims = {"sub": "1", "rol": "administrador", "iat": ahora, "exp": ahora + timedelta(hours=1)}
    return jwt.encode(claims, None, algorithm="none")


async def test_login_correcto_entrega_token_con_los_claims_esperados(cliente_api, crear_cuenta):
    cuenta = await crear_cuenta()

    respuesta = await _login(cliente_api, cuenta.email.upper(), PASSWORD_PRUEBA)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["token_type"], cuerpo["expires_in"]) == ("Bearer", 3600)
    claims = jwt.decode(cuerpo["access_token"], SECRETO_PRUEBAS, algorithms=["HS256"])
    assert set(claims) == {"sub", "rol", "iat", "exp"}
    assert (claims["sub"], claims["rol"]) == (str(cuenta.id), "usuario")


async def test_login_fallido_responde_igual_exista_o_no_el_email(cliente_api, crear_cuenta):
    cuenta = await crear_cuenta()

    contrasena_incorrecta = await _login(cliente_api, cuenta.email, "otra-contrasena")
    email_inexistente = await _login(cliente_api, email_de_prueba(), PASSWORD_PRUEBA)

    assert contrasena_incorrecta.status_code == email_inexistente.status_code == 401
    assert contrasena_incorrecta.json() == email_inexistente.json()
    assert contrasena_incorrecta.json()["type"] == "/problemas/credenciales-invalidas"
    assert email_inexistente.headers["www-authenticate"] == "Bearer"


async def test_sin_token_responde_401_con_www_authenticate(cliente_api):
    respuesta = await cliente_api.get("/v1/usuarios/me")

    assert respuesta.status_code == 401
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.headers["www-authenticate"] == "Bearer"
    assert respuesta.json()["type"] == "/problemas/no-autenticado"


@pytest.mark.parametrize("alterar", [_token_manipulado, _token_expirado, _token_sin_firma])
async def test_token_no_valido_responde_401(cliente_api, crear_cuenta, alterar):
    cuenta = await crear_cuenta()
    token = alterar(cuenta.token)

    respuesta = await cliente_api.get("/v1/usuarios", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == 'Bearer error="invalid_token"'
