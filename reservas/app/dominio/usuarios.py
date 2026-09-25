"""Reglas de las cuentas: administrador inicial (ADR-007)."""

import logging

from psycopg import AsyncConnection

from app.auth.contrasenas import generar_hash
from app.dominio.errores import EmailYaRegistrado
from app.persistencia import usuarios

logger = logging.getLogger(__name__)


# --- Administrador inicial (ADR-007, ADR-016) ---

async def crear_administrador_inicial(
    conexion: AsyncConnection, email: str | None, contrasena: str | None
) -> None:
    """Crea el primer administrador desde variables de entorno; si ya hay uno, no hace nada."""
    if not email or not contrasena:
        logger.warning(
            "Sin ADMIN_EMAIL_INICIAL o ADMIN_PASSWORD_INICIAL: no se crea el administrador inicial."
        )
        return
    if await usuarios.existe_administrador(conexion):
        logger.info("Ya existe un administrador: no se crea el administrador inicial.")
        return
    try:
        usuario = await usuarios.crear_usuario(
            conexion, "Administrador", email, await generar_hash(contrasena), "administrador"
        )
    except EmailYaRegistrado:
        # El email es de una cuenta de rol usuario: no se le cambia el rol en silencio.
        logger.warning("El email %s ya existe: no se crea el administrador inicial.", email)
        return
    logger.info("Administrador inicial creado (id=%s, email=%s).", usuario.id, usuario.email)
