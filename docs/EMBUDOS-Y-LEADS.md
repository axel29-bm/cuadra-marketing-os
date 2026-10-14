# Embudos y leads

Cómo pasa un contador de «no te conozco» a «quiero probarlo», y cómo se guardan sus datos sin romper la ley ni su confianza. Esto no es asesoría legal: los puntos marcados **validar con abogado** deben revisarse antes de publicar el formulario.

## 1. El embudo de Cuadra en prelanzamiento

Cuadra no se vende todavía (ver `docs/AUDITORIA-CUADRA.md`). El embudo termina en la **beta privada**, no en una compra.

| Elemento | Definición para Cuadra hoy |
| --- | --- |
| 1. Público | Contador independiente o estudio pequeño que lleva varias empresas (hipótesis en `productos/cuadra/audiencias.toml`) |
| 2. Problema | Cerrar el mes de muchas empresas a la vez, cuadrar compras y ventas con la propuesta del SIRE, importar desde Excel sin errores |
| 3. Contenido de atención | Situaciones reales del oficio: memes, trivias, novedades normativas con fuente oficial |
| 4. Contenido de interés | Carruseles educativos y vídeos cortos que muestran una pantalla real con la empresa de ejemplo |
| 5. Prueba de confianza | Demostraciones grabadas sin cortes engañosos, historia del desarrollo, datos en la PC del contador |
| 6. Oferta | Lugar en la beta privada y una demostración en vivo de 20 minutos. Nunca un precio |
| 7. Llamado a la acción | «Quiero participar en la beta» · «Pide una demostración» · «Escríbeme por WhatsApp» |
| 8. Captura | Formulario de la landing (lista de espera) o mensaje que inicia el propio contador |
| 9. Seguimiento | Respuesta en menos de 48 horas, una pregunta para cualificar (cuántas empresas lleva, qué usa hoy) y propuesta de demostración |
| 10. Cualificación | Lleva 5 o más empresas, usa Windows, hoy trabaja con Excel u otro sistema, tiene interés en probar |
| 11. Conversión | Entra a la beta privada (estado `BETA`) |
| 12. Métrica | Inscripciones con consentimiento, solicitudes de demostración, demostraciones hechas, ingresos a la beta |

Los estados de un lead en el sistema: `NUEVO → CONTACTADO → CUALIFICADO → DEMO_AGENDADA → DEMO_HECHA → BETA` (más adelante `PROPUESTA → GANADO`), y en cualquier momento `PERDIDO` o `NO_CONTACTAR`.

## 2. Qué datos se guardan y por qué

Solo lo necesario para responder y cualificar. Nada sensible.

| Campo | Para qué | Obligatorio |
| --- | --- | --- |
| Correo o teléfono | Responder | Uno de los dos |
| Nombre | Saludar | No |
| Problema principal | Ofrecer la demostración adecuada | No |
| Empresas que lleva | Cualificar | No |
| Fuente y campaña | Saber qué funcionó | Lo pone el sistema |
| Consentimiento principal, finalidad, fecha, versión del aviso y medio | Probar que la persona aceptó (la carga de la prueba es nuestra) | Sí, si vino de un formulario |
| Consentimiento para publicidad | Enviarle novedades comerciales. **Va aparte** y no está premarcado | No |
| Estado, próxima acción y fecha de seguimiento | No dejar a nadie sin respuesta | Lo pone el sistema |

No se piden RUC, DNI, claves SOL ni datos de los clientes del contador.

## 3. Reglas que el sistema ya aplica

Implementadas en `mos/leads.py` y probadas en `tests/test_leads.py`:

- **Sin duplicados.** El correo se normaliza (minúsculas, sin espacios) y el teléfono se lleva al formato +51. Registrar a la misma persona dos veces actualiza el registro y deja un evento `REINGRESO`.
- **Consentimiento probado.** Si el lead viene de un formulario, se guarda la finalidad, la fecha, la versión del aviso aceptado y el medio. La base rechaza un consentimiento sin fecha o sin finalidad.
- **Publicidad aparte.** La base no permite consentimiento de publicidad sin el consentimiento principal.
- **Baja respetada.** `python -m mos lead baja --contacto …` pone el lead en `NO_CONTACTAR`, quita el consentimiento de publicidad y guarda el hash del contacto en la lista de supresión. Si la persona aparece en una lista vieja reimportada, sigue sin recibir publicidad.
- **Acceso.** `python -m mos lead acceso --contacto …` genera un archivo con todos sus datos y su historial para entregárselos.
- **Supresión.** `python -m mos lead suprimir --contacto …` borra los datos y el historial. Queda solo el hash para no volver a escribirle. La auditoría registra que se suprimió, sin el contacto.
- **Importación prudente.** `python -m mos lead importar` salta las filas sin consentimiento.
- **Local primero.** Los leads viven en `espacio/mos.db`, en la PC de Didi. No se suben a ningún servicio sin autorización, y nunca entran en un prompt de IA (el proveedor rechaza prompts con correos o teléfonos).

