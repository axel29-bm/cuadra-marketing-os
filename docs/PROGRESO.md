# Progreso

Bitácora del Marketing OS. Lo más reciente arriba. Cada entrada dice qué se hizo, cómo se verificó, qué falta, los defectos conocidos y el siguiente paso.

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
