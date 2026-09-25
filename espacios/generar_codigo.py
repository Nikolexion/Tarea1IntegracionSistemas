"""Genera el código gRPC desde contratos/espacios.proto"""

import sys
from pathlib import Path

from grpc_tools import protoc

CARPETA_ESPACIOS = Path(__file__).resolve().parent
CARPETA_CONTRATOS = CARPETA_ESPACIOS.parent / "contratos"
CARPETA_GENERADO = CARPETA_ESPACIOS / "app" / "generado"


def generar() -> None:
    CARPETA_GENERADO.mkdir(parents=True, exist_ok=True)
    (CARPETA_GENERADO / "__init__.py").touch()

    argumentos = [
        "grpc_tools.protoc",
        f"-Iapp/generado={CARPETA_CONTRATOS}",
        f"--python_out={CARPETA_ESPACIOS}",
        f"--grpc_python_out={CARPETA_ESPACIOS}",
        str(CARPETA_CONTRATOS / "espacios.proto"),
    ]
    if protoc.main(argumentos) != 0:
        sys.exit("No se pudo generar el código desde espacios.proto")
    print(f"Código generado en {CARPETA_GENERADO}")


if __name__ == "__main__":
    generar()
