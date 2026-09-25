"""Hash y verificación de contraseñas con bcrypt (ADR-005, ADR-018)."""

import asyncio

import bcrypt


# bcrypt es lento a propósito: se ejecuta en un hilo aparte para no congelar el bucle de eventos
# y con él todas las peticiones (ADR-015).

async def generar_hash(contrasena: str) -> str:
    return await asyncio.to_thread(_hashear, contrasena)


async def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    return await asyncio.to_thread(_coincide, contrasena, hash_guardado)


def _hashear(contrasena: str) -> str:
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def _coincide(contrasena: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(contrasena.encode("utf-8"), hash_guardado.encode("ascii"))
