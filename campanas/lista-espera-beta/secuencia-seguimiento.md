# Secuencia de seguimiento con consentimiento

Qué escribir después de que alguien entra a la lista. La envías tú, una persona a la vez, por el mismo medio en que te escribió. El sistema te recuerda a quién toca (`python -m mos lead seguimientos` o la pantalla Leads del panel), pero no envía nada.

## Quién recibe qué

| Mensaje | Quién lo recibe | Por qué se puede |
| --- | --- | --- |
| Día 0: bienvenida | Todos los que dijeron SÍ a la lista | Es la respuesta a su pedido |
| Día 3: el problema que contó | Solo quien aceptó novedades (`--publicidad`) | Es publicidad: necesita el consentimiento aparte |
| Día 10: invitación a demostración | Solo quien aceptó novedades | Es publicidad |
| Apertura de la beta | Todos los de la lista | Es la finalidad que aceptaron: avisarles cuando abra |

Si alguien no responde a los mensajes del día 0, 3 y 10, pasa a `PERDIDO` y no se le escribe más (`python -m mos lead actualizar [uid] --estado PERDIDO`). Si alguien escribe BAJA, NO o «no me escribas», se le da de baja ese mismo día: `python -m mos lead baja --contacto [su correo o número]`. Queda en la lista de supresión y no vuelve a recibir publicidad aunque reaparezca en otra lista.

## Día 0 · Bienvenida (va en la misma conversación, ver `mensajes-y-demo.md`)

Ya está cubierta por la respuesta a «BETA». Anota en el lead cuántas empresas lleva y qué problema contó, y deja la próxima acción para el día 3 si aceptó novedades:

```powershell
python -m mos lead actualizar [uid] --estado CONTACTADO --proxima "Día 3: vídeo sobre su problema" --fecha [AAAA-MM-DD]
```

## Día 3 · El problema que contó

Elige la pieza que mejor responde a lo que dijo. Si contó que pierde tiempo digitando, el vídeo de importar Excel (C18); si su problema es el cierre, el de C13; si es el SIRE, la guía C10.

> Hola, [nombre]. El otro día me contaste que [su problema, con sus palabras]. Te comparto un vídeo corto de cómo lo estamos resolviendo en Cuadra: [enlace a la publicación].
>
> ¿Así lo harías tú o le cambiarías algo? Tu respuesta me ayuda a decidir qué sigue.
>
> Si prefieres que no te escriba más, responde BAJA.

Cuando tengas capturas reales de la pantalla con la empresa de ejemplo, este mensaje mejora mucho: una captura del caso que contó vale más que cualquier animación.

## Día 10 · Invitación a una demostración

> Hola, [nombre]. Estoy haciendo demostraciones en vivo de Cuadra, de unos 30 minutos por videollamada y con una empresa de ejemplo. Te muestro [lo que más se acerca a su problema].
>
> ¿Te acomoda [día y hora] o [día y hora]?
>
> Si prefieres que no te escriba más, responde BAJA.

Si acepta: `--estado DEMO_AGENDADA`. Después de la demostración, el mensaje del punto 5 de `mensajes-y-demo.md`.

## Apertura de la beta

Se escribe cuando la beta tenga fecha real, cupos reales y requisitos confirmados. No antes.

> Hola, [nombre]. Te escribo porque estás en la lista de la beta privada de Cuadra: abrimos el [fecha] con [número real] lugares.
>
> Requisitos: Windows [versión mínima confirmada] y [lo que haga falta]. La beta [es gratuita / tiene estas condiciones: completar solo con lo decidido].
>
> ¿Quieres uno de los lugares? Responde SÍ y te explico cómo instalarlo.
>
> Si ya no te interesa, responde BAJA y te saco de la lista.

## Si el seguimiento es por correo

Solo para quien te dio su correo y aceptó novedades. Además del mismo texto:

- **Asunto:** empieza con «PUBLICIDAD:» (Ley 28493), por ejemplo «PUBLICIDAD: el vídeo del cierre de mes que te comenté». Pendiente de confirmar con el abogado si hace falta cuando la persona lo pidió; mientras tanto se pone.
- **Remitente:** tu nombre y un correo que respondas tú. Al pie, el nombre de quien envía y su domicilio.
- **Baja:** «Si no quieres recibir más correos, responde a este con la palabra BAJA.» Se procesa en menos de 2 días hábiles.
- **Envío:** uno por uno desde tu correo. Nada de envíos masivos ni herramientas de correo masivo sin tu autorización y sin el aviso de privacidad publicado.

## Lo que no se hace

- Escribir a quien no lo pidió, aunque sea colega o esté en un grupo.
- Usar los contactos de ContaExcel sin la base legal que confirme el abogado (`docs/EMBUDOS-Y-LEADS.md`, sección 5).
- Insistir: tres mensajes sin respuesta y se detiene.
- Prometer un lugar en la beta, un precio especial o una fecha.
