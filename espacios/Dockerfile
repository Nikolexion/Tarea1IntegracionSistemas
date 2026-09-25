# Imagen del servicio Espacios (servidor gRPC)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependencias
WORKDIR /repo/espacios
COPY espacios/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Contrato y código
COPY contratos/espacios.proto /repo/contratos/espacios.proto
COPY espacios/ ./

# El código gRPC se genera desde el contrato al construir la imagen
RUN python generar_codigo.py

# Ejecución
EXPOSE 50051
CMD ["python", "-m", "app.servidor"]
