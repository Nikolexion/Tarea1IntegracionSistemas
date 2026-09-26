"""Recorrido del sistema completo, paso a paso (sirve también como ensayo del video).

Requiere el sistema levantado con `docker compose up -d --wait`. Uso:
    venv/Scripts/python.exe probar_sistema.py

Detiene Espacios a mitad del recorrido para mostrar el 503 y la cola de liberaciones (ADR-010), y
lo vuelve a iniciar al final. No deja reservas activas; sí deja la cuenta de demostración creada,
porque la API no permite borrar cuentas.
"""

import subprocess
import time
import uuid
from datetime import date, timedelta

import httpx

API = "http://localhost:8000"
SALA_ID = 1  # la semilla le da 2 puestos
FECHA = (date.today() + timedelta(days=30)).isoformat()


def paso(texto: str) -> None:
    print(f"\n=== {texto}")


def mostrar(respuesta: httpx.Response, detalle: str = "") -> None:
    if respuesta.is_error:  # los errores vienen como Problem Details (RFC 9457)
        detalle = respuesta.json().get("title", "")
    print(f"    {respuesta.request.method} {respuesta.request.url.path} -> {respuesta.status_code} {detalle}")


def docker_compose(*argumentos: str) -> None:
    print(f"    $ docker compose {' '.join(argumentos)}")
    subprocess.run(["docker", "compose", *argumentos], check=True, capture_output=True)


def puestos_libres(cliente: httpx.Client, hora_inicio: str) -> int:
    respuesta = cliente.get("/v1/salas", params={"fecha": FECHA})
    respuesta.raise_for_status()
    sala = next(s for s in respuesta.json()["salas"] if s["id"] == SALA_ID)
    return next(f["puestos_libres"] for f in sala["franjas"] if f["hora_inicio"] == hora_inicio)


def esperar_puestos(cliente: httpx.Client, hora_inicio: str, esperados: int) -> None:
    # La cola libera el puesto en segundo plano cada 5 s, así que se consulta hasta verlo.
    inicio = time.monotonic()
    while (libres := puestos_libres(cliente, hora_inicio)) != esperados:
        if time.monotonic() - inicio > 60:
            raise RuntimeError(f"Tras 60 s la franja sigue con {libres} puestos libres")
        print(f"    ... {libres} puestos libres, esperando a la cola")
        time.sleep(2)
    print(f"    Franja {hora_inicio}: {libres} puestos libres (tras {time.monotonic() - inicio:.0f} s)")


def main() -> None:
    cliente = httpx.Client(base_url=API, timeout=30)
    reservas: list[int] = []
    try:
        paso("1. Registrar un usuario nuevo")
        email = f"demo-{uuid.uuid4().hex[:8]}@example.com"
        credenciales = {"email": email, "password": "demo-contrasena"}
        respuesta = cliente.post("/v1/usuarios", json={"nombre": "Demo", **credenciales})
        mostrar(respuesta, f"cuenta {email}, rol {respuesta.json().get('rol')}")
        respuesta.raise_for_status()

        paso("2. Iniciar sesión")
        respuesta = cliente.post("/v1/auth/login", json=credenciales)
        respuesta.raise_for_status()
        cliente.headers["Authorization"] = f"Bearer {respuesta.json()['access_token']}"
        mostrar(respuesta, "token JWT recibido")

        paso(f"3. Consultar la grilla del {FECHA}")
        respuesta = cliente.get("/v1/salas", params={"fecha": FECHA})
        respuesta.raise_for_status()
        mostrar(respuesta)
        for sala in respuesta.json()["salas"]:
            libres = [f["puestos_libres"] for f in sala["franjas"]]
            print(f"    {sala['nombre']} (capacidad {sala['capacidad']}): libres por franja {libres}")
        sala = next(s for s in respuesta.json()["salas"] if s["id"] == SALA_ID)
        # Una franja sin reservas previas, para que el recorrido sea el mismo en cada ejecución.
        franja = next(
            (f for f in sala["franjas"] if f["puestos_libres"] == sala["capacidad"]), None
        )
        if franja is None:
            raise RuntimeError(f"La {sala['nombre']} no tiene franjas vacías el {FECHA}")
        hora = franja["hora_inicio"]
        cuerpo = {"sala_id": SALA_ID, "fecha": FECHA, "hora_inicio": hora, "hora_fin": franja["hora_fin"]}

        paso(f"4. Reservar en {sala['nombre']} de {hora} a {franja['hora_fin']} hasta llenarla")
        for _ in range(sala["capacidad"] + 1):
            respuesta = cliente.post("/v1/reservas", json=cuerpo)
            if respuesta.status_code == 201:
                reservas.append(respuesta.json()["id"])
                mostrar(respuesta, f"reserva {reservas[-1]} ACTIVA")
            else:
                mostrar(respuesta)
                break
        if respuesta.status_code != 409 or len(reservas) != sala["capacidad"]:
            raise RuntimeError("Se esperaba llenar la sala y recibir un 409")

        paso(f"5. Cancelar la reserva {reservas[0]} (el puesto se libera vía la cola)")
        mostrar(cancelar(cliente, reservas[0]), "CANCELADA")
        esperar_puestos(cliente, hora, 1)

        paso("6. Detener Espacios")
        docker_compose("stop", "espacios")

        paso("7. Intentar reservar con Espacios caído")
        respuesta = cliente.post("/v1/reservas", json=cuerpo)
        mostrar(respuesta)
        print(f"    Retry-After: {respuesta.headers.get('Retry-After')}")

        paso(f"8. Cancelar la reserva {reservas[1]} con Espacios caído (queda en la cola)")
        mostrar(cancelar(cliente, reservas[1]), "CANCELADA")

        paso("9. Iniciar Espacios de nuevo y esperar a que la cola procese")
        docker_compose("start", "espacios")
        esperar_puestos(cliente, hora, 2)

        paso("10. Mis reservas")
        respuesta = cliente.get("/v1/reservas")
        mostrar(respuesta)
        for reserva in respuesta.json()["items"]:
            print(f"    reserva {reserva['id']}: {reserva['estado']}")
        print("\nRecorrido completo.")
    finally:
        # Deja el sistema como estaba aunque algún paso falle.
        subprocess.run(["docker", "compose", "start", "espacios"], capture_output=True)
        for reserva_id in reservas:
            cancelar(cliente, reserva_id)  # idempotente: si ya estaba cancelada, no cambia nada


def cancelar(cliente: httpx.Client, reserva_id: int) -> httpx.Response:
    return cliente.patch(
        f"/v1/reservas/{reserva_id}",
        content='{"estado": "CANCELADA"}',
        headers={"Content-Type": "application/merge-patch+json"},
    )


if __name__ == "__main__":
    main()
