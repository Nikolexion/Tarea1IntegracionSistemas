from psycopg_pool import AsyncConnectionPool

ESPERA_APERTURA_SEGUNDOS = 10 
MAXIMO_CONEXIONES = 10


async def abrir_pool(url_base: str) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(
        conninfo=url_base,
        open=False,
        max_size=MAXIMO_CONEXIONES,
    )
    await pool.open(wait=True, timeout=ESPERA_APERTURA_SEGUNDOS)
    return pool
