from datetime import date
from urllib.parse import urlencode

from app.api.esquemas import Enlace
from app.persistencia.reservas import ReservaGuardada

def ruta_usuario(usuario_id: int) -> str:
    return f"/v1/usuarios/{usuario_id}"

def ruta_reserva(reserva_id: int) -> str:
    return f"/v1/reservas/{reserva_id}"

def ruta_disponibilidad(sala_id: int, fecha: date, hora_inicio: str, hora_fin: str) -> str:
    consulta = urlencode(
        {"fecha": fecha.isoformat(), "hora_inicio": hora_inicio, "hora_fin": hora_fin},
        safe=":",  
    )
    return f"/v1/salas/{sala_id}/disponibilidad?{consulta}"


def enlace_reservar(
    sala_id: int, fecha: date, hora_inicio: str, hora_fin: str, puestos_libres: int, iniciada: bool
) -> dict[str, Enlace]:
    if puestos_libres <= 0 or iniciada:
        return {}
    cuerpo = {"sala_id": sala_id, "fecha": fecha.isoformat(), "hora_inicio": hora_inicio,
              "hora_fin": hora_fin}
    return {"reservar": Enlace(href="/v1/reservas", method="POST", body=cuerpo)}

def enlaces_reserva(reserva: ReservaGuardada) -> dict[str, Enlace]:
    ruta_sala = ruta_disponibilidad(
        reserva.sala_id, reserva.fecha, reserva.hora_inicio, reserva.hora_fin
    )
    return {
        "self": Enlace(href=ruta_reserva(reserva.id), method="GET"),
        "sala": Enlace(href=ruta_sala, method="GET"),
    }
