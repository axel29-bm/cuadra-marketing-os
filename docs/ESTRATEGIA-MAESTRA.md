Estado: versión 1, 14/10/2026. Se revisa en la revisión semanal de los domingos y cada vez que cambie la etapa comercial o la matriz de capacidades.

# Estrategia maestra · Cuadra en prelanzamiento

Qué queremos lograr con el marketing de Cuadra en los próximos 90 días y con qué reglas. Este documento no reemplaza a sus fuentes: si algo de aquí contradice `productos/cuadra/capacidades.toml`, `docs/AUDITORIA-CUADRA.md` o `campanas/lista-espera-beta/campana.toml`, mandan ellos y este documento se corrige.

Documentos hermanos: `docs/ESTRATEGIA-EDITORIAL.md` (qué se publica y cómo) y `docs/METRICAS-Y-EXPERIMENTOS.md` (cómo sabemos si funciona).

## 1. Dónde estamos

| Tema | Situación al 14/10/2026 | Fuente |
| --- | --- | --- |
| Etapa comercial | Prelanzamiento. Nada se vende ni se descarga | `producto.toml`, AUDITORIA §3 |
| Producto | La mayoría del MVP está en el código, con 719 pruebas; no hay versión publicada ni instalador firmado | AUDITORIA §1 y §3 |
| Precio y fecha | No existen. No se publican ni se insinúan | CU-DIS-04 |
| Validación contable | Pendiente: ningún caso contable está firmado por un contador colegiado | `capacidades.toml` [meta] |
| Beta privada | No empezó. El PRD la plantea con 20 a 30 contadores | AUDITORIA §3 |
| Nombre | «Cuadra» es provisional; falta la búsqueda en INDECOPI | `producto.toml`, ROADMAP |
| Presupuesto | S/ 0 al mes | `producto.toml`, REGISTRO-HERRAMIENTAS-Y-COSTES |
| Campaña en curso | Lista de espera de la beta privada, del 15/10/2026 al 13/11/2026, 26 piezas | `campana.toml` |

**Qué significa:** el marketing de estos meses no vende. Su trabajo es reunir contadores interesados con su consentimiento, conseguir conversaciones y demostraciones que nos enseñen qué les pesa, y llegar a la apertura de la beta con candidatos cualificados. Todo llamado a la acción es de interés: escribir «BETA», pedir una demostración o, cuando Didi lo autorice, anotarse desde la página de la lista de espera (la landing). Al interesado registrado en la base, el sistema lo llama «lead».

## 2. Posicionamiento honesto

**Frase de posicionamiento** (de uso interno; no es un titular):

> Para el contador peruano que lleva muchas empresas, Cuadra es un sistema contable de escritorio para Windows, con los datos en su PC, que le muestra todas sus empresas en una pantalla y le ayuda a registrar, cotejar con el SIRE y cerrar cada mes con control. Está en desarrollo y lo construimos con contadores.

Tres ideas sostienen ese lugar:

1. **La cartera completa a la vista.** Suponemos que el dolor de quien lleva muchas empresas no es registrar una compra, sino saber qué falta en cada empresa (CU-EMP-02, CU-EMP-03).
2. **Control antes que velocidad.** Vista previa antes de importar, cotejo con la propuesta del SIRE y un cierre que queda cerrado. No prometemos rapidez porque no la hemos medido en la PC del cliente.
3. **Tus datos en tu PC.** Base cifrada por empresa y copias que se comprueban solas (CU-SEG-01, CU-SEG-02).

**Cómo hablamos de nosotros:** con la verdad de la etapa. Decimos qué hace hoy en nuestras pruebas, qué tiene matices y qué todavía no existe, como en la pieza C16. Esa transparencia es parte del posicionamiento.

