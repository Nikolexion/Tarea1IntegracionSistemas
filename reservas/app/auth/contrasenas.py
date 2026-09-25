import asyncio
from functools import cache

import bcrypt

MAXIMO_BYTES_BCRYPT = 72 


def excede_limite_bcrypt(contrasena: str) -> bool:
    return len(contrasena.encode("utf-8")) > MAXIMO_BYTES_BCRYPT

async def generar_hash(contrasena: str) -> str:
    return await asyncio.to_thread(_hashear, contrasena)


async def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    return await asyncio.to_thread(_coincide, contrasena, hash_guardado)


def _hashear(contrasena: str) -> str:
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def _coincide(contrasena: str, hash_guardado: str) -> bool:
    if excede_limite_bcrypt(contrasena):
        return False  
    hash_a_comparar = hash_guardado or _hash_de_relleno()
    coincide = bcrypt.checkpw(contrasena.encode("utf-8"), hash_a_comparar.encode("ascii"))
    return coincide and hash_guardado is not None

@cache
def _hash_de_relleno() -> str:
    return _hashear("contrasena-de-relleno-para-igualar-tiempos")
