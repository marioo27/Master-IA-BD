# Análisis comparativo de proveedores

## 1. Resultado de la comparativa

La tabla muestra que los tres modelos responden bien en general, pero con diferencias claras en velocidad, coste y estilo de respuesta.

- OpenAI: muy buena calidad general, respuestas directas y ajustadas al contexto. Tiene un coste muy bajo y una latencia muy buena.
- Claude: muy buena calidad en mensajes de atención al cliente. Tiene latencia buena y suele responder con tono natural y amable.
- Gemini: responde de forma muy detallada y muy útil en algunos casos, pero suele generar mucho más texto y por tanto gastar más tokens de salida.

## 2. ¿Por qué un modelo gasta muchos más tokens que otro?

La diferencia no viene solo del texto que pedimos, sino también de la forma en que cada proveedor:

- tokeniza el prompt y la respuesta,
- interpreta las instrucciones del sistema,
- decide cuánta explicación incluir,
- genera respuestas más largas o más estructuradas,
- aplica políticas internas distintas de estilo y longitud.

En la práctica, aunque el usuario haga la misma pregunta a todos, un modelo puede producir un texto mucho más largo sin que la pregunta sea más compleja. Eso se refleja en una diferencia grande en `tokens_salida`.

Gemini es el caso más claro: en varios correos genera respuestas más largas y más formales, y por eso tiene un número de tokens de salida mucho mayor que OpenAI o Claude, incluso cuando la tarea es equivalente.

## 3. ¿Qué modelo elegir para 2.000 correos al mes?

Yo elegiría OpenAI para 2.000 correos al mes.

### Motivos

- Tiene una excelente relación calidad/precio.
- Las respuestas son muy útiles para atención al cliente y suelen ser breves y aplicables.
- La latencia es muy baja, lo que ayuda a mantener un flujo de trabajo ágil.
- El coste por correo es más bajo que Claude y mucho más bajo que Gemini.

### Comparación rápida

- OpenAI: mejor equilibrio entre calidad, coste y velocidad.
- Claude: muy buena calidad, pero algo más caro y a veces un poco más verboso.
- Gemini: muy buena redacción, pero suele gastar muchos más tokens y, por tanto, aumenta el coste por respuesta.

En resumen, para un volumen alto como 2.000 correos al mes, el mejor equilibrio es OpenAI: mantiene buena calidad sin elevar el coste ni la latencia de forma excesiva.
