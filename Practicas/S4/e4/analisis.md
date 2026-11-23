# Analisis E4

## P1. Compactacion desde cero

La compactacion se activa cuando hay mas de `MANTENER` mensajes y el ultimo uso supera `UMBRAL_TOKENS`. Los mensajes antiguos se convierten en un resumen y los ultimos seis mensajes se conservan literalmente.

`MANTENER` debe ser par porque el historial alterna mensajes de usuario y asistente. Mantener un numero par conserva el inicio del bloque reciente como mensaje de usuario y evita entregar al modelo un turno inicial incompleto.

Prueba propuesta con al menos diez turnos:

| Configuracion | Entrada antes | Entrada despues | Observacion |
|---|---:|---:|---|
| Umbral 1000, mantener 6 | Registrar en la ejecucion real | Registrar tras primera compactacion | Balance entre frecuencia y conservacion |
| Umbral 500, mantener 6 | Mayor frecuencia | Bloque compacto mas pequeño | Menor contexto, mas llamadas de resumen |
| Umbral 1000, mantener 10 | Menor compactacion total | Mas mensajes recientes | Mayor coste y mejor continuidad |

No se pudo registrar una salida real de la API en este entorno porque no hay clave ni variables de OpenRouter configuradas. La tabla anterior debe completarse con los valores de `r.usage.input_tokens + r.usage.output_tokens` obtenidos en una ejecucion autorizada.

Datos que se deben comprobar: nombre del cliente, identificadores, cantidades, fechas, compromisos y temas pendientes. Preguntar por un dato del primer turno permite evaluar si el resumen lo conserva.

## P2. Registro de pruebas

### Sesion 1

1. Ejecutar `1 lunes`.
2. Guardar una preferencia estable, por ejemplo `idioma=espanol`.
3. Cerrar el proceso.
4. Reiniciar `1 lunes` y comprobar que el hilo continua.

### Sesion 2

1. Ejecutar `1 martes`: el hilo nuevo no comparte mensajes anteriores, pero si las preferencias del cliente 1.
2. Ejecutar `2 lunes` y pedir las preferencias del cliente 1: no se muestran porque el namespace aplica `("clientes", "2")`.
3. Ejecutar `1 lunes` o `1 martes` y pedir «olvidad mis datos».
4. Comprobar `memoria.db` y `hilos.db`: no quedan datos del cliente 1 y siguen los del cliente 2.

La prueba offline del repositorio ejecuta los comprobantes estructurales de aislamiento y borrado con SQLite temporal:

```text
OK: aislamiento por cliente
OK: borrado completo de cliente 1
OK: conservacion de datos del cliente 2
```

El hilo solicitado al borrado puede recrearse despues del uso de la herramienta, porque LangGraph vuelve a guardar el estado al terminar `invoke`. La aplicacion resuelve esto eliminando todos los hilos del cliente despues de procesar una solicitud de borrado, ademas de que la herramienta usa `borrar_datos_cliente` durante la ejecucion.

## Privacidad RGPD

- **Datos:** solo preferencias estables y no sensibles, como idioma, horario habitual o producto favorito. Nunca se deben guardar datos de pago, salud, creencias, origen o identificadores financieros.
- **Almacenamiento:** `hilos.db` contiene checkpoints de conversaciones por `thread_id`; `memoria.db` contiene preferencias dentro del namespace `("clientes", cliente_id)`.
- **Finalidad:** mantener continuidad del hilo y recordar preferencias para personalizar respuestas.
- **Conservacion:** sin periodicidad automaticica definida, por lo que se considera un dato activo hasta que el cliente solicita su supresion. En produccion se deberia fijar una politica temporal y cifrado del almacenamiento.
- **Supresion:** la herramienta `olvidar_preferencias` elimina todas las entradas del namespace y todas las filas de checkpoints cuyo `thread_id` empieza por `<cliente>-`. La capa interactiva repite el borrado tras `invoke` para eliminar un posible ultimo checkpoint recreado.
- **Derechos y control:** el cliente solo puede acceder a su namespace; el modelo no recibe ni decide el `cliente_id`. El acceso a base de datos debe restringirse a la aplicacion y a personal autorizado.
- **Minimizacion y transparencia:** informarle que su preferencia se guarda, por que se guarda y como retirarla. No copiar secretos al repositorio ni subir `.env`, bases SQLite ni datos reales.
