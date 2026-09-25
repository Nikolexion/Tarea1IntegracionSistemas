from typing import Literal

from pydantic import BaseModel, EmailStr

class Credenciales(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
