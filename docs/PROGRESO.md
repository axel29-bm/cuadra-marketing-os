# Progreso

Bitácora del Marketing OS. Lo más reciente arriba. Cada entrada dice qué se hizo, cómo se verificó, qué falta, los defectos conocidos y el siguiente paso.

---

## 14/10/2026 · Fase 5 adelantada: landing de la lista de espera y documentos de operación

### Hecho

- **Landing** (`sitio/`, `mos/sitio.py`, `python -m mos sitio`): se escribe en `sitio/sitio.toml` y se construye como página estática. Cada sección pasa por el auditor y cada capacidad se cita por su código de la matriz: «lo que ya hace» solo admite capacidades permitidas; las que tienen matices salen con su nota; lo que todavía no existe se dice como tal. Incluye la demostración, la trivia interactiva de la campaña, preguntas frecuentes, el aviso de privacidad en borrador e imagen para compartir. Sin nada cargado desde Internet.
- **Formulario con consentimiento:** nombre y correo; número de empresas y problema, opcionales; y tres casillas sin marcar: demostración, consentimiento (obligatoria) y publicidad aparte. Campo trampa para robots. Mientras falte algo legal, la página sale como borrador: franja visible, sin formulario, con `noindex` y un `robots.txt` que bloquea.
- **`sitio pendientes`** lista lo que falta para publicar: datos del responsable con el código de inscripción del banco de datos, flujo transfronterizo comunicado, aviso validado por un abogado con versión definitiva, y las direcciones de la página y del receptor. `sitio construir --publicable` se niega mientras falte algo.
- **Prueba en local:** `sitio ver` sirve la página en `http://127.0.0.1:8766` con un receptor local que guarda cada inscripción como lead con la evidencia del consentimiento (versión del aviso, fecha, medio y origen de la visita). Quien pide demostración queda con su próxima acción en «Seguimientos».
- **Receptor para Internet** (`sitio/receptor/`, **sin desplegar**): Cloudflare Workers + D1 en plan gratuito, código propio sin dependencias. No guarda la IP (solo su huella con una sal secreta), limita a 5 envíos por hora por conexión, no duplica, y exportar o borrar exige una clave que vive solo en Cloudflare y en tu consola. `sitio importar` trae las inscripciones a tu base y las borra del servidor; si una fila no entra, no borra nada.
- **Documentos:** `CANALES-Y-PUBLICACION.md` (niveles de automatización, canales, recorrido de una pieza y la landing), `OPERACION-DIARIA.md` (rutina diaria, semanal y mensual), `AUTOMATIZACIONES.md` (cada flujo con razón, criterio, comprobación y estado) e `INSTALACION.md` (fábrica, landing, Node opcional y cómo restaurar una copia).
- `semillas/canales.toml`: LinkedIn ahora lista 1200×627, el tamaño de vista de enlace que usan C22, C24 y C26. Una prueba nueva lo vigila para toda la campaña.

### Cómo se verificó

- `python -m unittest discover -s tests -t .` en verde con Chromium y FFmpeg (el número exacto, en la salida de la CI). Nuevas para la landing: el auditor revisa cada sección, una capacidad «no anunciar» o con matices no puede ir en «lo que ya hace», no se publica con pendientes, el borrador no lleva formulario ni nada de Internet, las casillas salen sin marcar, las reglas del formulario, el receptor local de punta a punta y la importación desde un receptor simulado (incluido que no borra nada si una fila falla).
- `node --test sitio/receptor/worker.test.mjs`: 7 pruebas con una D1 simulada sobre SQLite (sin consentimiento no guarda, sin duplicados ni IP en claro, trampa, límite por hora, clave para exportar y borrar, y las mismas reglas que Python). La CI las corre también.
- La página se revisó a ojo con Chromium en escritorio (1280 px) y en móvil (360 px, sin desplazamiento horizontal).
- El procedimiento para restaurar una copia de `INSTALACION.md` se probó sobre una base de prueba.

### Pendiente

- Lo tuyo para publicar la landing: completar los datos del responsable, inscribir el banco de datos «Interesados», comunicar el flujo transfronterizo, que un abogado revise el aviso y las casillas, y autorizar la cuenta de Cloudflare. Si Cloudflare pide tarjeta, se para ahí.
- Fase 4: rutina diaria con respaldo, lectura del radar y resumen semanal.
- Fase 6: leer el CSV que exporta cada red, y los experimentos.

