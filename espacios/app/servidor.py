"""Arranque del servidor gRPC de Espacios (desde espacios/: python -m app.servidor)"""

import asyncio
import logging
import signal

import grpc

from app.config import Config
from app.generado import espacios_pb2_grpc
from app.repositorio import RepositorioEspacios, crear_pool
from app.servicio import ServicioEspacios

registro = logging.getLogger("espacios")


def crear_servidor(servicio: ServicioEspacios, direccion: str) -> tuple[grpc.aio.Server, int]:
    """Crea el servidor sin iniciarlo y devuelve el puerto (con puerto 0, uno libre)"""
    servidor = grpc.aio.server()
    espacios_pb2_grpc.add_EspaciosServicer_to_server(servicio, servidor)
    return servidor, servidor.add_insecure_port(direccion)



async def ejecutar(config: Config) -> None:
    pool = crear_pool(config.db_url)
    await pool.open(wait=True)
    try:
        repositorio = RepositorioEspacios(pool, config.zona_horaria)
        await repositorio.verificar_zona_horaria()
        servicio = ServicioEspacios(repositorio)
        servidor, puerto = crear_servidor(servicio, f"[::]:{config.puerto_grpc}")
        await servidor.start()
        registro.info("Espacios escuchando en el puerto %s", puerto)
        try:
            await esperar_senal_de_termino()
        finally:
            # Primero se deja de aceptar RPC 5s, recién después se cierra el pool
            await servidor.stop(5)
            registro.info("Servidor gRPC detenido")
    finally:
        await pool.close()
        registro.info("Pool de conexiones cerrado")


async def esperar_senal_de_termino() -> None:
    terminar = asyncio.Event()
    for senal in (signal.SIGTERM, signal.SIGINT):
        try:
            asyncio.get_running_loop().add_signal_handler(senal, terminar.set)
        except NotImplementedError:
            pass
    await terminar.wait()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = Config.desde_entorno()
    try:
        asyncio.run(ejecutar(config), loop_factory=asyncio.SelectorEventLoop)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
