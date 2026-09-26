"""Excepciones del dominio; app/api/errores.py las traduce a Problem Details"""


class CredencialesInvalidas(Exception):
    """El email no existe o la contraseña no corresponde; nunca se dice cuál de los dos."""


class EmailYaRegistrado(Exception):
    pass


class SinPermiso(Exception):
    """La identidad es válida, pero su rol no permite la operación."""


class NoEncontrado(Exception):
    """El recurso no existe o no es de quien lo pide (ADR-007: ajeno → no encontrado)."""


class DatosInvalidos(Exception):
    """Un dato del cuerpo es válido en formato pero no en el negocio (p. ej. sala inexistente)."""


class SinPuestos(Exception):
    pass


class IdempotenciaReutilizada(Exception):
    """La misma Idempotency-Key llegó con un cuerpo distinto."""


class IdempotenciaEnCurso(Exception):
    """La primera petición con esa Idempotency-Key todavía no termina."""
