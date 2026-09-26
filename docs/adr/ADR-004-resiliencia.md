# ADR-004 · Resiliencia y modos de falla (D4)

## Contexto
Reservas depende de Espacios de forma síncrona. Espacios puede fallar de dos maneras: estar
**caído**, y entonces la conexión no se establece, o estar **lento**, y entonces la respuesta no
llega a tiempo. En el segundo caso el resultado es incierto: Espacios pudo haber ocupado el puesto
aunque la respuesta nunca llegara.

## Alternativas consideradas
- **Código de estado**: 500 (falso, no es un error de la API), 502 (Espacios no respondió mal, no
  respondió), siempre 503 (oculta la diferencia entre "no se hizo" y "no se sabe"), o 503 y 504
  según el caso.
- **Resultado incierto**: no hacer nada (puede quedar un puesto ocupado sin reserva), liberar tras
  el timeout (la liberación puede llegar antes que la ocupación atrasada), liberar y además
  registrar la liberación, o guardar la reserva como pendiente y reconciliarla después.
- **Cola de compensaciones**: en Redis o en un broker (sin transacción común con la base) o como
  tabla en la propia base de Reservas.
- **Reintentos automáticos y circuit breaker**: descartados, porque multiplican la carga sobre un
  servicio degradado o agregan un componente con estado.

## Decisión
Toda llamada a Espacios tiene un deadline de 1 s. Si Espacios no está disponible, o si el deadline
vence sin haber establecido la conexión, se responde **503** ("no se hizo nada", con
`Retry-After`); si vence con la conexión establecida, **504** ("resultado incierto"). Ante un 504
al reservar, se ordena liberar la referencia de esa ocupación, y Espacios registra la liberación
para rechazar una ocupación tardía. Las liberaciones pendientes se guardan en una tabla de la base
de Reservas (transactional outbox) que una tarea procesa cada 5 s, y cancelar una reserva siempre
pasa por esa cola, por lo que funciona aunque Espacios esté caído. Dentro de Espacios, las esperas
por bloqueos y por conexiones se acotan a 0,5 s, bajo el deadline, para responder "no se hizo
nada" antes que Reservas se rinda.

## Justificación
Distinguir 503 de 504 entrega al cliente la información que necesita para decidir si reintentar.
El experimento (`experimentos/timeout`) midió el efecto del deadline: sin él, el tiempo de
respuesta crece igual que la lentitud de Espacios; con él, queda acotado al valor configurado más
unos 17 ms. La regla de la conexión no establecida nació de una medición: al detener el contenedor
de Espacios, resolver su nombre tardaba cerca de 4 s, más que el deadline, y el cliente recibía un
504 cuando en realidad no se había hecho nada; con la regla responde 503 en 1 s. Liberar por
referencia es idempotente, así que la cola puede entregar la misma liberación más de una vez sin
efectos extra, y al guardar la cancelación y la liberación en una misma transacción, ninguna
liberación se pierde.

## Costo aceptado
El timeout descarta respuestas que habrían llegado tarde, y un deadline cercano a la latencia
habitual de Espacios corta casi todas las peticiones. Tras cancelar, el puesto se libera unos
segundos después (consistencia eventual). Queda un riesgo residual: si después de ocupar fallan a
la vez el guardado de la reserva, la liberación directa y el encolado, el puesto queda ocupado sin
reserva. Sin circuit breaker, mientras Espacios esté lento cada petición espera el deadline
completo.

## Consecuencias
Con Espacios caído se puede iniciar sesión, listar y cancelar reservas; solo reservar y consultar
disponibilidad responden 503. Como trabajo futuro quedan un proceso de reconciliación que elimine
el riesgo residual y un circuit breaker.
