# Operación diaria

La rutina para llevar el marketing de Cuadra en poco tiempo al día. Todo corre en tu PC; nada se publica ni se envía sin que tú lo hagas.

Abre una consola en la carpeta del proyecto. Si usas un espacio distinto del predeterminado, define `MOS_ESPACIO` antes (ver `INSTALACION.md`).

## Cada día (15 a 25 minutos)

1. **Abre el panel:** `python -m mos web`. La página «Hoy» muestra lo que espera por ti: piezas para aprobar, tareas para revisar, publicaciones para hoy o atrasadas, seguimientos de interesados, novedades del radar por verificar y errores.
2. **Aprueba o corrige** las piezas del día siguiente en «Aprobaciones». Si el auditor frenó una, el motivo está en la ficha; corrige el texto en `campanas/<campaña>/campana.toml` y vuelve a cargar:
   ```powershell
   python -m mos campana cargar campanas\lista-espera-beta
   python -m mos campana render campanas\lista-espera-beta
   ```
3. **Programa** lo aprobado: `python -m mos publicacion preparar --pieza <código>` te da el número de la publicación; sube los archivos a la herramienta nativa de la red (ver `CANALES-Y-PUBLICACION.md`) y regístralo con `python -m mos publicacion programar <número> --fecha AAAA-MM-DD`.
4. **Confirma** lo que salió ayer con su enlace: `python -m mos publicacion confirmar <número> --url https://…`.
5. **Responde** a quien escribió «BETA» o comentó. Las respuestas modelo están en `campanas/lista-espera-beta/mensajes-y-demo.md`.
   - **Mientras el banco de datos «Interesados» no esté inscrito** y el aviso de privacidad no esté validado, conversa en el chat de la red sin anotar a nadie fuera de él (`EMBUDOS-Y-LEADS.md`, sección 4).
   - Después, registra solo a quien dio su consentimiento, con la versión del aviso que aceptó:
     ```powershell
     python -m mos lead registrar --producto cuadra --fuente whatsapp --nombre "…" --telefono "…" --consentimiento --version-aviso <versión vigente> --medio "mensaje de WhatsApp"
     ```
6. **Seguimientos del día:** `python -m mos lead seguimientos`. Después de cada contacto: `python -m mos lead actualizar <uid> --estado … --proxima "…" --fecha AAAA-MM-DD`.

## Cada semana (domingo, 45 minutos)

1. **Copia de seguridad verificada:** `python -m mos respaldar`. Copia también la carpeta `espacio\respaldos` a un disco externo o a otra carpeta que no sea la de trabajo.
2. **Métricas:** anota las cifras de cada publicación que ves en la red: `python -m mos metrica registrar --publicacion <número> --nombre alcance --valor 1200 --naturaleza MEDIDA`. También acepta una planilla con columnas `url`, `fecha` y los nombres de métrica (`metrica importar --archivo …`); leer directamente el CSV que exporta cada red llega en la Fase 6.
3. **Embudo:** `python -m mos lead embudo` muestra cuántos interesados hay en cada etapa.
4. **Radar:** revisa las novedades de SUNAT, El Peruano y el MEF en el panel. Una noticia solo se convierte en pieza si tiene enlace a la fuente oficial y la revisa un contador.
5. **Plan de la semana siguiente:** revisa `CALENDARIO.md` de la campaña. Si algo se retrasó, `python -m mos campana mover campanas\lista-espera-beta --semanas 1` corre todas las fechas.
6. **Errores:** `python -m mos errores` no debería mostrar nada pendiente.

## Cada mes

- Revisa la matriz de capacidades con lo nuevo de Cuadra (`python -m mos capacidades cuadra`). Si una función pasa a verificada, ya se puede anunciar; si no, el auditor la sigue frenando.
- Compara las métricas del mes con las metas de cada campaña y decide qué repetir y qué dejar.
- Prueba los derechos de las personas con un interesado ficticio: exporta y suprime sus datos (`lead acceso --contacto …`, `lead suprimir --contacto …`) para comprobar que el procedimiento sigue funcionando.

## Cuando algo sale mal

| Situación | Qué hacer |
| --- | --- |
| Una red rechazó una publicación | `python -m mos publicacion fallo <número> --error "…"` y vuelve a programarla |
| El auditor frena una pieza que crees correcta | Lee el motivo. Si la regla está mal, anótalo como defecto en `PROGRESO.md`; no se aprueba saltándola |
| Alguien pide que borres sus datos | `python -m mos lead suprimir --contacto <correo o teléfono>` el mismo día. Queda solo una huella para no volver a escribirle |
| Alguien pide ver sus datos | `python -m mos lead acceso --contacto <correo o teléfono>` genera el archivo; envíaselo y bórralo |
| Alguien ya no quiere mensajes | `python -m mos lead baja --contacto <correo o teléfono>` |
| La base no abre | Restaura la última copia de `espacio\respaldos` (`INSTALACION.md`, sección 6) |
