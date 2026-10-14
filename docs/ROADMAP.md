# Hoja de ruta

Las fases siguen la sección 18 del encargo. Cada fase termina con pruebas en verde, `docs/PROGRESO.md` actualizado y una lista de defectos conocidos.

| Fase | Objetivo | Estado |
| --- | --- | --- |
| 0 | Auditoría de Cuadra, investigación de herramientas y arquitectura | ✓ Hecha (14/10/2026) |
| 1 | Núcleo: base local, matriz de capacidades, auditor, 11 agentes con contrato, motor de tareas, leads, métricas, línea de comandos | ✓ Hecha (14/10/2026) |
| 2 | Panel web local: productos, campañas, ideas, calendario, biblioteca, aprobaciones, publicaciones, leads, tareas y errores | En curso |
| 3 | Fábrica: plantillas visuales (promoción, beneficio, educativo, noticia, carrusel, trivia, meme, lanzamiento, demostración), exportación a PNG, PDF y MP4, teleprompter y paquete de voz, calendario de 30 días y paquete de lanzamiento | Siguiente |
| 4 | Automatizaciones locales: radar diario de fuentes oficiales, respaldos programados, resumen semanal del director, recordatorios de seguimiento de leads | Pendiente |
| 5 | Landing con lista de espera y formulario con consentimiento (local; publicarla requiere autorización y dominio o subdominio gratuito) | Pendiente |
| 6 | Medición y mejora: importación de métricas desde los CSV de cada red, experimentos, reciclaje de piezas, revisión mensual | Pendiente |

## Decisiones que esperan a Didi

| Decisión | Por qué importa | Mientras tanto |
| --- | --- | --- |
| Subir las imágenes de referencia | Ajustar la identidad visual | Identidad provisional basada en el diseño de Cuadra |
| Buscar «Cuadra» en el buscador de marcas de INDECOPI | Evitar invertir en un nombre ocupado | Todo usa el nombre como provisional |
| Dominio propio (S/ 110 al año un .pe; unos USD 10 un .com) | Correo con dominio y landing propia | Subdominio gratuito de Cloudflare Pages |
| Un contador que revise contenido normativo | Publicar noticias tributarias | Las noticias quedan bloqueadas por el auditor |
| Inscribir el banco de datos de interesados ante la autoridad de datos personales | Requisito legal antes de captar | El formulario no se publica |
| Revisión legal del aviso de privacidad | Requisito legal antes de captar | Borrador listo, sin publicar |
| Autorizar Higgsfield, la IA externa o la publicación por API | Consumen créditos o actúan en nombre de Didi | Todo apagado |

## Cuando Cuadra cambie de etapa

- **Beta privada:** actualizar `etapa_comercial` en `productos/cuadra/producto.toml`, revisar la matriz y cambiar los llamados a la acción.
- **Preventa o venta:** solo cuando existan precio aprobado, instalador firmado, términos y política de privacidad revisados y servicio de licencias. Entonces el auditor deja pasar las piezas promocionales.
- **Nuevos productos:** una carpeta nueva en `productos/` con su `producto.toml`, `capacidades.toml` y `audiencias.toml`, y una marca en `marcas/`. El resto del sistema no cambia.
