'''
Configuración del servicio de Espacios
'''

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    db_url: str
    puerto_grpc: int
    zona_horaria: str # la valida postgreSQL al arrancar 

    @classmethod
    def desde_entorno(cls) -> "Config":
        return cls(
            db_url=_leer_texto("ESPACIOS_DB_URL"),
            puerto_grpc=_leer_entero("ESPACIOS_PUERTO_GRPC", minimo=1),
            zona_horaria=_leer_texto("ESPACIOS_ZONA_HORARIA"),
        )

def _leer_texto(nombre: str) -> str:
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise ValueError(f"Falta variable de entorno {nombre}")
    return valor

def _leer_entero(nombre: str, minimo: int) -> int:
    texto = _leer_texto(nombre)
    try:
        valor = int(texto)
    except ValueError:
        raise ValueError(f"{nombre} debe ser un número entero, no {texto!r}") from None
    if valor < minimo:
        raise ValueError(f"{nombre} debe ser mayor o igual a {minimo}")
    return valor