**Contexto de mercado (solo interno).** Según lo observado en webs oficiales el 14/10/2026 (`INFORME-FASE-0.md` §1), los programas de escritorio establecidos no publican precios, varias opciones en la nube sí, y casi todos repiten superlativos, «SIRE» y «multiempresa ilimitado». Un hueco posible es el escritorio moderno con los datos en la PC, pero es una **hipótesis** que se valida conversando con contadores. Los competidores de `producto.toml` no se nombran en ninguna pieza: la comparación pública exige prueba previa y validación legal (D. Leg. 1044).

## 3. Audiencias (hipótesis a validar)

Las tres audiencias de `audiencias.toml` tienen naturaleza `HIPOTESIS`. Ninguna está observada todavía.

| Audiencia | Quién creemos que es | Dolores que suponemos | Canales que suponemos | Prioridad en 90 días |
| --- | --- | --- | --- | --- |
| `contador-multiempresa` | Contador independiente con varias empresas pequeñas, en Windows, entre Excel, SOL y un sistema contable | Saltar de empresa en empresa; semana de vencimientos; pasar a mano lo que ya está en Excel o en el SIRE; errores al cierre | Facebook, YouTube, TikTok, WhatsApp, grupos de colegios de contadores | Principal: es la audiencia de la campaña |
| `estudio-contable-pequeno` | Estudio con pocas personas y una cartera amplia; decide un responsable | Saber el estado de cada empresa sin preguntar; respaldo de toda la cartera; tiempo de digitación | LinkedIn, Facebook, YouTube | Secundaria: LinkedIn y demostraciones |
| `contador-en-formacion` | Estudiante de los últimos ciclos o recién colegiado | Aprender el SIRE y los cierres en la práctica; herramientas caras | TikTok, Instagram, YouTube | Alcance, no beta: sin cartera no puede probar el uso real |

**Cómo se validan.** En cada conversación que empiece un contador se hacen las preguntas de `campanas/lista-espera-beta/mensajes-y-demo.md`: cuántas empresas lleva y qué usa hoy. Las respuestas se guardan en el lead (`--empresas`, `--problema`) solo con su consentimiento. Una audiencia pasa a `OBSERVADA` cuando las conversaciones reales la confirman; propuesta (hipótesis): al menos 10 conversaciones de ese perfil con el mismo dolor principal. Se revisa el 08/11/2026.

**Objeciones previstas y la respuesta verdadera**

| Objeción | Respuesta que sí podemos dar |
| --- | --- |
| «¿Cuánto cuesta?» | Todavía no tiene precio. La beta es para probarlo y decirnos qué le falta |
| «¿Y si se pierde mi información?» | Copias cifradas que se comprueban solas y una clave de recuperación para abrir tus empresas en otra PC (CU-SEG-02, CU-SEG-04) |
| «No tengo tiempo para migrar» | Puedes traer tu libro diario desde Excel o desde el TXT del PLE y comparar el balance cuenta por cuenta (CU-MIG-01, con su matiz) |
| «Ya tengo mi sistema y mis plantillas» | No discutimos: invitamos a ver una demostración con la empresa de ejemplo y escuchamos qué le falta |
| «Necesito varios usuarios a la vez» | Hoy no: el multiusuario está planificado, no hecho. Se dice así |
| «Mi equipo ya sabe usar el sistema actual» | Se escucha y se anota; no hay argumento que dar sin datos |
| «Todavía no tengo clientes» | La empresa de ejemplo permite practicar sin miedo (CU-DEM-01), pero la beta prioriza a quien ya lleva empresas |

## 4. Propuesta de valor (solo lo que se puede afirmar)

Solo entran capacidades con uso `PERMITIDO` o `CON_MATICES`. Las que tienen matiz lo llevan siempre que se mencionan.

