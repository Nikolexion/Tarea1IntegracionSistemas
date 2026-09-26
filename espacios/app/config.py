"""Configuración del servicio, leída y validada al arrancar desde variables de entorno (ADR-016)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Configuracion:
    db_url: str
    puerto_grpc: int
    latencia_artificial_ms: int
    zona_horaria: str  # la valida PostgreSQL al arrancar (RepositorioEspacios.verificar_zona_horaria)

    @classmethod
    def desde_entorno(cls) -> "Configuracion":
        return cls(
            db_url=_leer_texto("ESPACIOS_DB_URL"),
            puerto_grpc=_leer_entero("ESPACIOS_PUERTO_GRPC", minimo=1),
            latencia_artificial_ms=_leer_entero("ESPACIOS_LATENCIA_ARTIFICIAL_MS", minimo=0),
            zona_horaria=_leer_texto("ESPACIOS_ZONA_HORARIA"),
        )


def _leer_texto(nombre: str) -> str:
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise ValueError(f"Falta la variable de entorno {nombre}")
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
