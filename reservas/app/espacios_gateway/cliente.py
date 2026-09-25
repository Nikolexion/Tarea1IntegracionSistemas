from typing import Annotated

import grpc
from fastapi import Depends, Request

from app.generado import espacios_pb2 as pb
from app.generado import espacios_pb2_grpc


class EspaciosNoDisponible(Exception):
    """Espacios está caído o saturado: no se hizo nada y se puede reintentar."""


class EspaciosSinRespuesta(Exception):
    """Espacios no respondió dentro del deadline: el resultado es incierto."""


class SalaNoEncontrada(Exception):
    pass


class DatosRechazados(Exception):
    """Espacios rechazó los datos (p. ej. franja ya iniciada); el mensaje es el de Espacios."""


class ErrorInesperadoEspacios(Exception):
    pass


EXCEPCION_POR_CODIGO = {
    grpc.StatusCode.UNAVAILABLE: EspaciosNoDisponible,
    grpc.StatusCode.ABORTED: EspaciosNoDisponible,
    grpc.StatusCode.DEADLINE_EXCEEDED: EspaciosSinRespuesta,
    grpc.StatusCode.NOT_FOUND: SalaNoEncontrada,
    grpc.StatusCode.INVALID_ARGUMENT: DatosRechazados,
}


class ClienteEspacios:

    def __init__(self, direccion: str, deadline_ms: int):
        self._canal = grpc.aio.insecure_channel(direccion)
        self._stub = espacios_pb2_grpc.EspaciosStub(self._canal)
        self._timeout = deadline_ms / 1000

    async def cerrar(self) -> None:
        await self._canal.close()

    async def listar_disponibilidad(self, fecha: str) -> pb.ListarDisponibilidadResponse:
        peticion = pb.ListarDisponibilidadRequest(fecha=fecha)
        return await self._llamar(self._stub.ListarDisponibilidad, peticion)

    async def consultar_disponibilidad(
        self, sala_id: int, fecha: str, hora_inicio: str, hora_fin: str
    ) -> pb.DisponibilidadSala:
        franja = pb.Franja(fecha=fecha, hora_inicio=hora_inicio, hora_fin=hora_fin)
        peticion = pb.ConsultarDisponibilidadRequest(sala_id=sala_id, franja=franja)
        return await self._llamar(self._stub.ConsultarDisponibilidad, peticion)

    async def ocupar_puesto(
        self, sala_id: int, fecha: str, hora_inicio: str, hora_fin: str, referencia: str
    ) -> pb.OcuparPuestoResponse:
        franja = pb.Franja(fecha=fecha, hora_inicio=hora_inicio, hora_fin=hora_fin)
        peticion = pb.OcuparPuestoRequest(sala_id=sala_id, franja=franja, referencia=referencia)
        return await self._llamar(self._stub.OcuparPuesto, peticion)

    async def liberar_puesto(self, referencia: str) -> pb.LiberarPuestoResponse:
        peticion = pb.LiberarPuestoRequest(referencia=referencia)
        return await self._llamar(self._stub.LiberarPuesto, peticion)

    async def _llamar(self, rpc, peticion):
        """Hace la llamada con deadline y traduce el error gRPC a una excepción propia."""
        try:
            return await rpc(peticion, timeout=self._timeout)
        except grpc.aio.AioRpcError as error:
            nunca_conecto = self._canal.get_state() != grpc.ChannelConnectivity.READY
            if error.code() == grpc.StatusCode.DEADLINE_EXCEEDED and nunca_conecto:
                raise EspaciosNoDisponible("No se pudo conectar con Espacios") from error
            excepcion = EXCEPCION_POR_CODIGO.get(error.code(), ErrorInesperadoEspacios)
            raise excepcion(error.details()) from error


def _cliente_espacios(request: Request) -> ClienteEspacios:
    return request.app.state.espacios


Espacios = Annotated[ClienteEspacios, Depends(_cliente_espacios)]
