"""
Constantes y ayudas compartidas por las pruebas
"""

import os
import uuid
from datetime import date, time
from app.repositorio import Franja

DB_URL_PRUEBAS = os.environ.get(
    "ESPACIOS_DB_URL_PRUEBAS", "postgresql://espacios:espacios_dev@127.0.0.1:5433/espacios"
)
PREFIJO_REFERENCIA = "prueba-"
FECHA_FUTURA = date(2099, 3, 10)
FECHA_PASADA = date(2020, 3, 10)


def franja(fecha: date = FECHA_FUTURA, inicio: str = "09:00", fin: str = "10:00") -> Franja:
    return Franja(fecha, time.fromisoformat(inicio), time.fromisoformat(fin))


def nueva_referencia() -> str:
    return f"{PREFIJO_REFERENCIA}{uuid.uuid4()}"
