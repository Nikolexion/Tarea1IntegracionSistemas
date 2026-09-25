"""
Pruebas del repositorio contra la base real de Espacios
"""

import asyncio
from collections import Counter
import pytest

from app.repositorio import (
    FranjaIniciada,
    FranjaInvalida,
    ReferenciaEnOtraFranja,
    ResultadoLiberacion,
    ResultadoOcupacion,
    SalaNoEncontrada,
)
from tests.datos import FECHA_PASADA, franja, nueva_referencia


@pytest.mark.parametrize("capacidad", [1, 3])
async def test_ocupaciones_simultaneas_no_superan_la_capacidad(repositorio, crear_sala, capacidad):
    sala_id = await crear_sala(capacidad)

    ocupaciones = await asyncio.gather(
        *(repositorio.ocupar(sala_id, franja(), nueva_referencia()) for _ in range(10))
    )

    resultados = Counter(o.resultado for o in ocupaciones)
    assert resultados[ResultadoOcupacion.OCUPADO] == capacidad
    assert resultados[ResultadoOcupacion.SIN_PUESTOS] == 10 - capacidad
    assert (await repositorio.consultar_disponibilidad(sala_id, franja()))["puestos_libres"] == 0


async def test_repetir_la_referencia_no_ocupa_otro_puesto(repositorio, crear_sala):
    sala_id = await crear_sala(2)
    referencia = nueva_referencia()

    primera = await repositorio.ocupar(sala_id, franja(), referencia)
    segunda = await repositorio.ocupar(sala_id, franja(), referencia)

    assert primera == segunda
    assert primera.resultado == ResultadoOcupacion.OCUPADO
    assert primera.puestos_libres == 1


async def test_referencia_en_otra_franja_o_sala_ya_existe(repositorio, crear_sala):
    sala_id, otra_sala_id = await crear_sala(2), await crear_sala(2)
    referencia = nueva_referencia()
    await repositorio.ocupar(sala_id, franja(), referencia)

    with pytest.raises(ReferenciaEnOtraFranja):
        await repositorio.ocupar(sala_id, franja(inicio="10:00", fin="11:00"), referencia)
    with pytest.raises(ReferenciaEnOtraFranja):
        await repositorio.ocupar(otra_sala_id, franja(), referencia)


async def test_liberar_y_sus_tres_resultados(repositorio, crear_sala):
    sala_id = await crear_sala(2)
    referencia = nueva_referencia()
    await repositorio.ocupar(sala_id, franja(), referencia)

    assert await repositorio.liberar(referencia) == ResultadoLiberacion.LIBERADO
    assert await repositorio.liberar(referencia) == ResultadoLiberacion.YA_LIBERADO
    assert await repositorio.liberar(nueva_referencia()) == ResultadoLiberacion.SIN_OCUPACION_PREVIA
    assert (await repositorio.consultar_disponibilidad(sala_id, franja()))["puestos_libres"] == 2
    reocupar = await repositorio.ocupar(sala_id, franja(), referencia)
    assert reocupar.resultado == ResultadoOcupacion.REFERENCIA_LIBERADA


async def test_ocupacion_tardia_de_referencia_liberada_se_rechaza(repositorio, crear_sala):
    # Caso del timeout, la liberación llega a Espacios antes que la ocupación atrasada
    sala_id = await crear_sala(2)
    referencia = nueva_referencia()
    await repositorio.liberar(referencia)

    ocupacion = await repositorio.ocupar(sala_id, franja(), referencia)

    assert ocupacion.resultado == ResultadoOcupacion.REFERENCIA_LIBERADA
    assert ocupacion.puestos_libres == 2


async def test_franja_iniciada_se_rechaza_al_ocupar_pero_se_puede_consultar(repositorio, crear_sala):
    sala_id = await crear_sala(2)

    with pytest.raises(FranjaIniciada):
        await repositorio.ocupar(sala_id, franja(FECHA_PASADA), nueva_referencia())
    assert (await repositorio.consultar_disponibilidad(sala_id, franja(FECHA_PASADA)))["puestos_libres"] == 2


@pytest.mark.parametrize(("inicio", "fin"), [("08:30", "09:30"), ("08:00", "10:00"), ("07:00", "08:00")])
async def test_franja_que_no_es_un_bloque_es_invalida(repositorio, crear_sala, inicio, fin):
    sala_id = await crear_sala(2)

    with pytest.raises(FranjaInvalida):
        await repositorio.consultar_disponibilidad(sala_id, franja(inicio=inicio, fin=fin))
    with pytest.raises(FranjaInvalida):
        await repositorio.ocupar(sala_id, franja(inicio=inicio, fin=fin), nueva_referencia())


async def test_sala_inexistente(repositorio):
    with pytest.raises(SalaNoEncontrada):
        await repositorio.ocupar(8_999_999, franja(), nueva_referencia())

