"""Las 4 RPC de contratos/espacios.proto"""

import re
from contextlib import asynccontextmanager
from datetime import date, time

import grpc
from psycopg.errors import LockNotAvailable
from psycopg_pool import PoolTimeout

from app.generado import espacios_pb2, espacios_pb2_grpc
from app.repositorio import (
    Franja,
    FranjaIniciada,
    FranjaInvalida,
    ReferenciaEnOtraFranja,
    RepositorioEspacios,
    ResultadoLiberacion,
    ResultadoOcupacion,
    SalaNoEncontrada,
)


class FormatoInvalido(Exception):
    """La petición no respeta el formato del contrato (fecha, hora o referencia)"""


CODIGO_POR_ERROR = {
    FormatoInvalido: grpc.StatusCode.INVALID_ARGUMENT,
    SalaNoEncontrada: grpc.StatusCode.NOT_FOUND,
    FranjaInvalida: grpc.StatusCode.INVALID_ARGUMENT,
    FranjaIniciada: grpc.StatusCode.INVALID_ARGUMENT,
    ReferenciaEnOtraFranja: grpc.StatusCode.ALREADY_EXISTS,
}


# --- Lectura de la petición ---
def _leer(texto: str, patron: str, convertir, nombre: str, esperado: str):
    # Regex primero: fromisoformat también acepta variantes ("20261001") que el contrato no permite
    if not re.fullmatch(patron, texto):
        raise FormatoInvalido(f"{nombre} con formato inválido: {texto!r} (se espera {esperado})")
    try:
        return convertir(texto)
    except ValueError:
        raise FormatoInvalido(f"{nombre} inexistente: {texto!r}") from None


def leer_fecha(texto: str) -> date:
    return _leer(texto, r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date.fromisoformat, "Fecha", "AAAA-MM-DD")


def leer_hora(texto: str) -> time:
    return _leer(texto, r"[0-9]{2}:[0-9]{2}", time.fromisoformat, "Hora", "HH:MM")


def leer_franja(franja: espacios_pb2.Franja) -> Franja:
    return Franja(leer_fecha(franja.fecha), leer_hora(franja.hora_inicio), leer_hora(franja.hora_fin))


def leer_referencia(referencia: str) -> str:
    if not referencia.strip():
        raise FormatoInvalido("La referencia no puede estar vacía")
    return referencia


# --- Conversión a mensajes protobuf ---
RESULTADO_OCUPACION_PROTO = {
    ResultadoOcupacion.OCUPADO: espacios_pb2.RESULTADO_OCUPACION_OCUPADO,
    ResultadoOcupacion.SIN_PUESTOS: espacios_pb2.RESULTADO_OCUPACION_SIN_PUESTOS,
    ResultadoOcupacion.REFERENCIA_LIBERADA: espacios_pb2.RESULTADO_OCUPACION_REFERENCIA_LIBERADA,
}

RESULTADO_LIBERACION_PROTO = {
    ResultadoLiberacion.LIBERADO: espacios_pb2.RESULTADO_LIBERACION_LIBERADO,
    ResultadoLiberacion.YA_LIBERADO: espacios_pb2.RESULTADO_LIBERACION_YA_LIBERADO,
    ResultadoLiberacion.SIN_OCUPACION_PREVIA: espacios_pb2.RESULTADO_LIBERACION_SIN_OCUPACION_PREVIA,
}


def a_disponibilidad_proto(fila: dict, franja: espacios_pb2.Franja) -> espacios_pb2.DisponibilidadSala:
    return espacios_pb2.DisponibilidadSala(
        sala=espacios_pb2.Sala(id=fila["id"], nombre=fila["nombre"], capacidad=fila["capacidad"]),
        franja=franja,
        puestos_libres=fila["puestos_libres"],
        iniciada=fila["iniciada"],
    )


# --- Servicio gRPC ---
class ServicioEspacios(espacios_pb2_grpc.EspaciosServicer):
    def __init__(self, repositorio: RepositorioEspacios):
        self._repositorio = repositorio

    @asynccontextmanager
    async def _atender(self, context: grpc.aio.ServicerContext):
        """Traduce las excepciones a códigos de estado gRPC."""
        try:
            yield
        except tuple(CODIGO_POR_ERROR) as error:
            await context.abort(CODIGO_POR_ERROR[type(error)], str(error))
        except LockNotAvailable:  # se superó el lock_timeout: no se ocupó nada
            await context.abort(grpc.StatusCode.ABORTED, "La sala estuvo bloqueada demasiado tiempo, reintente")
        except PoolTimeout:  # pool acotado sin conexion libre, no se hizo nada
            await context.abort(grpc.StatusCode.UNAVAILABLE, "Servicio saturado, reintente más tarde")

    async def ConsultarDisponibilidad(self, request, context):
        async with self._atender(context):
            fila = await self._repositorio.consultar_disponibilidad(request.sala_id, leer_franja(request.franja))
        # El formato ya se validó, así que la franja pedida es idéntica a la normalizada.
        return a_disponibilidad_proto(fila, request.franja)

    async def ListarDisponibilidad(self, request, context):
        async with self._atender(context):
            filas = await self._repositorio.listar_disponibilidad(leer_fecha(request.fecha))
        return espacios_pb2.ListarDisponibilidadResponse(disponibilidades=[
            a_disponibilidad_proto(fila, espacios_pb2.Franja(
                fecha=request.fecha,
                hora_inicio=fila["hora_inicio"].strftime("%H:%M"),
                hora_fin=fila["hora_fin"].strftime("%H:%M"),
            ))
            for fila in filas
        ])

    async def OcuparPuesto(self, request, context):
        async with self._atender(context):
            franja, referencia = leer_franja(request.franja), leer_referencia(request.referencia)
            ocupacion = await self._repositorio.ocupar(request.sala_id, franja, referencia)
        return espacios_pb2.OcuparPuestoResponse(
            resultado=RESULTADO_OCUPACION_PROTO[ocupacion.resultado],
            puestos_libres=ocupacion.puestos_libres,
            sala_nombre=ocupacion.sala_nombre,
        )

    async def LiberarPuesto(self, request, context):
        async with self._atender(context):
            resultado = await self._repositorio.liberar(leer_referencia(request.referencia))
        return espacios_pb2.LiberarPuestoResponse(resultado=RESULTADO_LIBERACION_PROTO[resultado])
