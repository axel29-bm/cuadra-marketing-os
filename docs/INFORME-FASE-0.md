# Informe de la Fase 0 · Cuadra Marketing OS

Fecha: 14 de octubre de 2026.
Qué se hizo: auditoría de Cuadra en solo lectura (`axel29-bm/contatony-2`, commit `0411f76`) e investigación de herramientas gratuitas en las 20 categorías del encargo, con fuente y fecha.
Documentos completos: `docs/AUDITORIA-CUADRA.md` (la auditoría) y `docs/REGISTRO-HERRAMIENTAS-Y-COSTES.md` (el registro de herramientas).

Este informe responde los ocho puntos de la sección 20 del encargo.

---

## 1. Lo que descubrí del producto

**Cuadra existe y funciona, pero todavía no se puede vender ni descargar.**

- Es un sistema contable de escritorio para Windows, con los datos en la PC del contador (una base cifrada por empresa), pensado para el contador que lleva muchas empresas.
- El código está muy avanzado: 22 pantallas, 6 diálogos y 528 métodos de prueba. La CI de GitHub del 14/10/2026 compila y pasa el núcleo y la aplicación. El trabajo «Licencias, vulnerabilidades y SBOM» falló en «Buscar vulnerabilidades»: es un asunto del producto, no del marketing, pero conviene revisarlo antes de una beta.
- Lo que falta para vender, según el propio PRD (§XVIII.4): beta privada con 20 a 30 contadores (no empezó), servicio de licencias y cobro (a medias), instalador firmado y publicado (no hay), términos y política de privacidad revisados por abogado (no existen), casos contables CC-01 a CC-16 firmados (0 firmados; solo CC-01 a CC-06 están escritos) y precio (no está decidido).

**Etapa comercial: prelanzamiento.** El objetivo honesto del marketing en los próximos meses no es vender: es reunir contadores interesados, conseguir participantes para la beta privada y validar el mensaje. Todo llamado a la acción será de interés (lista de espera, participar en la beta, pedir una demostración en vivo), nunca de compra o descarga. El sistema bloquea solo cualquier pieza que diga «descárgalo», «prueba gratis» o un precio.

**El mercado, en dos líneas** (webs oficiales revisadas el 14/10/2026): los programas de escritorio establecidos (CONCAR, SISCONT, StarSoft) no publican precios; las opciones en la nube con empresas ilimitadas sí, por ejemplo Siigo Contador (US$ 500 al año más IGV), NubeCont Multiempresa (S/ 1 490 al año) o ContaUno VIP (S/ 219 al mes). Casi todos repiten superlativos («número uno», «el más usado»), SIRE y «multiempresa ilimitado». Un hueco posible para Cuadra es el escritorio moderno con los datos en la PC, pero es una **hipótesis**: hay que validarla conversando con contadores antes de construir la campaña sobre ella.

Dos fuentes del repositorio están desactualizadas y lo anoto para no repetir sus errores: `docs/FALTANTES.md` (varias filas ya están hechas según PROGRESO) y `GUIA-INICIO.md` (dice que ContaExcel es de terceros; la decisión D3 del 10/10 dice que es tuyo).

## 2. Capacidades comerciales: qué está verificado y qué no

Revisé 44 capacidades contra el código, las pruebas, PROGRESO y la CI. Cada una tiene un código (por ejemplo `CU-REG-03`), su evidencia, la frase permitida y los patrones que el auditor bloquea.

| Uso en publicidad | Cantidad | Qué significa |
| --- | --- | --- |
| Permitido | 20 | Se puede afirmar y mostrar |
| Con matices | 12 | Se puede afirmar solo con su aclaración |
| Solo en demostración | 3 | Se muestra en vivo, no se promete en una pieza |
| No anunciar | 9 | En desarrollo, planificado o sin evidencia |

Por estado: 30 implementadas y verificadas, 7 parciales, 4 en desarrollo, 2 planificadas y 1 sin evidencia.

**Lo más fuerte y verificado** (se puede usar hoy):
- Todas tus empresas en una pantalla, con lo que toca hacer en cada una (`CU-EMP-02`, `CU-EMP-03`).
- Pegas tu Excel de compras y ves fila por fila qué va a pasar antes de guardar; si te equivocas, deshaces la importación entera (`CU-REG-03`).
- Importa la propuesta del SIRE descargada de SOL y te muestra las diferencias con tu contabilidad (`CU-SIRE-02`, `CU-SIRE-03`).
- Cierras el mes y queda cerrado de verdad; si se reabre, queda el motivo (`CU-LIB-05`).
- Tus datos se quedan en tu PC, cifrados, con copias que se comprueban solas (`CU-SEG-01`, `CU-SEG-02`).

