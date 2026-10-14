# CLAUDE.md · Cuadra Marketing OS

Sistema de marketing local-first de Didi, en Python. Empieza con Cuadra (software contable para contadores peruanos) y debe servir para futuros productos y marcas. Explica en español, corto y claro.

## Antes de tocar nada

- Lee `docs/PROGRESO.md` (qué está hecho y qué sigue) y `docs/ARQUITECTURA-AGENTES.md`.
- La verdad sobre lo que un producto puede afirmar está en `productos/<slug>/capacidades.toml`. Si cambia el producto, se actualiza ahí con evidencia y fecha, y después `docs/AUDITORIA-<PRODUCTO>.md`.
- El repositorio de Cuadra (`axel29-bm/contatony-2`) es **solo fuente de información**. Nunca se modifica desde aquí.

## Reglas

1. **Nada se inventa:** clientes, testimonios, cifras, precios, certificaciones, integraciones ni resultados. Lo no verificable queda como PENDIENTE.
2. **El auditor no se salta.** No se debilita una regla de `mos/calidad/auditor.py` ni de la matriz para que una pieza pase. Si una regla está mal, se corrige con una prueba que lo demuestre.
3. **Sin gasto ni acciones externas sin autorización de Didi:** compras, pruebas de pago, créditos (incluido Higgsfield), publicación, envío de correos o mensajes, despliegues públicos. Se prepara todo y se pide la autorización.
4. **Sin secretos en el repositorio.** Las claves solo se leen de variables de entorno (`MOS_IA_CLAVE`). Nunca se piden a Didi por chat.
5. **Sin datos personales reales** en código, pruebas, ejemplos, prompts, capturas ni registros. Ejemplos con la empresa de ejemplo (RUC 2099…).
6. **Licencias:** solo herramientas y recursos con uso comercial permitido, registrados en `semillas/herramientas.toml` y `semillas/licencias.toml`.
7. **Esquema de la base:** tablas `STRICT`, migraciones numeradas en `mos/migraciones/`. Una migración publicada no se edita: se agrega otra.

## Modo asistido (cuando Didi te pida resolver tareas de agentes)

1. `python -m mos tarea listar` y `python -m mos tarea preparar T-XXXX`.
2. Lee `espacio/tareas/T-XXXX/PROMPT.md` y respóndelo **siguiendo su formato de salida al pie de la letra**.
3. Guarda solo el JSON en `espacio/tareas/T-XXXX/resultado.json` y ejecuta `python -m mos tarea completar T-XXXX`.
4. Si el sistema lo rechaza, corrige según los problemas que lista. No edites la base a mano para forzar un estado.

## Comandos

```bash
python -m mos iniciar                       # crea o actualiza la base y carga la configuración
python -m unittest discover -s tests -t .   # todas las pruebas; deben pasar antes de decir «listo»
python -m mos --help
```

## Al terminar una fase

Resume lo hecho, lista los archivos, corre las pruebas, actualiza `docs/PROGRESO.md` (hecho, pendiente, defectos conocidos, siguiente paso) y la documentación afectada.