| Promesa | Frase permitida (de la matriz) | Código | Matiz obligatorio |
| --- | --- | --- | --- |
| Cartera a la vista | Todas tus empresas en una pantalla, con lo que toca hacer en cada una | CU-EMP-02 | — |
| | Te avisa de correlativos faltantes, posibles duplicados y meses sin cerrar | CU-EMP-03 | — |
| | Pensado para el contador que lleva muchas empresas | CU-EMP-01 | Sin prometer rendimiento con cientos o miles de RUC |
| | Escribe Ctrl+K y llega a cualquier empresa, comprobante o cuenta | CU-EMP-05 | — |
| | Saca el mismo reporte de varias empresas en un solo paso | CU-EMP-07 | — |
| Registrar sin digitar dos veces | Pegas tu Excel y ves fila por fila qué va a pasar antes de guardar. Si te equivocas, deshaces la importación entera | CU-REG-03 | — |
| | La segunda vez reconoce las columnas de tu archivo sola | CU-REG-04 | — |
| | Aprende qué cuenta usas con cada proveedor y te explica por qué la sugiere | CU-REG-07 | — |
| | Mientras registras la compra, ves el asiento que se va a generar | CU-REG-01 | Tratamientos sin firma de contador colegiado |
| | Trae tu libro diario desde Excel o desde el TXT del PLE y compara el balance cuenta por cuenta | CU-MIG-01 | Sin nombres ni cifras de las bases reales |
| Control del SIRE y del cierre | Importa el ZIP de la propuesta del SIRE tal como lo bajas de SOL, sin duplicar | CU-SIRE-02 | — |
| | Compara la propuesta del SIRE con lo que registraste y te dice qué falta y dónde | CU-SIRE-03 | Tolerancias provisionales sin firma contable |
| | Te muestra los huecos y saltos de fecha en tus series de venta | CU-REG-05 | — |
| | Cierras el mes y queda cerrado de verdad. Si hay que reabrirlo, queda el motivo | CU-LIB-05 | — |
| | Genera los TXT del PLE de diario, mayor, caja, bancos y plan de cuentas | CU-LIB-04 | Aún sin validar con el programa oficial de SUNAT |
| Datos seguros en tu PC | Tu información contable se queda en tu PC, cifrada empresa por empresa | CU-SEG-01 | — |
| | Copias de seguridad que se comprueban solas, y un botón para probar que se pueden restaurar | CU-SEG-02 | — |
| | Cada cambio queda en el historial y casi todo se puede deshacer | CU-SEG-03 | — |
| | No te deja trabajar con la base dentro de una carpeta que se sincroniza, para que no se dañe | CU-SEG-05 | — |
| Probar sin miedo | Una empresa de ejemplo con datos inventados para probar sin miedo | CU-DEM-01 | — |

Las demás frases están en `python -m mos capacidades cuadra --detalle`. Tres capacidades (CU-REG-02, CU-SIRE-01 y CU-SIRE-04) son `SOLO_DEMO`: se pueden mostrar en una demostración en vivo, nunca prometer en una pieza.

## 5. Mensajes prohibidos

El auditor bloquea la mayoría de estas frases, pero la regla vale aunque una variante se le escape.