**Lo que no se puede anunciar todavía:** el envío del SIRE a SUNAT por API (nunca se probó contra SUNAT), el asistente con IA (en desarrollo), el instalador, la prueba de 30 días, el portal de pago, el precio, «funciona sin Internet» (depende del servicio de licencias), los vencimientos por último dígito (el cronograma está vacío a propósito) y cualquier cifra de rendimiento en una PC de 4 GB.

**Frases prohibidas en todo el sistema:** «cumple con SUNAT» u «homologado», «usado por N contadores», testimonios, porcentajes u horas de ahorro, escasez inventada, «reemplaza a ContaExcel» y cualquier comparación con nombre.

## 3. Herramientas gratuitas que merecen prueba

El registro completo tiene cada herramienta con coste, licencia, límites, requisitos, privacidad, riesgo, decisión y fuente. Resumen de lo que vale la pena:

| Para qué | Herramienta | Por qué |
| --- | --- | --- |
| IA local | Ollama (MIT) con Qwen3.5 4B o 9B, Gemma 4 o Ministral 3 (Apache-2.0) | Sin coste por uso y sin enviar datos. Depende de la RAM de tu PC |
| IA en la nube, solo contenido público | Gemini (plan gratuito) | Sin tarjeta y con uso comercial, pero Google puede usar lo que envíes para mejorar sus productos, con revisión humana. Nunca datos de clientes ni leads |
| Imágenes | Plantillas HTML y CSS propias, capturadas con Playwright (Apache-2.0) | Texto perfecto, marca coherente, sin GPU y sin licencias raras |
| Animación y vídeo | anime.js (MIT) + Playwright fotograma a fotograma + FFmpeg | Motion graphics sin editor de pago. Remotion queda como opción (gratis hasta 3 personas) |
| Demostraciones del software | OBS (grabación) y FlaUI para guiar Cuadra en tu PC | Pantallas reales con la empresa de ejemplo; nada simulado |
| Subtítulos | faster-whisper (MIT), en local | En una PC potente, 13 minutos de audio en menos de 2 minutos con el modelo pequeño |
| Voz sintética (solo respaldo) | Piper o Kokoro, con voces de licencia verificada | Tu voz es la prioridad; esto es para pruebas o piezas sin narrador |
| Música | Pixabay Music, Incompetech (con crédito), pistas CC0 | Cada pista queda registrada con su licencia |
| Programar publicaciones | Meta Business Suite, YouTube Studio, TikTok Studio y LinkedIn (nativos y gratis); Buffer Free como apoyo | Sin API ni revisiones de app |
| Encuestas | Tally o Google Forms | Gratis y con exportación |
| Landing y formulario | Cloudflare Pages + Worker + D1 | Gratis con límites amplios y uso comercial permitido |
| Analítica | Cloudflare Web Analytics, Umami | Sin cookies, sin banner de consentimiento |
| Copias | Copia verificada de SQLite + restic + rclone hacia tu Google Drive | Cifradas y comprobadas |
| Monitorización | Healthchecks.io (20 controles gratis) | Avisa si una tarea programada deja de correr |

**Descartadas, con motivo:** CapCut (la música comercial solo se puede publicar en TikTok y sus términos piden una licencia amplia sobre tu contenido), Vercel Hobby (prohíbe anunciar la venta de un producto), GitHub Pages como landing comercial, FLUX.1 [dev] (el modelo no se puede usar en una actividad que genera ingresos), n8n como motor central (su licencia solo permite uso interno y exige un servidor aparte; basta un orquestador propio pequeño), GitHub Models (se retiró el 30/07/2026), Cerebras y Llama 4 (sin plan gratuito permanente o con licencia restrictiva).

**Higgsfield** (el conector instalado en el proyecto): queda en reserva. Su plan gratuito no incluye créditos, sus términos permiten entrenar con lo que subes y cualquier generación consumiría tus créditos. No genero nada con él sin tu autorización explícita.

