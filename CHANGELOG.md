# Registro de cambios

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [1.0.0]

### Agregado
- Contrato gRPC `colabora.espacios.v1` (`contratos/espacios.proto`) y contrato REST bajo `/v1`
  (`contratos/openapi.yaml`).
- Servicio Espacios: consultar y listar disponibilidad, ocupar un puesto de forma atómica e
  idempotente por referencia, y liberar por referencia.
- Servicio Reservas: registro y login con JWT, usuarios, salas, reservas y cancelación.
- Integración con Espacios por gRPC con deadline, respuestas 503 y 504, y cola de liberaciones.
- Opcionales: caché de disponibilidad con Redis (O1), `Idempotency-Key` al reservar (O2), enlaces
  HATEOAS (O3) y prueba de contrato contra `openapi.yaml` (O4).
- Frontend mínimo servido por nginx.
- Experimento del efecto del timeout y recorrido del sistema (`probar_sistema.py`).

### Cambiado
- `colabora.espacios.v1`: se agregaron `DisponibilidadSala.iniciada` (campo 4) y
  `OcuparPuestoResponse.sala_nombre` (campo 3). Son cambios compatibles: campos nuevos con números
  nuevos, que un cliente anterior ignora; no requieren una versión `v2`.
