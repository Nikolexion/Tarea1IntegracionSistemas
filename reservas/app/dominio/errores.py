class CredencialesInvalidas(Exception):
    """El email no existe o la contraseña no corresponde."""


class EmailYaRegistrado(Exception):
    pass


class SinPermiso(Exception):
    """La identidad es válida, pero su rol no permite la operación."""


class NoEncontrado(Exception):
    """El recurso no existe o no es de quien lo pide."""