## 4. Arquitectura propuesta

Un programa en Python que corre en tu PC, con una base SQLite y archivos de configuración versionados en git. Nada depende de un servicio de pago.

```
 Configuración en git (TOML)                 Base local (SQLite, espacio/mos.db)
 productos · capacidades · marcas  ───────▶  ideas · campañas · piezas y versiones · revisiones
 fuentes · herramientas · licencias          aprobaciones · publicaciones · métricas · leads
                                             tareas de agentes · errores · autorizaciones · auditoría
                    │
   11 agentes = contrato + prompt + criterios de éxito
   director · investigador · radar · estratega · copywriter · director creativo
   productor audiovisual · community manager            → razonan (modo asistido, local o externo)
   leads · analista · auditor de calidad                → código determinista, sin IA
                    │
   Fábrica: plantillas HTML/CSS ─▶ Playwright ─▶ PNG, PDF, MP4 · FFmpeg · subtítulos locales
                    │
   Auditor (barrera) ─▶ tu aprobación ─▶ paquete de publicación ─▶ programador nativo o manual
                    │                                                      │
   Registro con prueba (URL o id externo) ◀────────────────────────────────┘
```

Claves del diseño:
- **Un agente es un contrato**, no un proceso suelto: entradas, salida con esquema, criterios de éxito, límite de intentos (3), de subtareas (10) y de profundidad (3), plazo y registro de cada paso. Ninguna tarea se marca «completada» si su salida no pasa la validación.
- **Cuatro modos de IA.** Determinista (sin IA). Asistido, por defecto: el sistema prepara el prompt completo y tú, o Claude Code en este proyecto, lo resuelven con la IA que ya tienes. Local, con Ollama. Externo: apagado hasta que lo autorices, con clave solo en variables de entorno, tope diario de llamadas y bloqueo automático de prompts con correos o teléfonos.
- **El auditor de calidad es la barrera.** Contrasta cada texto con la matriz de capacidades, la etapa comercial, los precios, los datos personales, las fuentes de noticias y el estilo. Si encuentra un bloqueo, la pieza vuelve a corrección.
- **Nada se da por publicado sin prueba.** La base exige la URL o el id externo para marcar una publicación como hecha.

## 5. Qué funciona sin API de pago

Todo el sistema base:
- Base de datos, matriz de capacidades, auditor, motor de tareas y línea de comandos (ya funcionan).
- Los 11 agentes en modo asistido o local.
- Producción de imágenes, carruseles, PDF y vídeos animados desde plantillas.
- Subtítulos locales, montaje de vídeo y limpieza de audio.
- Calendario, biblioteca de contenidos, aprobaciones, registro de publicaciones, leads con consentimiento y métricas (manuales o desde CSV exportado de cada red).
- Copias de seguridad verificadas y panel web local.

Sobre tu suscripción de Claude: los términos de consumo prohíben el acceso automatizado salvo con clave de API o permiso explícito. Por eso Claude Code queda como herramienta de trabajo supervisada (tú la abres y la miras), no como motor oculto de agentes desatendidos.

## 6. Qué no se puede automatizar gratis o necesita aprobación externa

| Tema | Situación |
| --- | --- |
| Publicar por API en tu Página de Facebook | En modo desarrollo solo lo ven quienes tienen rol en la app; para público hace falta App Review de Meta |
| TikTok por API | Sin auditoría todo queda privado, y la auditoría rechaza las herramientas para publicar en cuentas propias. Se programa en TikTok Studio |
| Página de empresa en LinkedIn por API | Solo para organizaciones legales registradas, con revisión en dos niveles |
| Instagram y YouTube por API | Posibles para cuentas propias, pero hay que confirmarlo con una prueba real antes de depender de ello |
| WhatsApp Cloud API | Cobra cada mensaje de plantilla entregado. La app WhatsApp Business es gratis y suficiente por ahora |
| Correo masivo (Brevo, Resend) | Exige dominio propio: un Gmail no se puede autenticar |
| Dominio | El único gasto difícil de evitar: un `.pe` o `.com.pe` cuesta S/ 110 al año en punto.pe, y un `.com` unos USD 10,46 al año en Cloudflare. Mientras tanto, la landing puede vivir en un subdominio gratuito de Cloudflare Pages. **No lo compro: es tu decisión** |
| Contenido tributario o normativo | Necesita la revisión de un contador antes de publicarse. El auditor lo bloquea sin esa revisión |
| Cualquier publicación | Al inicio, toda publicación necesita tu aprobación explícita (niveles 1 y 2) |

