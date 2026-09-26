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
    admin_email_inicial: str | None 
    admin_password_inicial: str | None


class ConfiguracionInvalida(Exception):
    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__("Configuración inválida: " + "; ".join(errores))


def cargar_configuracion(entorno: Mapping[str, str] | None = None) -> Configuracion:
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
    
    configuracion = Configuracion(
        reservas_db_url=obligatoria("RESERVAS_DB_URL"),
        espacios_direccion=obligatoria("ESPACIOS_DIRECCION"),
        espacios_deadline_ms=entero_positivo("ESPACIOS_DEADLINE_MS"),
        jwt_secreto=obligatoria("JWT_SECRET"),
        jwt_minutos_validez=entero_positivo("JWT_MINUTOS_VALIDEZ"),
        redis_url=obligatoria("REDIS_URL"),
        admin_email_inicial=opcional("ADMIN_EMAIL_INICIAL"),
        admin_password_inicial=opcional("ADMIN_PASSWORD_INICIAL"),
    )
    if errores:
        raise ConfiguracionInvalida(errores)
    return configuracion
