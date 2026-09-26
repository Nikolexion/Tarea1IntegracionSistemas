from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic_core import PydanticCustomError

from app.auth.contrasenas import MAXIMO_BYTES_BCRYPT, excede_limite_bcrypt


Rol = Literal["usuario", "administrador"]
PATRON_HORA = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"

class Enlace(BaseModel):

    href: str
    method: Literal["GET", "POST", "PATCH"]
    body: dict[str, Any] | None = None  


class ConEnlaces(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enlaces: dict[str, Enlace] = Field(alias="_links")


class Listado(ConEnlaces):
    total: int
    limit: int
    offset: int

class Credenciales(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int

class UsuarioNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)
    rol: Rol | None = None 

    @field_validator("password")
    @classmethod
    def _maximo_72_bytes(cls, password: str) -> str:
        if excede_limite_bcrypt(password):
            raise PydanticCustomError(
                "contrasena_muy_larga",
                "La contraseña no puede superar {maximo} bytes en UTF-8; "
                "caracteres como 'ñ' ocupan 2 bytes.",
                {"maximo": MAXIMO_BYTES_BCRYPT},
            )
        return password


class Usuario(ConEnlaces):
    id: int
    nombre: str
    email: str
    rol: Rol
    creado_en: datetime


class ListaUsuarios(Listado):
    items: list[Usuario]

class Sala(BaseModel):
    id: int
    nombre: str
    capacidad: int


class FranjaDisponible(ConEnlaces):
    hora_inicio: str
    hora_fin: str
    puestos_libres: int


class SalaConDisponibilidad(Sala):
    franjas: list[FranjaDisponible]


class GrillaDisponibilidad(BaseModel):
    fecha: date
    salas: list[SalaConDisponibilidad]


class Disponibilidad(ConEnlaces):
    sala: Sala
    fecha: date
    hora_inicio: str
    hora_fin: str
    puestos_libres: int