## 7. Primera versión funcional

**Ya funciona (Fase 1, en `cuadra-marketing-os`):**
- Núcleo: base SQLite con 28 tablas, migraciones, copias verificadas y registro de errores y auditoría.
- La matriz de 44 capacidades de Cuadra, su producto, sus audiencias (como hipótesis) y la identidad visual provisional (con Geist, licencia OFL).
- El auditor de calidad: bloquea precios sin aprobar, promesas no verificadas, datos personales, noticias sin fuente oficial y llamados a descargar o comprar.
- Los 11 agentes con su contrato, el motor de tareas y la línea de comandos (`python -m mos iniciar`, `estado`, `capacidades`, `agentes`, `tarea`, `auditar`, `respaldar`, `autorizar`).

**Sigue sin parar (Fases 2 y 3):** pruebas automáticas, prompts de los agentes, panel web local (productos, campañas, ideas, calendario, biblioteca, aprobaciones, publicaciones, leads, tareas y errores), plantillas visuales (promoción, beneficio, educativo, noticia, carrusel, trivia, meme, lanzamiento, invitación a demo), calendario de 30 días y paquete de lanzamiento con archivos exportados de verdad, y la landing con formulario de lista de espera (en local; publicarla requiere tu autorización).

## 8. Riesgos y límites

1. **Sin firma contable.** Ningún caso contable está firmado. Las piezas que explican un tratamiento tributario quedan en revisión hasta que un contador las revise.
2. **No puedo ejecutar Cuadra.** Es una aplicación de Windows y este entorno es Linux. Las capturas y demostraciones reales las tienes que grabar tú en tu PC; el sistema te deja la lista de tomas, el guion y la empresa de ejemplo preparados.
3. **Tu voz.** Los vídeos con narración necesitan que grabes tú. El sistema prepara el guion, un teleprompter y la limpieza del audio.
4. **Marca y dominio.** «Cuadra» no tiene búsqueda de marca registrada. Conviene buscarlo gratis en INDECOPI antes de abrir cuentas o comprar dominio.
5. **Datos personales.** Una lista de espera es tratamiento de datos personales bajo la Ley 29733 y su nuevo reglamento (D.S. 016-2024-JUS, vigente desde el 31/03/2025). Antes de publicar el formulario hacen falta: aviso de privacidad con el contenido mínimo, consentimiento expreso y **separado** para recibir publicidad, inscribir el banco de datos de interesados ante la autoridad (es gratis; no hacerlo se multa con 0,5 a 5 UIT) y declarar si los datos se guardan en servidores fuera del Perú. Los correos comerciales llevan «PUBLICIDAD» en el asunto y una forma de darse de baja (Ley 28493). El sistema ya guarda finalidad, fecha y versión del consentimiento, y permite exportar y borrar los datos de una persona. Esto no es asesoría legal: conviene que un abogado revise el aviso de privacidad.
6. **Planes gratuitos que cambian.** Varias condiciones quedaron PENDIENTES porque la página oficial no cargó o es ambigua. Cada una está listada en el registro con lo que hace falta para cerrarla.
7. **ContaExcel.** Si tiene usuarios, son la audiencia más cercana para la beta, pero escribirles exige una base legítima (que hayan aceptado recibir noticias).
8. **Imágenes de referencia.** No llegaron adjuntas. Mientras no las subas, uso la identidad del sistema de diseño de Cuadra adaptada a publicidad: fondo blanco, azul noche, acento azul y verde lima de realce.

## Lo que necesito de ti (con lo que hago mientras tanto)

1. **Sube las imágenes de referencia** al proyecto. Mientras tanto sigo con la identidad provisional.
2. **¿ContaExcel tiene usuarios a los que puedas escribir con su permiso?** Mientras tanto, el embudo arranca con contenido educativo y la lista de espera.
3. **¿Hay un contador que pueda revisar contenido normativo?** Mientras tanto, las noticias tributarias se preparan pero quedan bloqueadas.
4. **¿Cuánta RAM y qué tarjeta gráfica tiene tu PC?** Con eso elijo el modelo local. Mientras tanto, todo corre en modo asistido.
