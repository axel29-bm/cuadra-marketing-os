# Canales y publicación

Cómo sale una pieza del sistema hacia una red, quién aprieta el botón y cómo se demuestra que salió. La investigación de cada red, con fuentes y fechas, está en `REGISTRO-HERRAMIENTAS-Y-COSTES.md` (matriz de publicación por red). Este documento es la regla de trabajo.

## Lo que no cambia

- **Nada público sale sin tu aprobación explícita.** El sistema prepara; tú apruebas y publicas.
- **El sistema nunca dice «publicada» sin prueba.** La base de datos rechaza ese estado si no tiene la URL pública o el identificador que devolvió la red (`CHECK` en la tabla `publicacion`).
- **Un fallo no se pierde.** Una publicación `FALLIDA` exige el texto del error; queda en el panel hasta que se resuelve y cuenta sus reintentos.
- **Sin atajos.** Nada de automatizar el navegador para publicar, ni saltarse revisiones de apps, CAPTCHA o límites de las redes.
- **Lo sensible nunca sale solo:** contenido tributario, promociones y cualquier capacidad que no esté implementada y verificada. El auditor lo frena antes de la aprobación.

## Niveles de automatización

| Nivel | Qué hace | Estado hoy |
| --- | --- | --- |
| 1. Preparación automática | Archivos en los tamaños de cada red, texto, fecha recomendada y paquete listo | **Funciona.** `campana render` y `campana paquete` |
| 2. Revisión y programación | El auditor revisa, tú apruebas en el panel y programas con la herramienta nativa de cada red | **Funciona.** La programación la haces tú en la red; el sistema registra que quedó programada |
| 3. Publicación automática autorizada | Publicar por la API oficial de una red | **Apagado.** Necesita la autorización `PUBLICACION_API`, revocable con `python -m mos autorizar`, y una prueba real en tu cuenta antes |
| 4. Optimización | Leer métricas, comparar y proponer cambios | **Funciona en local.** Métricas a mano o desde el CSV que exporta cada red (`metrica importar`), experimentos calculados con lo medido y revisión mensual con piezas para reutilizar. Proponer es automático; decidir y cambiar una pieza siguen siendo tuyos |

Cuando un flujo de nivel 2 lleve semanas sin errores, se puede proponer el nivel 3 para una categoría concreta (por ejemplo, «trivias en Instagram»). La propuesta dirá qué se publica solo, qué no, cómo se revoca y qué prueba se hizo.

## Canales

Formatos y límites de texto en `semillas/canales.toml`; el auditor los usa. Los límites de texto quedan **por verificar** en la ayuda oficial de cada red (no cargó durante la investigación): mientras tanto son conservadores.

| Canal | Cómo se programa (gratis) | Tamaños que exporta la fábrica | Notas |
| --- | --- | --- | --- |
| Facebook (Página) | Meta Business Suite | 1080×1350, 1080×1080, 1080×1920 | Publicar por API exigiría la revisión de la app de Meta |
| Instagram (profesional) | Meta Business Suite | 1080×1350, 1080×1080, 1080×1920 | Carrusel de hasta 10 láminas |
| LinkedIn (tu perfil) | Programación nativa de LinkedIn | 1080×1350, 1200×1200, 1920×1080, 1200×627 | La Página de empresa por API exige una organización legal |
| TikTok | TikTok Studio (web) | 1080×1920 | Su API no sirve para publicar en cuenta propia sin auditoría |
| YouTube | YouTube Studio | 1920×1080, 1080×1920 | Shorts en vertical |
| WhatsApp Business (app) | Manual | 1080×1920, 1080×1080 | Estados y respuestas a quien te escribió primero. Nunca mensajes en frío |
| Landing | Despliegue con tu autorización | web | Ver «La landing» más abajo |
| Correo | Manual o servicio con dominio propio | html | Solo a quien dio su consentimiento para publicidad; asunto con «PUBLICIDAD» |

Una prueba (`tests/test_campanas.py`) comprueba que cada pieza de la campaña de lanzamiento se exporta en un tamaño que su red acepta.

## El recorrido de una pieza

```
borrador ─▶ auditor ─▶ lista para tu aprobación ─▶ aprobada ─▶ paquete listo ─▶ programada ─▶ publicada (con URL)
                │                                                      │
                └─▶ correcciones (frenada)                             └─▶ fallida (con error) ─▶ reintento
```

1. **Auditor.** Cada vez que la pieza cambia, se vuelve a auditar. Si la frena, el panel dice por qué y la aprobación queda bloqueada.
2. **Aprobación.** En el panel (`python -m mos web`, sección Aprobaciones) o con `python -m mos pieza aprobar <código>`. La aprobación vale para esa versión: si el texto cambia, hay que aprobar de nuevo.
3. **Paquete.** `python -m mos campana paquete campanas/<campaña>` deja en `exportados/` las imágenes, vídeos y el texto de cada pieza. El `texto.md` de cada carpeta dice su estado: sube solo las que digan «aprobada». Para una pieza suelta: `python -m mos publicacion preparar --pieza <código>`.
4. **Programar.** Subes los archivos a Meta Business Suite, TikTok Studio, YouTube Studio o LinkedIn y eliges la fecha. Luego: `python -m mos publicacion programar <id> --fecha AAAA-MM-DD`.
5. **Confirmar.** Cuando la red la muestra en público, copias el enlace: `python -m mos publicacion confirmar <id> --url https://…`. Sin enlace, sigue «programada».
6. **Si falló.** `python -m mos publicacion fallo <id> --error "lo que dijo la red"`. Queda visible en el panel hasta que la vuelvas a programar.

## La landing

La página de la lista de espera se construye en local (`python -m mos sitio construir`) y se ve en `python -m mos sitio ver`. Mientras falte algo legal, sale como borrador: con una franja que lo dice, sin formulario y con `noindex` para los buscadores.

Para publicarla:

1. `python -m mos sitio pendientes` tiene que salir vacío: datos del responsable, banco de datos inscrito, flujo transfronterizo comunicado, aviso revisado por un abogado y dirección del receptor.
2. Tu autorización explícita para crear la cuenta de Cloudflare y desplegar. Si Cloudflare pide tarjeta, se para ahí.
3. Los pasos de `sitio/receptor/LEEME.md`.

## Lo que el sistema no hace

- No publica en ninguna red por su cuenta (nivel 3 apagado).
- No envía mensajes ni correos: los deja redactados para que tú los envíes.
- No compra anuncios ni gestiona pauta pagada.
- No responde comentarios: el community manager prepara respuestas y tú las publicas.
