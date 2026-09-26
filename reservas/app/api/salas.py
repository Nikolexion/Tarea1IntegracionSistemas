"""Salas y disponibilidad: `/v1/salas`. Solo traducen la respuesta de Espacios al contrato REST"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.enlaces import enlace_reservar, ruta_disponibilidad
from app.api.esquemas import (
    PATRON_HORA,
    Disponibilidad,
    Enlace,
    FranjaDisponible,
    GrillaDisponibilidad,
    Sala,
    SalaConDisponibilidad,
)
from app.auth.dependencias import identidad_obligatoria
from app.cache.disponibilidad import Cache
from app.espacios_gateway.cliente import Espacios

# Cualquier usuario autenticado puede consultar
router = APIRouter(
    prefix="/v1/salas", tags=["Salas"], dependencies=[Depends(identidad_obligatoria)]
)

HoraConsulta = Annotated[str, Query(pattern=PATRON_HORA)]


@router.get("", response_model_exclude_none=True)
async def listar_disponibilidad(
    fecha: date, espacios: Espacios, cache: Cache
) -> GrillaDisponibilidad:
    respuesta, redis_respondio = await cache.obtener(fecha)
    if respuesta is None:
        respuesta = await espacios.listar_disponibilidad(fecha.isoformat())
        # Si Redis no respondió al leer, tampoco se intenta guardar: evita esperar dos veces
        if redis_respondio:
            await cache.guardar(fecha, respuesta)
    # El .proto entrega una lista plana (sala × franja); el contrato la agrupa por sala
    salas: dict[int, SalaConDisponibilidad] = {}
    for item in respuesta.disponibilidades:
        sala, franja = item.sala, item.franja
        if sala.id not in salas:
            salas[sala.id] = SalaConDisponibilidad(
                id=sala.id, nombre=sala.nombre, capacidad=sala.capacidad, franjas=[]
            )
        salas[sala.id].franjas.append(FranjaDisponible(
            hora_inicio=franja.hora_inicio,
            hora_fin=franja.hora_fin,
            puestos_libres=item.puestos_libres,
            enlaces=enlace_reservar(
                sala.id, fecha, franja.hora_inicio, franja.hora_fin,
                item.puestos_libres, item.iniciada,
            ),
        ))
    return GrillaDisponibilidad(fecha=fecha, salas=list(salas.values()))


@router.get("/{sala_id}/disponibilidad", response_model_exclude_none=True)
async def consultar_disponibilidad(
    sala_id: Annotated[int, Path(ge=1)],
    fecha: date,
    hora_inicio: HoraConsulta,
    hora_fin: HoraConsulta,
    espacios: Espacios,
) -> Disponibilidad:
    item = await espacios.consultar_disponibilidad(
        sala_id, fecha.isoformat(), hora_inicio, hora_fin
    )
    ruta = ruta_disponibilidad(sala_id, fecha, hora_inicio, hora_fin)
    enlaces = {
        "self": Enlace(href=ruta, method="GET"),
        **enlace_reservar(
            sala_id, fecha, hora_inicio, hora_fin, item.puestos_libres, item.iniciada
        ),
    }
    return Disponibilidad(
        sala=Sala(id=item.sala.id, nombre=item.sala.nombre, capacidad=item.sala.capacidad),
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        puestos_libres=item.puestos_libres,
        enlaces=enlaces,
    )
