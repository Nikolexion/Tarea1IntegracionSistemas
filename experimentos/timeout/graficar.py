"""Gráficos del experimento de timeout a partir de resultados/resumen.csv (lo genera medir.py).

Uso: venv/Scripts/python.exe experimentos/timeout/graficar.py
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # solo genera archivos, sin abrir ventanas
import matplotlib.pyplot as plt  # noqa: E402

RESULTADOS = Path(__file__).resolve().parent / "resultados"


def leer_resumen() -> dict[int, list[dict]]:
    """Filas del resumen agrupadas por deadline."""
    por_deadline: dict[int, list[dict]] = {}
    with open(RESULTADOS / "resumen.csv", encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            por_deadline.setdefault(int(fila["deadline_ms"]), []).append(fila)
    return por_deadline


def nombre_deadline(deadline_ms: int) -> str:
    return "sin timeout (30 000 ms)" if deadline_ms >= 30000 else f"deadline {deadline_ms} ms"


def graficar_latencia(por_deadline: dict[int, list[dict]]) -> None:
    fig, eje = plt.subplots(figsize=(8, 5))
    for deadline_ms, filas in por_deadline.items():
        x = [int(f["latencia_espacios_ms"]) for f in filas]
        linea, = eje.plot(x, [float(f["p50_ms"]) for f in filas], marker="o",
                          label=f"p50, {nombre_deadline(deadline_ms)}")
        eje.plot(x, [float(f["p95_ms"]) for f in filas], marker="s", linestyle="--",
                 color=linea.get_color(), label=f"p95, {nombre_deadline(deadline_ms)}")
    eje.set_title("Latencia de GET /v1/salas según la latencia de Espacios")
    eje.set_xlabel("Latencia artificial de Espacios (ms)")
    eje.set_ylabel("Latencia vista por el cliente (ms)")
    eje.grid(True, alpha=0.3)
    eje.legend()
    fig.tight_layout()
    fig.savefig(RESULTADOS / "latencia.png", dpi=150)


def graficar_exito(por_deadline: dict[int, list[dict]]) -> None:
    fig, eje = plt.subplots(figsize=(8, 5))
    for deadline_ms, filas in por_deadline.items():
        eje.plot([int(f["latencia_espacios_ms"]) for f in filas],
                 [float(f["porcentaje_200"]) for f in filas], marker="o",
                 label=nombre_deadline(deadline_ms))
    eje.set_title("Respuestas exitosas (200) según la latencia de Espacios")
    eje.set_xlabel("Latencia artificial de Espacios (ms)")
    eje.set_ylabel("Respuestas 200 (%)")
    eje.set_ylim(-5, 105)
    eje.grid(True, alpha=0.3)
    eje.legend()
    fig.tight_layout()
    fig.savefig(RESULTADOS / "respuestas_200.png", dpi=150)


if __name__ == "__main__":
    resumen = leer_resumen()
    graficar_latencia(resumen)
    graficar_exito(resumen)
    print(f"Gráficos en {RESULTADOS}")
