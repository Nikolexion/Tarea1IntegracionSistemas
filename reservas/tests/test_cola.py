import random
import uuid
from datetime import date, timedelta

import pytest

from app.cola.procesador import procesar_ciclo
from app.espacios_gateway.cliente import EspaciosNoDisponible
from app.persistencia import reservas as persistencia_reservas

SALA_ID, HORA_INICIO, HORA_FIN = 1, "10:00", "11:00"


@pytest.fixture
async def liberacion_encolada(app_iniciada):
    """Ocupa un puesto en Espacios y encola su liberación; al terminar deja todo limpio"""
    fecha = date.today() + timedelta(days=random.randint(60, 3000))
    referencia = uuid.uuid4()
    espacios = app_iniciada.state.espacios
    await espacios.ocupar_puesto(SALA_ID, fecha.isoformat(), HORA_INICIO, HORA_FIN, str(referencia))
    async with app_iniciada.state.pool.connection() as conexion:
        await persistencia_reservas.encolar_liberacion(
            conexion, referencia, SALA_ID, fecha, HORA_INICIO, HORA_FIN
        )
    yield referencia, fecha
    await espacios.liberar_puesto(str(referencia))
    async with app_iniciada.state.pool.connection() as conexion:
        await conexion.execute(
            "DELETE FROM liberaciones_pendientes WHERE referencia = %s", (referencia,)
        )


async def _fila(app, referencia):
    """(intentos, ultimo_error) de la fila en la cola, o None si ya no está"""
    async with app.state.pool.connection() as conexion:
        cursor = await conexion.execute(
            "SELECT intentos, ultimo_error FROM liberaciones_pendientes WHERE referencia = %s",
            (referencia,),
        )
        return await cursor.fetchone()


async def _puestos_libres(app, fecha) -> int:
    disponibilidad = await app.state.espacios.consultar_disponibilidad(
        SALA_ID, fecha.isoformat(), HORA_INICIO, HORA_FIN
    )
    return disponibilidad.puestos_libres


async def test_un_ciclo_libera_el_puesto_y_borra_la_fila(app_iniciada, liberacion_encolada):
    referencia, fecha = liberacion_encolada
    assert await _puestos_libres(app_iniciada, fecha) == 1

    await procesar_ciclo(app_iniciada.state.pool, app_iniciada.state.espacios)

    assert await _fila(app_iniciada, referencia) is None
    assert await _puestos_libres(app_iniciada, fecha) == 2


async def test_si_espacios_falla_la_fila_queda_y_se_reintenta(
    app_iniciada, liberacion_encolada, monkeypatch
):
    referencia, fecha = liberacion_encolada
    espacios = app_iniciada.state.espacios
    liberar_real = espacios.liberar_puesto

    async def liberar_con_falla(ref):
        if ref == str(referencia):
            raise EspaciosNoDisponible("falla simulada")
        return await liberar_real(ref)

    monkeypatch.setattr(espacios, "liberar_puesto", liberar_con_falla)
    await procesar_ciclo(app_iniciada.state.pool, espacios)

    intentos, ultimo_error = await _fila(app_iniciada, referencia)
    assert intentos == 1
    assert "falla simulada" in ultimo_error

    monkeypatch.undo()
    await procesar_ciclo(app_iniciada.state.pool, espacios)

    assert await _fila(app_iniciada, referencia) is None
    assert await _puestos_libres(app_iniciada, fecha) == 2
