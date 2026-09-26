# ADR-003 · Contrato, versionado y evolución (D3)

## Contexto
El sistema tiene dos contratos con consumidores distintos: el `openapi.yaml` de la API pública,
usado por clientes que el equipo no controla, y el `.proto` de Espacios, con un solo consumidor
pero mantenido por otro equipo. Hay que definir qué cambios son compatibles, cuáles exigen una
versión nueva y cómo se enteran los consumidores.

## Alternativas consideradas
- **Versión en la ruta (`/v1`)**, en un header o en el tipo de contenido. La ruta es visible y fácil
  de probar; las otras dejan URLs estables pero son invisibles al navegar.
- **Versión en el paquete del `.proto`** (`colabora.espacios.v1`) o sin versión. Con versión, dos
  versiones pueden servirse a la vez desde el mismo servidor.
- **Campos desconocidos**: ignorarlos (lector tolerante) o rechazarlos con 422, lo que detecta
  errores del cliente pero vuelve incompatible cualquier campo nuevo.
- **Aviso a los consumidores**: solo un registro de cambios, o además marcas en los contratos y
  headers en las respuestas.

## Decisión
Versión mayor en la ruta REST (`/v1`) y en el paquete gRPC, creando una versión nueva solo ante un
cambio incompatible. Agregar campos, rutas o RPC es compatible; eliminar o renombrar campos,
cambiar tipos o volver obligatorio un campo no lo es. En protobuf, los números de campo eliminados
se reservan y nunca se reutilizan. Los campos desconocidos se ignoran, y los cambios se anuncian
con marcas `deprecated`, un `CHANGELOG`, los headers `Deprecation` y `Sunset`, y un período en que
ambas versiones conviven. Los contratos se escriben antes que el código, y una prueba automática
verifica que la API implemente exactamente las rutas del contrato (O4).

## Justificación
Un cambio es compatible si un cliente anterior sigue funcionando sin modificarse. Agregar un campo
solo cumple esa condición si ambos lados ignoran lo que no conocen, por eso el lector tolerante es
requisito de toda la estrategia. En protobuf los campos viajan identificados por número y no por
nombre, así que reutilizar un número haría que un cliente antiguo interprete un dato como otro sin
ningún error. La versión en el paquete permite que Espacios publique una versión nueva sin obligar
a Reservas a actualizarse el mismo día, lo que es necesario con equipos que no despliegan juntos.
La estrategia se aplicó durante el proyecto: al implementar Reservas se agregaron dos campos al
`.proto` (`iniciada` y `sala_nombre`) con números nuevos, sin crear una versión nueva y sin romper
al otro servicio.

## Costo aceptado
La versión queda en la URL de cada recurso. Con el lector tolerante, un campo opcional mal escrito
se descarta sin aviso. Mantener dos versiones vivas duplica código durante la transición, y
escribir el contrato a mano exige una prueba que controle que no se desvíe de la implementación.

## Consecuencias
No se construyó un `/v2`: la estrategia está documentada y se probó con los cambios compatibles del
`.proto`. Todas las respuestas de error usan el formato estándar RFC 9457, que admite campos nuevos
sin romper a los clientes.
