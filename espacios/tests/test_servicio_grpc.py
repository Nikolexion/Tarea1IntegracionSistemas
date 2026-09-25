"""
Pruebas del servicio gRPC real, levantado en el mismo proceso
"""

import grpc
import pytest
from app.generado import espacios_pb2 as pb
from tests.datos import nueva_referencia

FRANJA = pb.Franja(fecha="2099-03-10", hora_inicio="09:00", hora_fin="10:00")


async def test_resultados_en_enums_y_errores_en_codigos_de_estado(cliente_grpc, crear_sala):
    sala_id = await crear_sala(2)

    ocupada = await cliente_grpc.OcuparPuesto(
        pb.OcuparPuestoRequest(sala_id=sala_id, franja=FRANJA, referencia=nueva_referencia())
    )
    assert ocupada.resultado == pb.RESULTADO_OCUPACION_OCUPADO
    assert ocupada.puestos_libres == 1
    consulta = await cliente_grpc.ConsultarDisponibilidad(pb.ConsultarDisponibilidadRequest(sala_id=sala_id, franja=FRANJA))
    assert (consulta.sala.id, consulta.franja, consulta.puestos_libres) == (sala_id, FRANJA, 1)

    with pytest.raises(grpc.aio.AioRpcError) as error:
        await cliente_grpc.ConsultarDisponibilidad(pb.ConsultarDisponibilidadRequest(sala_id=8_999_999, franja=FRANJA))
    assert error.value.code() == grpc.StatusCode.NOT_FOUND

    with pytest.raises(grpc.aio.AioRpcError) as error:
        await cliente_grpc.ListarDisponibilidad(pb.ListarDisponibilidadRequest(fecha="20990310"))
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT



async def test_sala_bloqueada_mas_que_el_lock_timeout_responde_aborted(cliente_grpc, crear_sala, pool):
    sala_id = await crear_sala(2)
    # Otra conexión toma el bloqueo de la sala y no lo suelta mientras se intenta ocupar.
    async with pool.connection() as otra_conexion, otra_conexion.transaction(force_rollback=True):
        await otra_conexion.execute("SELECT id FROM salas WHERE id = %s FOR UPDATE", (sala_id,))
        with pytest.raises(grpc.aio.AioRpcError) as error:
            await cliente_grpc.OcuparPuesto(
                pb.OcuparPuestoRequest(sala_id=sala_id, franja=FRANJA, referencia=nueva_referencia())
            )
    assert error.value.code() == grpc.StatusCode.ABORTED