| No decimos | Por qué | Si preguntan, decimos |
| --- | --- | --- |
| «Descárgalo», «prueba gratis», «30 días gratis», «disponible ya» | No hay instalador publicado ni licencias operativas (CU-DIS-01, CU-DIS-02) | «Todavía no hay descarga pública. Cuando abra la beta, te explicamos cómo instalarlo» |
| Cualquier precio, descuento o «precio de fundador» | No hay precio (CU-DIS-04) | «Todavía no tiene precio» |
| Una fecha de lanzamiento o de apertura de la beta | No está decidida | «No tiene fecha. Si estás en la lista, te avisamos primero» |
| «Cumple con SUNAT», «homologado», «asientos 100 % correctos» | Ningún caso contable firmado; no consta homologación | Lo que hace, sin garantías |
| «Envía tu SIRE automáticamente», «SIRE automático» | El envío por API nunca se probó contra SUNAT (CU-SIRE-05) | «Importa la propuesta que bajas de SOL y la coteja con lo registrado» |
| «Toda tu cartera en un clic», «RUC ilimitados», «1,000 empresas» | Sin medición en la PC de referencia (CU-EMP-01, CU-SIRE-01) | «Está pensado para muchas empresas; todavía medimos el rendimiento» |
| «Con inteligencia artificial» | El asistente está en desarrollo (CU-IA-01) | «No por ahora» |
| «Funciona sin Internet» | Depende del servicio de licencias, que no opera (CU-SEG-06) | Nada, hasta que la licencia funcione |
| «Vencimientos por dígito», «calendario de vencimientos automático» | El cronograma está vacío a propósito (CU-EMP-04) | Nada |
| «PCGE oficial completo», «PLE listo para presentar», «tipo de cambio automático» | Tienen matices en la matriz | La frase permitida, con su matiz |
| «Usado por N contadores», testimonios, «ahorra X horas» | No hay usuarios ni mediciones | Nada |
| «Últimos cupos», «solo quedan N» | Escasez inventada | Los cupos reales, cuando existan |
| «Reemplaza a ContaExcel» o cualquier comparación con nombre | Ninguna condición del PRD se cumple y exige validación legal | Nada |
| «Funciona en cualquier PC», requisitos mínimos | Sin evidencia en una PC de 4 GB (CU-DIS-05) | «Es para Windows, de escritorio» |

Una aclaración que sí conviene decir: **Cuadra no es un facturador** ni hace planillas (quedan fuera del producto según el PRD). Así evitamos interesados equivocados.

## 6. Objetivos de los próximos 90 días (del 14/10/2026 al 12/01/2027)

Las ventanas son de trabajo, no fechas prometidas. Las metas marcadas «(hipótesis)» se revisan con datos cada domingo.

| Fase | Ventana | Objetivo | Meta | Condiciones previas |
| --- | --- | --- | --- | --- |
| 1. Lista de espera | Del 15/10/2026 al 13/11/2026 (la campaña) | Primeros contadores en la lista, con consentimiento, y saber qué problema les pesa más | 30 contadores con consentimiento: meta inicial que se revisa el 25/10/2026 | Inscribir el banco de datos «Interesados» y tener el aviso de privacidad antes de anotar a nadie |
| 2. Demostraciones | A pedido desde ya; con invitación pública desde C20 (06/11/2026) hasta mediados de diciembre | Mostrar Cuadra en vivo con la empresa de ejemplo y escuchar qué falta | 10 demostraciones hechas (hipótesis) | Horarios definidos antes del 06/11/2026 y un guion de unos 30 minutos |
| 3. Preparar la beta | De mediados de diciembre al 12/01/2027 | Tener candidatos cualificados y el aviso de apertura listo para cuando el producto lo permita | 20 a 30 candidatos cualificados (rango del PRD; hipótesis para esta ventana) | La apertura la decide Didi según el producto (instalador, licencia, requisitos). No se anuncia sin fecha y cupos reales |

**Fechas de decisión ya fijadas** en `campana.toml`: 18/10/2026 (métricas, leads y voz de C13), 25/10/2026 (revisión de la meta y noticia C12 al contador), 01/11/2026 (decidir si se autoriza publicar la landing) y 08/11/2026 (agendar demostraciones y elegir qué tres piezas repetir). Propuesta: cerrar la campaña el domingo 15/11/2026.

**Cualificar también es objetivo.** Un candidato a la beta lleva 5 o más empresas, usa Windows, trabaja hoy con Excel u otro sistema y quiere probar (`EMBUDOS-Y-LEADS.md` §1). El estado del lead lo refleja: `NUEVO → CONTACTADO → CUALIFICADO → DEMO_AGENDADA → DEMO_HECHA → BETA`. Cómo se mide cada fase está en `docs/METRICAS-Y-EXPERIMENTOS.md`.

## 7. Canales y su rol

