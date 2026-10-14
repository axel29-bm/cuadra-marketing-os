# Mensajes: responder a «BETA» y «DEMO» y pedir una demostración

Textos para copiar y adaptar. Los escribes y envías tú: el sistema no manda mensajes. Reglas que no se rompen:

- Solo se responde a quien escribió primero. No se escribe en frío a nadie (Código de Protección al Consumidor, art. 58).
- Nadie entra a la lista sin decir que sí a la pregunta de consentimiento. La publicidad se pregunta aparte y se puede rechazar.
- No se promete fecha, precio, descarga ni prueba gratis. Si preguntan, se dice la verdad: todavía no hay.
- No se piden RUC, claves SOL, archivos ni datos de clientes. Nunca.

Lo que va entre corchetes se reemplaza. `[enlace al aviso de privacidad]` es la página del aviso cuando esté publicada (Fase 5). Mientras no exista, no anotes a nadie: conversa y avísale que le escribes cuando la lista esté abierta.

## 1. Alguien escribe «BETA»

> ¡Hola, [nombre]! Gracias por escribir.
>
> Cuadra es un sistema contable de escritorio para Windows que estamos construyendo para contadores que llevan muchas empresas. Todavía no está a la venta y no tiene fecha ni precio.
>
> Para anotarte en la lista de la beta privada necesito guardar tu nombre y cómo contactarte, solo para avisarte cuando abra y coordinar una demostración si la quieres. Aquí explicamos cómo cuidamos tus datos y cómo pedir que los borremos: [enlace al aviso de privacidad].
>
> ¿Me autorizas a anotarte con ese fin? Responde SÍ o NO.

Si responde **SÍ**:

> ¡Listo, quedaste en la lista! Una cosa más, y puedes decir que no: ¿te puedo escribir de vez en cuando con novedades de Cuadra (avances y la apertura de la beta)? Si dices que no, igual quedas en la lista y solo te escribo para la beta.
>
> Y para que la beta te sirva: ¿cuántas empresas llevas más o menos y qué usas hoy para la contabilidad?

Regístralo (en el panel, Leads, o con el comando):

```powershell
python -m mos lead registrar --fuente "instagram-dm" --campana lista-espera-beta --nombre "[nombre]" --telefono "[número]" --consentimiento --finalidad "lista de espera de la beta privada" --version-aviso "[versión del aviso]" --medio "mensaje directo"
# agrega --publicidad solo si aceptó las novedades, y --empresas y --problema con lo que contó
```

Si responde **NO**: «Entendido, no guardo tus datos. Si cambias de opinión, escríbenos «BETA» cuando quieras.» No se registra nada.

## 2. Alguien escribe «DEMO»

> ¡Hola, [nombre]! Con gusto te mostramos Cuadra.
>
> Es una videollamada de unos 30 minutos con una empresa de ejemplo y datos inventados. Vas a ver todas las empresas en una pantalla, cómo se importan compras desde Excel con vista previa y cómo se cierra un mes con su lista de control.
>
> Tengo estos horarios: [día y hora], [día y hora], [día y hora]. ¿Cuál te acomoda?
>
> Para agendarla guardo tu nombre y tu contacto, solo para coordinar la demostración ([enlace al aviso de privacidad]). ¿Estás de acuerdo?

Con su sí, regístralo como en el punto 1 y luego márcalo: `python -m mos lead actualizar [uid] --estado DEMO_AGENDADA --proxima "Demo el [día]" --fecha [AAAA-MM-DD]`.

## 3. Preguntas frecuentes (respuestas verdaderas al 14/10/2026)

| Pregunta | Respuesta |
| --- | --- |
| ¿Cuánto cuesta? | Todavía no tiene precio. La beta privada es para probarlo y decirnos qué falta |
| ¿Cuándo sale? | No tiene fecha todavía. Si estás en la lista, te avisamos primero |
| ¿Dónde lo descargo? | Todavía no hay descarga pública. Cuando abra la beta privada, te explicamos cómo instalarlo |
| ¿Funciona en Mac o en el celular? | Es para Windows, de escritorio |
| ¿Dónde quedan mis datos? | En tu PC, cifrados empresa por empresa. No te deja trabajar con la base dentro de OneDrive, Google Drive o Dropbox |
| ¿Envía a SUNAT? | Hoy importa la propuesta del SIRE que descargas de SOL y la coteja con lo registrado. El envío directo a SUNAT todavía no existe |
| ¿Cuántas empresas aguanta? | Está pensado para contadores con muchas empresas. Todavía estamos midiendo el rendimiento, así que no te prometo un número |
| ¿Tiene inteligencia artificial? | No por ahora |
| ¿Puedo pasar mi información de otro sistema? | Puedes traer tu libro diario desde Excel o desde el TXT del PLE y comparar el balance cuenta por cuenta |
| ¿Quién está detrás? | [Tu presentación en una o dos líneas, en primera persona] |

Si preguntan algo que no está aquí y no sabes si Cuadra lo hace, la respuesta es: «Déjame confirmarlo y te respondo», y se revisa la matriz (`python -m mos capacidades`).

## 4. Pedir una demostración en una publicación

Para comentarios o publicaciones propias (ya están en C20 y C22):

> ¿Quieres ver Cuadra funcionando? Te hacemos una demostración en vivo de unos 30 minutos por videollamada, con una empresa de ejemplo. Escríbenos «DEMO» por mensaje y coordinamos el día.

Para responder un comentario que pregunta «¿cómo funciona?»:

> ¡Gracias por preguntar! Si quieres, te lo mostramos en vivo con una empresa de ejemplo. Escríbenos «DEMO» por mensaje y coordinamos.

No se responde en público con datos de nadie ni se pide el número en los comentarios.

## 5. Después de una demostración

> ¡Gracias por tu tiempo, [nombre]! Una pregunta para mejorar Cuadra: ¿qué fue lo más útil y qué te faltó ver?
>
> Si quieres entrar a la beta privada cuando abra, ya estás en la lista. Te escribo solo para eso.

Actualiza el lead a `DEMO_HECHA` y anota lo que contó en `--nota`. Lo que diga no se publica como testimonio sin su permiso escrito.
