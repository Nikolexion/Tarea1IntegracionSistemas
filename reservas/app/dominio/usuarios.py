import logging

from psycopg import AsyncConnection

from app.auth.contrasenas import generar_hash, verificar_contrasena
from app.auth.tokens import ROL_ADMINISTRADOR, ROL_USUARIO, Identidad
from app.dominio.errores import CredencialesInvalidas, EmailYaRegistrado, NoEncontrado
from app.persistencia import usuarios
from app.persistencia.usuarios import UsuarioGuardado


logger = logging.getLogger(__name__)

async def registrar(
    conexion: AsyncConnection,
    nombre: str,
    email: str,
    contrasena: str,
    rol_pedido: str | None,
    quien_llama: Identidad | None,
) -> UsuarioGuardado:
    es_administrador = quien_llama is not None and quien_llama.rol == ROL_ADMINISTRADOR
    rol = rol_pedido if es_administrador and rol_pedido else ROL_USUARIO
    password_hash = await generar_hash(contrasena)
    return await usuarios.crear_usuario(conexion, nombre, email, password_hash, rol)

async def autenticar(conexion: AsyncConnection, email: str, contrasena: str) -> UsuarioGuardado:
    usuario = await usuarios.obtener_por_email(conexion, email)
    hash_guardado = usuario.password_hash if usuario else None
    if not await verificar_contrasena(contrasena, hash_guardado):
        raise CredencialesInvalidas()
    return usuario

async def obtener(
    conexion: AsyncConnection, usuario_id: int, quien_llama: Identidad
) -> UsuarioGuardado:
    usuario = None
    if quien_llama.usuario_id == usuario_id or quien_llama.rol == ROL_ADMINISTRADOR:
        usuario = await usuarios.obtener_por_id(conexion, usuario_id)
    if usuario is None:
        raise NoEncontrado(f"No existe un usuario con id {usuario_id}.")
    return usuario

async def crear_administrador_inicial(
    conexion: AsyncConnection, email: str | None, contrasena: str | None
) -> None:
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
        logger.warning("El email %s ya existe: no se crea el administrador inicial.", email)
        return
    logger.info("Administrador inicial creado (id=%s, email=%s).", usuario.id, usuario.email)