| Canal | Rol en prelanzamiento | Piezas en la campaña | Cómo se publica |
| --- | --- | --- | --- |
| Facebook (Página) | Canal principal del contador independiente (hipótesis): atención, utilidad e invitación a «BETA» y «DEMO» | 8 | Meta Business Suite, a mano |
| Instagram (cuenta profesional) | Producto real en imagen, carruseles útiles e historias con encuesta | 8 | Meta Business Suite, a mano |
| LinkedIn (perfil de Didi) | Conversación entre profesionales y estudios, en primera persona; guías como documento PDF | 6 | Programación nativa, a mano |
| TikTok | Alcance con humor del oficio y vídeo corto | 2 | TikTok Studio, a mano |
| YouTube (Shorts) | Vídeos cortos del producto; archivo para enviar en el seguimiento | 2 | YouTube Studio, a mano |
| WhatsApp Business (app) | Conversación uno a uno, solo con quien escribió primero | — | A mano; nunca mensajes masivos |
| Landing de la lista de espera | Inscripción con aviso de privacidad y consentimiento separado para publicidad | — | Borrador en `sitio/`; publicarla necesita autorización (`CANALES-Y-PUBLICACION.md`) |
| Correo | Seguimiento solo a quien aceptó recibir novedades | — | Uno por uno desde el correo de Didi; masivo solo con dominio propio y autorización |
| Grupos de colegios de contadores | Canal supuesto en `audiencias.toml` | — | Solo si las reglas del grupo lo permiten y participa Didi en persona; nunca mensajes privados a sus miembros |

Ningún canal se publica por API por ahora. Toda publicación se registra con su enlace; sin enlace no cuenta como publicada.

## 8. Presupuesto: S/ 0 y lo que espera a Didi

El presupuesto mensual es S/ 0 (`presupuesto_mensual_c = 0`). Nada se paga, se publica ni se envía sin la aprobación explícita de Didi, y **no hay publicidad pagada** (anuncios, publicaciones promocionadas ni pagos a terceros) sin su autorización.

| Decisión pendiente | Coste conocido | Mientras tanto | Qué desbloquea |
| --- | --- | --- | --- |
| Publicar la landing en Cloudflare Pages | S/ 0; falta confirmar si Cloudflare pide tarjeta | Inscripción por mensaje | El formulario y el llamado «Únete a la lista de espera» |
| Dominio propio | .pe o .com.pe: S/ 110 al año; .com: unos USD 10,46 al año | Subdominio gratuito `*.pages.dev` | Correo autenticado y más confianza |
| Revisión legal del aviso de privacidad | PENDIENTE: no está estimado | Borrador sin publicar | Guardar datos fuera del chat de cada red |
| Publicidad pagada en cualquier red | Sin presupuesto | Solo alcance orgánico | Más alcance; obligaría a revisar la medición y el consentimiento de cookies |
| IA externa o clave de API | Por uso; precios PENDIENTE | Modo asistido y local | Agentes desatendidos |
| Créditos de Higgsfield | Precios oficiales PENDIENTE | Plantillas propias | Vídeo generativo |
| WhatsApp Cloud API | Por plantilla entregada; tarifa de Perú PENDIENTE | App WhatsApp Business | Mensajes automáticos |
| Cuenta de Google Ads para Keyword Planner | Exige datos de facturación | Search Console y Google Trends | Volúmenes de búsqueda |
| Confirmar la suscripción de Claude | USD 20, 100 o 200 al mes, si no se paga ya | — | Saber si Claude Code es S/ 0 adicional |

Trámites gratuitos que también dependen de Didi: inscribir el banco de datos, buscar «Cuadra» en INDECOPI, conseguir un contador que revise el contenido normativo y grabar su voz para los vídeos.

## 9. Riesgos y cómo se mitigan

