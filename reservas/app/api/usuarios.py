from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Path, Request, Response

from app.api.enlaces import ruta_usuario
from app.api.esquemas import Enlace, ListaUsuarios, Usuario, UsuarioNuevo
from app.api.paginacion import ParametrosPagina, sobre_pagina
from app.auth.dependencias import Administrador, IdentidadObligatoria, IdentidadOpcional
from app.dominio import usuarios as dominio_usuarios
from app.persistencia import usuarios as persistencia_usuarios
from app.persistencia.conexion import Conexion
from app.persistencia.usuarios import UsuarioGuardado

router = APIRouter(prefix="/v1/usuarios", tags=["Usuarios"])


def a_respuesta(usuario: UsuarioGuardado) -> Usuario:
    enlaces = {"self": Enlace(href=ruta_usuario(usuario.id), method="GET")}
    return Usuario(**asdict(usuario), enlaces=enlaces)


@router.post("", status_code=201, response_model_exclude_none=True)
async def registrar_usuario(
    datos: UsuarioNuevo, response: Response, quien_llama: IdentidadOpcional, conexion: Conexion
) -> Usuario:
    usuario = await dominio_usuarios.registrar(
        conexion, datos.nombre, datos.email, datos.password, datos.rol, quien_llama
    )
    response.headers["Location"] = ruta_usuario(usuario.id)
    return a_respuesta(usuario)


@router.get("", response_model_exclude_none=True)
async def listar_usuarios(
    request: Request, _administrador: Administrador, pagina: ParametrosPagina, conexion: Conexion
) -> ListaUsuarios:
    filas, total = await persistencia_usuarios.listar(conexion, pagina.limit, pagina.offset)
    items = [a_respuesta(fila) for fila in filas]
    return ListaUsuarios(**sobre_pagina(items, total, pagina, request.url.path))


@router.get("/me", response_model_exclude_none=True)
async def obtener_usuario_actual(identidad: IdentidadObligatoria, conexion: Conexion) -> Usuario:
    return a_respuesta(await dominio_usuarios.obtener(conexion, identidad.usuario_id, identidad))


@router.get("/{usuario_id}", response_model_exclude_none=True)
async def obtener_usuario(
    usuario_id: Annotated[int, Path(ge=1)], identidad: IdentidadObligatoria, conexion: Conexion
) -> Usuario:
    return a_respuesta(await dominio_usuarios.obtener(conexion, usuario_id, identidad))
