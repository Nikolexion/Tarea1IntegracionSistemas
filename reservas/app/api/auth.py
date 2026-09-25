from fastapi import APIRouter, Request

from app.api.esquemas import Credenciales, Token
from app.auth.tokens import emitir_token
from app.dominio import usuarios as dominio_usuarios
from app.persistencia.conexion import Conexion

router = APIRouter(prefix="/v1/auth", tags=["Autenticación"])

@router.post("/login")
async def iniciar_sesion(datos: Credenciales, request: Request, conexion: Conexion) -> Token:
    usuario = await dominio_usuarios.autenticar(conexion, datos.email, datos.password)
    configuracion = request.app.state.configuracion
    minutos = configuracion.jwt_minutos_validez
    token = emitir_token(usuario.id, usuario.rol, configuracion.jwt_secreto, minutos)
    return Token(access_token=token, expires_in=minutos * 60)