### Defectos y límites conocidos

- No hay analítica en la página: `analitica_token` queda vacío hasta decidir una herramienta sin cookies.
- La landing usa iconos donde irían capturas reales de Cuadra (mismo motivo que en la Fase 3).
- `metrica importar` solo entiende una planilla propia (columnas `url`, `fecha` y nombres de métrica), no el CSV de cada red.
- No se verificó todavía si Cloudflare pide tarjeta para crear la cuenta o usar D1.

### Siguiente paso

Fase 4: un comando `rutina diaria` (respaldo, radar y lo pendiente del día) que puedas programar en Windows, y el resumen semanal.

---

## 14/10/2026 · Fase 3: fábrica de piezas, calendario de 30 días y paquete de lanzamiento

### Hecho

- **Fábrica** (`mos/fabrica/`, `plantillas/`): 10 plantillas (educativo, beneficio, noticia, carrusel, trivia, meme, lanzamiento, invitación a demo, promoción y vídeo animado) con la identidad provisional de Cuadra: Geist, iconos Lucide y logo incrustados, sin Internet. Exportan PNG en cinco formatos, PDF de carrusel para LinkedIn, trivia interactiva en HTML, vídeo MP4 con portada y, si hay locución, guion, teleprompter y subtítulos SRT. Los textos que no caben se achican hasta un 55 % y, si aun así no caben, avisan. Cada archivo queda registrado con su huella SHA-256. Previsualizaciones en `plantillas/<nombre>/previa/`. Guía en `docs/IDENTIDAD-VISUAL.md`.
- **Campañas como archivos** (`mos/campanas.py`, `python -m mos campana`): `cargar` (sin duplicar; versión nueva solo si el contenido cambió; auditoría en cada carga), `render` (la misma imagen o vídeo para varias redes se renderiza una vez), `calendario` (Markdown y CSV), `paquete` (una carpeta por publicación con sus archivos y el texto) y `mover` (corre todas las fechas por semanas).
- **Calendario de 30 días** (`campanas/lista-espera-beta/`): del 15/10 al 13/11/2026, 26 publicaciones en Facebook, Instagram, LinkedIn, TikTok y YouTube y 4 domingos de revisión. Cada día tiene producto, audiencia, objetivo, etapa, pilar, tema, formato, canal, gancho, copy o guion, llamado, fuente, archivos, verificación, aprobación y métrica.
- **Paquete de lanzamiento exportado** (`campanas/lista-espera-beta/exportados/`, 94 archivos): flyers comerciales y educativos, dos carruseles con PDF, trivia con versión interactiva, tres memes, un vídeo meme, dos vídeos con guion para tu voz y una noticia con fuente oficial verificada (R.S. N.° 000125-2026/SUNAT). Más `mensajes-y-demo.md` (respuestas a «BETA» y «DEMO» con la pregunta de consentimiento y preguntas frecuentes), `secuencia-seguimiento.md` y `concepto-video-meme.md`.
- Auditor: el nombre de la marca ya no se confunde con el verbo («algo no cuadra») ni con otras palabras («cuadrado»).

### Cómo se verificó

- `python -m unittest discover -s tests -t .`: todas en verde (ver el número en la salida de la CI). Nuevas: plantillas y exportación real (medidas exactas, PDF con sus páginas, vídeo con su duración, caché de render, registro de archivos) y campañas (herencia entre piezas, carga idempotente, piezas publicadas intocables, calendario, paquete, mover fechas). La campaña real tiene su propia prueba: 30 días seguidos sin repetir, cada pieza encaja en su plantilla y el auditor solo frena la noticia hasta que la revise un contador.
- Las 26 piezas se renderizaron con Chromium y FFmpeg y se revisaron a ojo en hojas de contacto; se corrigieron las portadas de vídeo (ahora se elige la escena) y la invitación de la trivia en historias.

### Pendiente

