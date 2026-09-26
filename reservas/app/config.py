"""Configuración leída y validada una sola vez desde variables de entorno"""

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Configuracion:
    reservas_db_url: str
    espacios_direccion: str
    espacios_deadline_ms: int
    jwt_secreto: str
    jwt_minutos_validez: int
    redis_url: str
    cache_ttl_segundos: int  # 0 desactiva la caché
    admin_email_inicial: str | None  # opcionales: sin ellas no se crea el administrador inicial
    admin_password_inicial: str | None


class ConfiguracionInvalida(Exception):
    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__("Configuración inválida: " + "; ".join(errores))


def cargar_configuracion(entorno: Mapping[str, str] | None = None) -> Configuracion:
    """Lee `entorno` (por defecto `os.environ`) y reúne todos los errores antes de fallar."""
    entorno = os.environ if entorno is None else entorno
    errores: list[str] = []

    def opcional(nombre: str) -> str | None:
        return entorno.get(nombre, "").strip() or None

    def obligatoria(nombre: str) -> str:
        valor = opcional(nombre)
        if valor is None:
            errores.append(f"falta la variable {nombre}")
        return valor or ""

    def entero_positivo(nombre: str) -> int:
        texto = obligatoria(nombre)
        if texto and (not texto.isdigit() or int(texto) <= 0):
            errores.append(f"{nombre} debe ser un entero positivo (valor actual: {texto!r})")
            return 0
        return int(texto or 0)

    def entero_no_negativo(nombre: str, por_defecto: int) -> int:
        texto = opcional(nombre)
        if texto is None:
            return por_defecto
        if not texto.isdigit():
            errores.append(f"{nombre} debe ser un entero >= 0 (valor actual: {texto!r})")
            return por_defecto
        return int(texto)

    configuracion = Configuracion(
        reservas_db_url=obligatoria("RESERVAS_DB_URL"),
        espacios_direccion=obligatoria("ESPACIOS_DIRECCION"),
        espacios_deadline_ms=entero_positivo("ESPACIOS_DEADLINE_MS"),
        jwt_secreto=obligatoria("JWT_SECRETO"),
        jwt_minutos_validez=entero_positivo("JWT_MINUTOS_VALIDEZ"),
        redis_url=obligatoria("REDIS_URL"),
        cache_ttl_segundos=entero_no_negativo("CACHE_TTL_SEGUNDOS", por_defecto=30),
        admin_email_inicial=opcional("ADMIN_EMAIL_INICIAL"),
        admin_password_inicial=opcional("ADMIN_PASSWORD_INICIAL"),
    )
    if errores:
        raise ConfiguracionInvalida(errores)
    return configuracion
