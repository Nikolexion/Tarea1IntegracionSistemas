from dataclasses import dataclass
from datetime import datetime

from psycopg import AsyncConnection
from psycopg.rows import class_row

from app.dominio.errores import EmailYaRegistrado


@dataclass(frozen=True)
class UsuarioGuardado:
    id: int
    nombre: str
    email: str
    password_hash: str
    rol: str
    creado_en: datetime


_COLUMNAS = "id, nombre, email, password_hash, rol, creado_en"


async def crear_usuario(
    conexion: AsyncConnection, nombre: str, email: str, password_hash: str, rol: str
) -> UsuarioGuardado:
    """Inserta el usuario con el email en minúsculas; lanza EmailYaRegistrado si ya existe."""
    cursor = conexion.cursor(row_factory=class_row(UsuarioGuardado))
    await cursor.execute(
        f"""
        INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)
        ON CONFLICT (email) DO NOTHING
        RETURNING {_COLUMNAS}
        """,
        (nombre, email.lower(), password_hash, rol),
    )
    usuario = await cursor.fetchone()
    if usuario is None:
        raise EmailYaRegistrado(email.lower())
    return usuario


async def existe_administrador(conexion: AsyncConnection) -> bool:
    cursor = await conexion.execute(
        "SELECT EXISTS (SELECT 1 FROM usuarios WHERE rol = 'administrador')"
    )
    (existe,) = await cursor.fetchone()
    return existe


async def obtener_por_email(conexion: AsyncConnection, email: str) -> UsuarioGuardado | None:
    cursor = conexion.cursor(row_factory=class_row(UsuarioGuardado))
    await cursor.execute(f"SELECT {_COLUMNAS} FROM usuarios WHERE email = %s", (email.lower(),))
    return await cursor.fetchone()