| Riesgo | Mitigación |
| --- | --- |
| Captar datos sin base legal (Ley 29733) | Nadie entra a la lista sin banco de datos inscrito, aviso de privacidad y su SÍ; publicidad con consentimiento aparte; baja el mismo día |
| La lista no abre a tiempo y la meta de 30 no se alcanza | Contar las conversaciones mientras tanto, sin guardar datos; revisar la meta el 25/10/2026 |
| Afirmar algo que el producto no hace | Matriz de capacidades, auditor obligatorio y aprobación de Didi ligada a cada versión |
| Contenido contable o tributario equivocado | Fuente oficial, fecha y revisión de un contador; sin revisión no sale (C12 está frenada así) |
| Expectativas de fecha o precio que no podemos cumplir | Respuestas fijas y verdaderas; nunca prometer un lugar, una fecha ni un precio especial |
| El producto no está listo cuando ya hay interesados | La fase 3 prepara candidatos sin anunciar fecha; el aviso de apertura se escribe solo con fecha y cupos reales |
| Nombre ocupado | Búsqueda en INDECOPI antes de comprar dominio o abrir cuentas nuevas |
| Humor que ofende | Reglas de `ESTRATEGIA-EDITORIAL.md`: sin clientes, SUNAT, colegas ni memes de terceros |
| Una sola persona para producir, publicar y responder | Calendario realista, reutilizar piezas entre redes y responder en menos de 48 horas antes que publicar más |
| Piezas con iconos donde irían capturas reales | No simular pantallas; reemplazar con capturas de la empresa de ejemplo cuando Didi las tenga |
| Audiencias equivocadas | Tratarlas como hipótesis y validarlas con las preguntas de cualificación |
| Escribir a usuarios de ContaExcel sin base legítima | Solo invitación pública o aviso dentro de ContaExcel si Didi lo decide; nada masivo sin el visto bueno del abogado |
| Datos personales en prompts de IA | El sistema rechaza prompts con correos o teléfonos; los leads viven solo en la PC |

## 10. Cómo se suma un segundo producto

El sistema está hecho para varios productos sin cambiar el código:

1. **Carpeta del producto:** `productos/<slug>/`, copiando como modelo los archivos de Cuadra:
   - `producto.toml`: público, problemas, propuesta de valor, `etapa_comercial`, `disponible_al_publico`, `precio_definido`, canales, `presupuesto_mensual_c` y marca.
   - `capacidades.toml`: la matriz. Cada capacidad con código propio, estado, uso (`PERMITIDO`, `CON_MATICES`, `SOLO_DEMO` o `NO_ANUNCIAR`), evidencia con fecha, frase, matiz y patrones prohibidos, más sus `prohibicion_global`.
   - `audiencias.toml`: audiencias con `naturaleza = "HIPOTESIS"` hasta validarlas.
2. **Auditoría:** `docs/AUDITORIA-<PRODUCTO>.md` con la evidencia que respalda la matriz. Sin matriz, el auditor no deja afirmar nada del producto.
3. **Marca:** `marcas/<slug>/marca.toml` con su logo, o una marca existente.
4. **Carga:** `python -m mos iniciar` lee todas las carpetas de `productos/` y `marcas/` sin duplicar.
5. **Campañas:** `campanas/<slug-de-campaña>/campana.toml` con `producto = "<slug>"`. Leads, métricas (`--producto`) y presupuesto quedan separados por producto.
6. **Estrategia:** una sección nueva aquí o un documento propio si el producto tiene otra etapa u otro público.

Lo que no cambia: la verdad de cada producto está en su matriz, el auditor no se salta y nada se publica, se paga ni se envía sin Didi.

## 11. Cuándo cambia esta estrategia

- **Cuando Cuadra entre en beta:** se actualiza `etapa_comercial`, se revisa la matriz y se cambian los llamados (`ROADMAP.md`).
- **Cuando cambie una capacidad:** primero `capacidades.toml` con evidencia y fecha, después `AUDITORIA-CUADRA.md` y después este documento.
- **Cada domingo:** se revisan con los datos de la semana las metas marcadas como hipótesis.