## 4. Requisitos legales antes de publicar el formulario

Fuente: investigación del 14/10/2026 sobre la Ley 29733, su reglamento (D.S. 016-2024-JUS, vigente desde el 31/03/2025), la Ley 28493 y el Código de Protección al Consumidor (Ley 29571). Los artículos citados están en el registro de investigación.

| Requisito | Qué hacer | Estado |
| --- | --- | --- |
| Aviso de privacidad con el contenido mínimo (reglamento art. 6.1) | Identidad y domicilio del responsable, finalidades, destinatarios, consecuencias de no dar los datos, transferencias, plazo de conservación y cómo ejercer los derechos | Borrador en la landing (Fase 3). **Validar con abogado** |
| Consentimiento libre, previo, expreso e inequívoco | Casillas sin premarcar, una por finalidad | Diseñado así en el formulario |
| Consentimiento separado para publicidad (art. 26) | Segunda casilla opcional | Implementado en el sistema |
| Inscribir el banco de datos «Interesados» en el Registro Nacional de Protección de Datos Personales | Trámite gratuito y de aprobación automática. No hacerlo se multa con 0,5 a 5 UIT | **Pendiente: lo hace Didi** antes de captar |
| Flujo transfronterizo (art. 21.2) | Si los datos pasan por un servidor fuera del Perú (Cloudflare, Google, Meta, un servicio de correo), declararlo en el aviso y comunicarlo e inscribirlo | **Validar con abogado** cuando se elija dónde vive el formulario |
| Derechos ARCO en plazo | Información 8 días hábiles; acceso 20; rectificación, cancelación y oposición 10 | Comandos `acceso` y `suprimir` listos; falta el correo de contacto para derechos |
| Incidentes en 48 horas | Procedimiento escrito para avisar a la autoridad y a los titulares | Ver `docs/SEGURIDAD-Y-PRIVACIDAD.md` |
| Correo comercial (Ley 28493) | «PUBLICIDAD» en el asunto, remitente con domicilio, baja en un clic, procesada en menos de 2 días | Hecho en `campanas/lista-espera-beta/secuencia-seguimiento.md` |
| Contacto masivo (Código art. 58.1 e) | Nada de llamadas, SMS, WhatsApp ni correos masivos a quien no lo pidió | Regla del sistema |
| No comprar ni alquilar bases de datos | Prohibido por el sistema | Regla del sistema |

**Preguntas para el abogado:** si un contador cuenta como consumidor para el Código; cómo declarar el flujo transfronterizo de cada proveedor; el texto del aviso y de las casillas; cuánto tiempo conservar los leads; si hace falta Oficial de Datos Personales; y el Libro de Reclamaciones cuando haya venta en línea.

## 5. Contactos de ContaExcel

Si ContaExcel tiene usuarios, son la audiencia más cercana para la beta. Escribirles exige una base legítima: que hayan aceptado recibir noticias, o que la relación existente lo permita según el abogado. Hasta saberlo, **no se les escribe en masa**; se les puede invitar con una publicación pública o un aviso dentro del propio ContaExcel si Didi lo decide.

## 6. Secuencia de seguimiento (con consentimiento)

Los textos listos para usar están en `campanas/lista-espera-beta/secuencia-seguimiento.md` y las respuestas a «BETA» y «DEMO», con la pregunta de consentimiento, en `campanas/lista-espera-beta/mensajes-y-demo.md`.

Los días 3 y 10 son solo para quien aceptó novedades (publicidad); la bienvenida y el aviso de apertura, para todos los de la lista. Cada mensaje lo envía Didi.

1. **Día 0.** Gracias por anotarte. Qué es la beta, qué no es (no hay precio ni descarga todavía) y una pregunta: cuántas empresas llevas y qué usas hoy.
2. **Día 3.** Un vídeo corto de una pantalla real con la empresa de ejemplo, ligado al problema que contó.
3. **Día 10.** Invitación a una demostración en vivo de unos 30 minutos.
4. **Al abrir la beta.** Aviso con los cupos reales y los requisitos (Windows, número de empresas).

Cada mensaje incluye cómo darse de baja. Si no responde a los tres primeros, el lead pasa a `PERDIDO` y no se le escribe más.