- Tu aprobación de cada pieza en el panel. Que un contador lea la noticia C12 y los contenidos educativos.
- Grabar tu voz para C13 y C18 y volver a renderizar con `--audio`.
- Capturas reales de Cuadra con la empresa de ejemplo para reemplazar iconos en C06, C15, C17 y los vídeos.
- Inscribir el banco de datos «Interesados» y publicar el aviso de privacidad antes de guardar datos de nadie.
- Landing de captación (Fase 5) y los documentos que faltan: ESTRATEGIA-MAESTRA, ESTRATEGIA-EDITORIAL, AUTOMATIZACIONES, CANALES-Y-PUBLICACION, METRICAS-Y-EXPERIMENTOS y OPERACION-DIARIA.

### Defectos y límites conocidos

- La identidad visual es provisional: las imágenes de referencia que mencionaste no llegaron.
- Las piezas usan iconos donde irían capturas reales del producto, porque Cuadra no se pudo ejecutar en este entorno (es de Windows).
- Renderizar todo el paquete tarda unos 6 minutos (los vídeos se graban cuadro a cuadro).
- Los vídeos salen sin música: en cada red se elige un sonido con licencia comercial o se publican sin música.
- `exportados/` es una foto del paquete: si cambias el TOML, vuelve a renderizar y a exportar.

### Siguiente paso

Landing local con la lista de espera y la trivia interactiva, sin publicar (Fase 5 adelantada), y los documentos de operación.

---

## 14/10/2026 · Fase 2: panel web local y registro de herramientas

### Hecho

- Panel web en `http://127.0.0.1:8765` con `python -m mos web` (`mos/web/`). Solo biblioteca estándar de Python. Pantallas: Hoy, Aprobaciones, Calendario mensual, Tareas de agentes (con el prompt preparado y un cuadro para pegar la respuesta de la IA), Ideas con puntuación explicable, Campañas, Biblioteca de piezas (versiones, auditor, decisiones, archivos y paquete de publicación), Publicaciones (confirmar con enlace, programada o fallida), Leads (contactos enmascarados, derechos de la persona, exportación), Métricas, Radar normativo, Productos con su matriz, Herramientas y Errores.
- Seguridad del panel: solo responde a `127.0.0.1` y `localhost` (evita el ataque de DNS rebinding), token por proceso en cada formulario, todo texto escapado, no sirve la base, ni CSV ni JSON con datos personales, ni archivos fuera de su carpeta.
- Radar con verificación humana (`mos/radar.py`): una novedad solo pasa a VERIFICADA con enlace a la fuente oficial.
- Contexto de producto compartido entre la línea de comandos y el panel (`mos/contexto.py`).
- Registro de herramientas y costes consolidado: 175 herramientas (63 adoptar, 34 probar, 58 reservar, 20 descartar; 51 requieren autorización) y 36 recursos con licencia (`docs/REGISTRO-HERRAMIENTAS-Y-COSTES.md`, `semillas/herramientas.toml`, `semillas/licencias.toml`). Higgsfield queda en RESERVAR con autorización obligatoria.

### Cómo se verificó

- `python -m unittest discover -s tests -t .`: 90 pruebas en verde. Las 12 nuevas del panel prueban el rechazo de otro host y de formularios sin token, que todas las pantallas se muestren, el escape de textos, el enmascarado de contactos, la supresión con confirmación, el bloqueo de una pieza con precio y el recorrido completo de una pieza con clics (crear, escribir, auditar, aprobar, preparar y confirmar la publicación).
- Panel levantado con datos sintéticos y revisado en capturas de Chromium.

### Pendiente

- Lo de la Fase 3 en adelante (ver la entrada anterior).
- 68 pendientes de verificación en el registro de herramientas; los cinco más importantes: inscribir el banco de datos de leads y validar el aviso con un abogado; confirmar si Cloudflare Workers, D1 o R2 piden tarjeta; confirmar el plan de Claude que paga Didi; conocer la RAM y la GPU de su PC; leer la licencia comercial de changedetection.io.

### Defectos y límites conocidos

- El panel no tiene usuarios ni contraseña: está pensado para una sola persona en su propia PC.
- El calendario no permite arrastrar piezas entre días; la fecha se cambia en la pieza.

### Siguiente paso

Fase 3: plantillas visuales y exportación a PNG, PDF y vídeo; calendario de 30 días y paquete de lanzamiento.

---

## 14/10/2026 · Fases 0 y 1: auditoría, investigación y núcleo

### Hecho

