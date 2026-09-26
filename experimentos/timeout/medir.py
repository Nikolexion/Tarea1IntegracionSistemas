"""Experimento de timeout: tiempo de respuesta de GET /v1/salas según la latencia de Espacios y el
deadline de Reservas. Uso, con el sistema levantado: python experimentos/timeout/medir.py
"""

import asyncio
import csv
import os
import platform
import statistics
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parents[2]
RESULTADOS = Path(__file__).resolve().parent / "resultados"
API = "http://localhost:8000"

LATENCIAS_ESPACIOS_MS = [0, 250, 500, 750, 1000, 1500, 2000]
DEADLINES_MS = [500, 1000, 30000]  # 30 000 ms hace de "sin timeout"
CORRIDAS = 3
PETICIONES = 200
CALENTAMIENTO = 10  # se descartan: incluyen abrir el canal gRPC tras el reinicio
CONCURRENCIA = 10
FECHA = (date.today() + timedelta(days=30)).isoformat()


def docker_compose(*argumentos: str, entorno: dict[str, str] | None = None) -> str:
    resultado = subprocess.run(
        ["docker", "compose", *argumentos],
        cwd=RAIZ, env=entorno, check=True, capture_output=True, text=True,
    )
    return resultado.stdout.strip()


def reiniciar_servicios(latencia_ms: int, deadline_ms: int) -> None:
    # Las variables del proceso tienen prioridad sobre el .env en la interpolación del compose.
    entorno = os.environ | {
        "ESPACIOS_LATENCIA_ARTIFICIAL_MS": str(latencia_ms),
        "ESPACIOS_DEADLINE_MS": str(deadline_ms),
        "CACHE_TTL_SEGUNDOS": "0",  # sin caché, cada petición llega a Espacios
    }
    docker_compose(
        "up", "-d", "--wait", "--force-recreate", "--no-deps", "espacios", "reservas",
        entorno=entorno,
    )


def credenciales_admin() -> dict[str, str]:
    valores = {}
    for linea in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.startswith("#"):
            nombre, valor = linea.split("=", 1)
            valores[nombre.strip()] = valor.strip()
    return {"email": valores["ADMIN_EMAIL_INICIAL"], "password": valores["ADMIN_PASSWORD_INICIAL"]}


async def medir_corrida(cliente: httpx.AsyncClient) -> list[tuple[int, float]]:
    """Hace CALENTAMIENTO + PETICIONES consultas con CONCURRENCIA en paralelo; devuelve
    (status, duración en ms) de las que no son de calentamiento."""
    pendientes = iter(range(CALENTAMIENTO + PETICIONES))
    mediciones: list[tuple[int, float]] = []

    async def trabajador() -> None:
        for numero in pendientes:  # el iterador compartido reparte las peticiones
            inicio = time.perf_counter()
            respuesta = await cliente.get("/v1/salas", params={"fecha": FECHA})
            duracion_ms = (time.perf_counter() - inicio) * 1000
            if numero >= CALENTAMIENTO:
                mediciones.append((respuesta.status_code, duracion_ms))

    await asyncio.gather(*(trabajador() for _ in range(CONCURRENCIA)))
    return mediciones


async def medir_combinacion(latencia_ms: int, deadline_ms: int) -> list[list]:
    async with httpx.AsyncClient(base_url=API, timeout=60) as cliente:
        login = await cliente.post("/v1/auth/login", json=credenciales_admin())
        login.raise_for_status()
        cliente.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        filas = []
        for corrida in range(1, CORRIDAS + 1):
            for status, duracion_ms in await medir_corrida(cliente):
                filas.append([corrida, latencia_ms, deadline_ms, status, round(duracion_ms, 1)])
        return filas


def resumir(filas: list[list]) -> list:
    duraciones = [fila[4] for fila in filas]
    percentiles = statistics.quantiles(duraciones, n=100)
    n = len(filas)
    return [
        filas[0][1], filas[0][2],
        round(percentiles[49], 1), round(percentiles[94], 1),
        round(100 * sum(fila[3] == 200 for fila in filas) / n, 1),
        round(100 * sum(fila[3] == 504 for fila in filas) / n, 1),
        n,
    ]


def guardar_entorno() -> None:
    # La RAM y los CPU relevantes son los de la máquina virtual de Docker, donde corren los servicios.
    lineas = [
        f"Fecha de la medición: {date.today().isoformat()}",
        f"Sistema operativo: {platform.platform()}",
        f"CPU: {platform.processor()} ({os.cpu_count()} hilos lógicos)",
        f"Python: {platform.python_version()}",
        f"Docker: {subprocess.run(['docker', '--version'], capture_output=True, text=True).stdout.strip()}",
        "Recursos de Docker: " + subprocess.run(
            ["docker", "info", "--format", "{{.NCPU}} CPU, {{.MemTotal}} bytes de RAM, {{.OperatingSystem}}"],
            capture_output=True, text=True,
        ).stdout.strip(),
        f"Variables controladas: {CORRIDAS} corridas x {PETICIONES} peticiones, "
        f"{CALENTAMIENTO} de calentamiento descartadas por corrida, {CONCURRENCIA} concurrentes, "
        "CACHE_TTL_SEGUNDOS=0",
    ]
    (RESULTADOS / "entorno.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> None:
    RESULTADOS.mkdir(exist_ok=True)
    guardar_entorno()
    mediciones, resumen = [], []
    try:
        for deadline_ms in DEADLINES_MS:
            for latencia_ms in LATENCIAS_ESPACIOS_MS:
                print(f"Latencia de Espacios {latencia_ms} ms, deadline {deadline_ms} ms ...", flush=True)
                reiniciar_servicios(latencia_ms, deadline_ms)
                filas = asyncio.run(medir_combinacion(latencia_ms, deadline_ms))
                mediciones += filas
                resumen.append(resumir(filas))
                print(f"    p50 {resumen[-1][2]} ms, p95 {resumen[-1][3]} ms, "
                      f"{resumen[-1][4]} % 200, {resumen[-1][5]} % 504", flush=True)
    finally:
        print("Restaurando la configuración normal ...")
        docker_compose("up", "-d", "--wait")
        # nginx resuelve la IP de `reservas` al arrancar; tras recrear el contenedor puede cambiar.
        docker_compose("restart", "frontend")

    with open(RESULTADOS / "mediciones.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["corrida", "latencia_espacios_ms", "deadline_ms", "status", "duracion_ms"])
        escritor.writerows(mediciones)
    with open(RESULTADOS / "resumen.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(
            ["latencia_espacios_ms", "deadline_ms", "p50_ms", "p95_ms", "porcentaje_200", "porcentaje_504", "n"]
        )
        escritor.writerows(resumen)
    print(f"Resultados en {RESULTADOS}")


if __name__ == "__main__":
    main()
