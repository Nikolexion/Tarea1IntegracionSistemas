"""
Prueba manual de las 4 RPC contra Espacios en ejecución:
python espacios/probar_rpc.py
"""

import asyncio
import sys
import uuid
from datetime import date, timedelta

import grpc
from google.protobuf import text_format

from app.generado import espacios_pb2 as pb, espacios_pb2_grpc

DIRECCION = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:50051"
FECHA = (date.today() + timedelta(days=7)).isoformat()
FRANJA = pb.Franja(fecha=FECHA, hora_inicio="09:00", hora_fin="10:00")


def mostrar(titulo: str, mensaje) -> None:
    print(f"{titulo}:\n  {text_format.MessageToString(mensaje, as_one_line=True)}\n")


async def main() -> None:
    async with grpc.aio.insecure_channel(DIRECCION) as canal:
        stub = espacios_pb2_grpc.EspaciosStub(canal)
        listado = await stub.ListarDisponibilidad(pb.ListarDisponibilidadRequest(fecha=FECHA))

        print(f"ListarDisponibilidad({FECHA}): {len(listado.disponibilidades)} entradas; primeras 3:")
        for disponibilidad in listado.disponibilidades[:3]:
            print(f"  {text_format.MessageToString(disponibilidad, as_one_line=True)}")
        print()

        consulta = pb.ConsultarDisponibilidadRequest(sala_id=1, franja=FRANJA)
        mostrar("ConsultarDisponibilidad", await stub.ConsultarDisponibilidad(consulta))

        # Ocupa y libera un puesto de la sala 1, deja en la base solo un registro LIBERADA
        ocupar = pb.OcuparPuestoRequest(sala_id=1, franja=FRANJA, referencia=str(uuid.uuid4()))
        liberar = pb.LiberarPuestoRequest(referencia=ocupar.referencia)

        mostrar("OcuparPuesto", await stub.OcuparPuesto(ocupar))
        mostrar("OcuparPuesto (repetido, idempotente)", await stub.OcuparPuesto(ocupar))
        mostrar("ConsultarDisponibilidad (tras ocupar)", await stub.ConsultarDisponibilidad(consulta))
        mostrar("LiberarPuesto", await stub.LiberarPuesto(liberar))
        mostrar("LiberarPuesto (repetido)", await stub.LiberarPuesto(liberar))
        mostrar("OcuparPuesto (tardío, referencia liberada)", await stub.OcuparPuesto(ocupar))

        try:
            await stub.ConsultarDisponibilidad(pb.ConsultarDisponibilidadRequest(sala_id=999, franja=FRANJA))
        except grpc.aio.AioRpcError as error:
            print(f"ConsultarDisponibilidad(sala 999): {error.code().name} - {error.details()}")


if __name__ == "__main__":
    asyncio.run(main())
