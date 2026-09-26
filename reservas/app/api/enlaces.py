from datetime import date
from urllib.parse import urlencode

from app.api.esquemas import Enlace


def ruta_usuario(usuario_id: int) -> str:
    return f"/v1/usuarios/{usuario_id}"


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

