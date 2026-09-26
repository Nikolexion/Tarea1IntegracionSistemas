class CredencialesInvalidas(Exception):
    """El email no existe o la contraseña no corresponde"""


class EmailYaRegistrado(Exception):
    pass


class SinPermiso(Exception):
    """La identidad es válida, pero su rol no permite la operación"""


class NoEncontrado(Exception):
    """El recurso no existe o no es de quien lo pide"""

class DatosInvalidos(Exception):
    """Un dato del cuerpo es válido en formato pero no en el negocio (p. ej. sala inexistente)"""


class SinPuestos(Exception):
    pass