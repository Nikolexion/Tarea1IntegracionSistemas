"""Prueba de contrato (O4, ADR-011): la API expone exactamente las rutas y métodos del openapi.yaml.

Compara en ambos sentidos. No valida esquemas de respuesta (ADR-011).
"""

from fastapi.openapi.utils import get_openapi

from app.main import contrato_openapi, crear_app

METODOS_HTTP = {"get", "post", "put", "patch", "delete"}


def operaciones(esquema: dict) -> set[tuple[str, str]]:
    return {
        (metodo.upper(), ruta)
        for ruta, detalle in esquema["paths"].items()
        for metodo in detalle
        if metodo in METODOS_HTTP
    }


def operaciones_de_la_app() -> set[tuple[str, str]]:
    # `app.openapi` devuelve el contrato escrito (ADR-018), así que se genera el esquema desde el
    # código. Deja fuera /docs, /openapi.json y las demás rutas internas de FastAPI.
    app = crear_app()
    return operaciones(get_openapi(title=app.title, version=app.version, routes=app.routes))


def test_la_app_no_expone_operaciones_fuera_del_contrato():
    sobrantes = operaciones_de_la_app() - operaciones(contrato_openapi())
    assert not sobrantes, f"La app expone operaciones que no están en openapi.yaml: {sorted(sobrantes)}"


def test_la_app_implementa_todas_las_operaciones_del_contrato():
    faltantes = operaciones(contrato_openapi()) - operaciones_de_la_app()
    assert not faltantes, f"Operaciones de openapi.yaml que la app no implementa: {sorted(faltantes)}"
