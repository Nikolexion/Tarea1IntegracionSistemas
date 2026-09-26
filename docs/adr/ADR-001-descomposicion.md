# ADR-001 · Descomposición e integración (D1)

## Contexto
Espacios y Reservas son sistemas existentes, con equipos distintos. Hay que decidir si se mantienen
separados y cómo se comunican, sin compartir base de datos.

## Alternativas consideradas
- **Monolito**: una base y transacciones simples, pero obliga a reescribir dos sistemas y fusionar
  a sus equipos.
- **Monolito modular**: módulos separados en un solo despliegue; ambos equipos comparten ciclo de
  despliegue y no se escalan por separado.
- **Dos servicios con base propia**: respeta a cada dueño, a cambio de comunicarse por red y perder
  la transacción común. Considerando que la situación inicial era explícitamente sobre dos servicios
  que funcionaban sin comunicación, naturalmente surgió esta opción.

## Decisión
Dos servicios con base propia, integrados por RPC síncrono (gRPC), con la frontera en el bounded
context de cada uno. Espacios verifica y ocupa en una sola operación atómica mientras que Reservas
solo conoce la sala y la franja de cada reserva.

## Justificación
La decisión se tomó porque Espacios y Reservas tienen dueños y ciclos de cambio distintos. Una
frontera alineada con esa organización permite que cada equipo modifique y despliegue su sistema
sin coordinarse con el otro, salvo en el contrato.

Además, RPC síncrono se justifica en que una reserva requiere una respuesta inmediata sobre la
disponibilidad, lo que excluye transferencia de archivos y mensajería asíncrona como opciones. La
base compartida estaba denegada así que no se consideró. La invocación remota síncrona es el único
estilo que cumplía con estas condiciones.

## Costo aceptado
Todo lo que resuelve D4 es el precio de separar: latencia de red, fallas parciales, compensaciones
en lugar de una transacción, y consistencia eventual. Además, seis contenedores y el nombre de la
sala copiado en Reservas, que puede quedar desactualizado.

## Consecuencias
El `.proto` pasa a ser la frontera. Con un solo equipo y un sistema nuevo, un monolito modular
sería la opción más razonable y menos compleja.