**Fase 0**
- Auditoría de Cuadra en solo lectura sobre `axel29-bm/contatony-2` (commit `0411f76`): `docs/AUDITORIA-CUADRA.md`. Etapa comercial: prelanzamiento. 44 capacidades con evidencia: 20 permitidas, 12 con matices, 3 solo en demostración y 9 que no se anuncian.
- Matriz legible por el sistema: `productos/cuadra/capacidades.toml` (con los patrones de frases que el auditor bloquea), `producto.toml` y `audiencias.toml` (hipótesis).
- Investigación con fuente y fecha en cuatro frentes: IA y automatización; producción creativa; publicación, leads y analítica; mercado, radar normativo y cumplimiento legal. Consolidada en `docs/REGISTRO-HERRAMIENTAS-Y-COSTES.md` y `semillas/herramientas.toml`.
- Informe con los ocho puntos pedidos: `docs/INFORME-FASE-0.md`.

**Fase 1**
- Base SQLite local con 29 tablas `STRICT`, WAL, migraciones con `PRAGMA user_version`, respaldo verificado y registro de errores y auditoría (`mos/db.py`, `mos/migraciones/0001_inicial.sql`).
- Configuración versionada en TOML y carga idempotente (`mos/semillas.py`): marcas, productos, capacidades, audiencias, 23 fuentes del radar, herramientas y licencias.
- Auditor de calidad, marca y cumplimiento (`mos/calidad/auditor.py`).
- 11 agentes con contrato, prompts y criterios de éxito; motor de tareas con idempotencia, límites de profundidad, intentos y plazo; proveedores de IA asistido, local y externo con autorización, tope diario y bloqueo de datos personales (`mos/agentes/`, `prompts/`).
- Flujo de contenido: ideas con puntuación explicable, campañas, piezas con versiones, auditoría, aprobación ligada al hash de la versión, paquetes de publicación y confirmación solo con URL o id externo (`mos/contenido.py`).
- Leads con deduplicación, consentimiento probado y separado para publicidad, baja con lista de supresión, acceso y supresión (`mos/leads.py`).
- Métricas medidas y estimadas por separado, recomendaciones explicables y piezas reciclables (`mos/metricas.py`).
- Límites y formatos por canal (`semillas/canales.toml`).
- Línea de comandos completa (`python -m mos --help`).
- Documentación: README, CLAUDE.md, ARQUITECTURA-AGENTES, EMBUDOS-Y-LEADS, SEGURIDAD-Y-PRIVACIDAD, CALIDAD-Y-CUMPLIMIENTO, INSTALACION, ROADMAP.

### Cómo se verificó

- `python -m unittest discover -s tests -t .`: 78 pruebas en verde (base, semillas, auditor, agentes, proveedores, contenido, leads, métricas y línea de comandos de punta a punta).
- `python -m mos iniciar` y `estado` sobre una base nueva.

### Pendiente

- Panel web local (Fase 2).
- Fábrica de plantillas, calendario de 30 días y paquete de lanzamiento con archivos exportados (Fase 3).
- Radar automático, respaldos programados y resumen semanal (Fase 4).
- Landing con formulario (Fase 5).
- Documentos que faltan: ESTRATEGIA-MAESTRA, IDENTIDAD-VISUAL, ESTRATEGIA-EDITORIAL, AUTOMATIZACIONES, CANALES-Y-PUBLICACION, METRICAS-Y-EXPERIMENTOS, OPERACION-DIARIA.

### Defectos y límites conocidos

- No se ejecutó Cuadra (es de Windows y el entorno de construcción es Linux): las capturas reales las hace Didi.
- Los máximos de texto por canal de `semillas/canales.toml` están marcados como no verificados en la ayuda oficial (las páginas no cargaron). Son conservadores.
- El sitemap de noticias de El Peruano y las páginas de gob.pe quedan por confirmar antes de automatizar el radar.
- El modo externo de IA se probó solo con pruebas simuladas (no se llamó a ningún proveedor real, por diseño).

### Decisiones nuevas

- Orquestador propio en Python en lugar de n8n o Activepieces (licencia y peso).
- Publicación por herramientas nativas de cada red; el sistema prepara paquetes y registra la prueba.
- Identidad provisional: blanco, azul noche, acento azul y verde lima de realce, con Geist (OFL), mientras llegan las imágenes de referencia.

### Siguiente paso

Fase 2: panel web local servido en `http://127.0.0.1:8765` sin dependencias externas.
