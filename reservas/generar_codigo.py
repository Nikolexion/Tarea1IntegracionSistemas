import sys
from pathlib import Path

from grpc_tools import protoc


CARPETA_RESERVAS = Path(__file__).resolve().parent
CARPETA_CONTRATOS = CARPETA_RESERVAS.parent / "contratos"
CARPETA_GENERADO = CARPETA_RESERVAS / "app" / "generado"



def generar() -> None:
    CARPETA_GENERADO.mkdir(parents=True, exist_ok=True)
    (CARPETA_GENERADO / "__init__.py").touch()
    
    argumentos = [
        "grpc_tools.protoc",
        f"-Iapp/generado={CARPETA_CONTRATOS}",
        f"--python_out={CARPETA_RESERVAS}",
        f"--grpc_python_out={CARPETA_RESERVAS}",
        str(CARPETA_CONTRATOS / "espacios.proto"),
    ]
    if protoc.main(argumentos) != 0:
        sys.exit("No se pudo generar el código desde espacios.proto")
    print(f"Código generado en {CARPETA_GENERADO}")


if __name__ == "__main__":
    generar()
