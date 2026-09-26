# CoLabora | Sistema de reservas de puestos

Integración de los sistemas **Espacios** y **Reservas** de la red de cowork CoLabora.

- **Espacios** (`espacios/`): servidor gRPC interno, fuente de verdad sobre salas y puestos libres.
- **Reservas** (`reservas/`): API REST pública (FastAPI) con usuarios, autenticación JWT y reservas;
  consulta a Espacios por gRPC y usa Redis como caché.
- **Frontend** (`frontend/`): HTML y JavaScript servidos por nginx, que reenvía `/v1` a Reservas.

Cada servicio tiene su propia base PostgreSQL.

## Requisitos

- Docker con Docker Compose.
- Python 3.12, solo para correr las pruebas, el recorrido y el experimento fuera de Docker.

## Cómo levantar

```bash
cp .env.example .env
docker compose up -d --build --wait
```

| Servicio | Acceso |
|---|---|
| Frontend | http://localhost:8080 |
| API REST y documentación | http://localhost:8000/docs |
| Espacios (gRPC) | `127.0.0.1:50051` |
| Bases de datos | `127.0.0.1:5433` (Espacios) y `127.0.0.1:5434` (Reservas) |

El administrador inicial se crea con `ADMIN_EMAIL_INICIAL` y `ADMIN_PASSWORD_INICIAL` del `.env`.
Para detener todo y borrar los datos: `docker compose down -v`.

## Cómo correr las pruebas

Entorno virtual en la raíz del repositorio (en Linux o macOS, `venv/bin/python`):

```bash
python -m venv venv
venv/Scripts/python.exe -m pip install -r espacios/requirements.txt -r reservas/requirements.txt
venv/Scripts/python.exe espacios/generar_codigo.py
venv/Scripts/python.exe reservas/generar_codigo.py
```

**Espacios:**

```bash
docker compose up -d --wait espacios-db
cd espacios && ../venv/Scripts/python.exe -m pytest && cd ..
```

**Reservas** (el contenedor `reservas` debe estar detenido, porque su cola de liberaciones usaría
las filas que crean las pruebas):

```bash
docker compose stop reservas
docker compose up -d --wait reservas-db espacios
cd reservas && ../venv/Scripts/python.exe -m pytest && cd ..
```

## Recorrido del sistema y experimento

Con el sistema completo levantado (`docker compose up -d --wait`):

```bash
venv/Scripts/python.exe probar_sistema.py
```

Registra un usuario, reserva hasta llenar una sala, detiene Espacios para mostrar el 503 y la cola
de liberaciones, y lo vuelve a iniciar.

**Experimento de timeout:** mide `GET /v1/salas` con distintas latencias de Espacios y deadlines de
Reservas. Tarda unos 20 minutos y deja los resultados en `experimentos/timeout/resultados/`.

```bash
venv/Scripts/python.exe -m pip install -r experimentos/requirements.txt
venv/Scripts/python.exe experimentos/timeout/medir.py
venv/Scripts/python.exe experimentos/timeout/graficar.py
```

## Estructura del repositorio

```
contratos/      Contratos v1: espacios.proto (gRPC) y openapi.yaml (REST)
espacios/       Servicio Espacios (gRPC); db/ con el esquema y los datos iniciales
reservas/       Servicio Reservas (REST); db/ con el esquema
frontend/       Frontend HTML + JavaScript servido por nginx
experimentos/   Experimento de timeout y sus resultados
docs/adr/       Registros de decisiones de arquitectura (D1 a D4)
```

## Declaración de uso de asistentes de IA

Se usó Claude (Anthropic), mediante Claude Code, como apoyo durante el desarrollo:

- **Diseño:** para discutir alternativas de arquitectura y sus costos antes de cada decisión. Las
  decisiones las tomó el equipo.
- **Código:** para generar versiones iniciales de código, pruebas y el script del experimento, y
  para revisar el código escrito por el equipo.
- **Documentación:** para apoyar la redacción de los ADR y del informe.

**Qué se verificó:** cada integrante reescribió y revisó línea a línea el código que incorporó al
repositorio; el funcionamiento se comprobó con las pruebas automatizadas de ambos servicios, el
recorrido `probar_sistema.py` y levantando el sistema completo con Docker Compose.
