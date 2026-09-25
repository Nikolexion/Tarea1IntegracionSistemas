'''
Configuración del servicio de Espacios
'''

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    db_url: str
    zona_horaria: str # la valida postgreSQL al arrancar 

    @classmethod
    def desde_entorno(cls) -> "Config":
        return cls(
            db_url=_leer_texto("ESPACIOS_DB_URL"),
            zona_horaria=_leer_texto("ESPACIOS_ZONA_HORARIA"),
        )

def _leer_texto(nombre: str) -> str:
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise ValueError(f"Falta variable de entorno {nombre}")
    return valor
