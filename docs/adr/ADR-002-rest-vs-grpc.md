# ADR-002 · REST frente a gRPC (D2)

## Contexto
El sistema tiene dos fronteras de comunicación con consumidores distintos. La externa (clientes
hacia Reservas) la usan clientes que el equipo no controla, como el navegador y un futuro portal.
La interna (Reservas hacia Espacios) tiene un único consumidor conocido, que la usa con mucha
frecuencia y que el exterior no ve.

## Alternativas consideradas
- **REST en ambas**: una sola tecnología, pero la comunicación interna pierde el contrato tipado y
  el control de tiempo por llamada.
- **gRPC en ambas**: una sola tecnología eficiente, pero el navegador no puede consumirla
  directamente y la API externa deja de ser legible con herramientas comunes.
- **REST hacia afuera y gRPC hacia adentro**: cada frontera con la tecnología que corresponde a su
  consumidor, a cambio de mantener dos tecnologías.

## Decisión
REST con JSON para la API pública de Reservas y gRPC con protobuf para la comunicación interna
entre Reservas y Espacios.

## Justificación
La tecnología de cada frontera se elige según quién la consume. La frontera externa debe poder
usarla cualquier cliente HTTP sin herramientas especiales: el navegador no habla gRPC sin un proxy
intermedio, y REST además se depura y documenta con herramientas estándar. La frontera interna, en
cambio, tiene un solo consumidor que genera su código desde el mismo contrato, por lo que puede
aprovechar lo que gRPC ofrece: tipos verificados en ambos lados, mensajes binarios compactos sobre
conexiones HTTP/2 persistentes, y un tiempo máximo de espera (deadline) que viaja con cada llamada.
Este último fue decisivo para D4: en el experimento (`experimentos/timeout`), el deadline acotó el
tiempo de respuesta de Reservas al valor configurado más unos 17 ms, sin importar cuán lento
respondiera Espacios.

## Costo aceptado
Dos tecnologías, dos contratos y dos conjuntos de herramientas. Reservas debe traducir los estados
de gRPC a códigos HTTP. La comunicación interna es binaria, por lo que depurarla requiere
herramientas específicas, y como la caché HTTP no aplica a gRPC, la caché se implementó en la
aplicación (Redis).

## Consecuencias
El navegador nunca se comunica con Espacios, por lo que Espacios podría cambiar de tecnología sin
que los clientes externos lo noten, siempre que respete el `.proto`. Si Espacios llegara a tener
consumidores externos, habría que exponerlo por REST o por gRPC-Web.
