FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /servicio

COPY reservas/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY reservas/ .
COPY contratos/espacios.proto /contratos/espacios.proto
COPY contratos/openapi.yaml /contratos/openapi.yaml

RUN python generar_codigo.py

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
