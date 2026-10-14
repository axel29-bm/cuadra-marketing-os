# Seguridad y privacidad

## 1. Qué datos maneja el sistema

| Dato | Dónde vive | Sensibilidad | Sale de la PC |
| --- | --- | --- | --- |
| Configuración de productos, matrices, marcas, fuentes, herramientas | Repositorio git | Baja (no tiene datos personales) | Sí, en GitHub (repositorio privado) |
| Piezas, versiones, aprobaciones, publicaciones, métricas, tareas | `espacio/mos.db` | Media (estrategia comercial) | No |
| Leads (correo, teléfono, nombre) | `espacio/mos.db`, tabla `lead` | **Alta (datos personales)** | No, salvo autorización expresa |
| Prompts preparados | `espacio/tareas/` | Media | Solo si Didi los pega en una IA; el sistema nunca pone datos personales en ellos |
| Archivos exportados | `espacio/salidas/` | Variable | Los sube Didi |
| Respaldos | `espacio/respaldos/` | Alta (contienen leads) | Solo cifrados (ver sección 4) |
| Claves de servicios | Variables de entorno | **Crítica** | Nunca en archivos del repositorio |

`espacio/` está en `.gitignore`: nada de esa carpeta llega a git.

## 2. Reglas

1. **Ningún secreto en el código ni en git.** Las claves solo se leen de variables de entorno (`MOS_IA_CLAVE`). El sistema nunca pide claves por chat y nunca las escribe en un registro.
2. **Ningún dato personal en la IA.** El proveedor de IA rechaza cualquier prompt con un correo o un teléfono. Los agentes trabajan con métricas y textos, no con leads.
3. **Ningún dato real de clientes de Cuadra.** Las capturas y los vídeos usan la empresa de ejemplo (datos inventados, RUC 2099…). El auditor bloquea RUC, DNI, correos y celulares que no sean de la marca.
4. **Ninguna credencial SOL ni información tributaria de clientes** entra a este sistema, nunca.
5. **El modo de IA externo está apagado** hasta que Didi lo autorice, y se puede revocar: `python -m mos autorizar IA_EXTERNA --revocar`.
6. **La base viva no va en una carpeta sincronizada** (OneDrive, Google Drive, Dropbox): la sincronización puede corromper SQLite. Los respaldos sí pueden ir a la nube, cifrados.

## 3. Proveedores de IA y lo que hacen con los datos

| Proveedor | Qué hace con lo que envías | Uso permitido aquí |
| --- | --- | --- |
| Ollama con modelos abiertos (local) | Nada sale de la PC | Todo, excepto leads |
| Gemini, plan gratuito | Google puede usarlo para mejorar sus productos, con revisión humana | Solo contenido público (borradores de posts, ideas). Nunca leads ni estrategia sensible |
| Cloudflare Workers AI, plan gratuito | Según su documentación, no entrena con los datos | Contenido público, como respaldo |
| OpenRouter, modelos gratuitos | Algunos proveedores pueden entrenar con los datos | Solo contenido público, y solo con autorización |
| Higgsfield | Sus términos permiten entrenar con lo que subes y generas | Ninguno sin autorización expresa de Didi (además consume sus créditos) |

Detalle y fuentes en `docs/REGISTRO-HERRAMIENTAS-Y-COSTES.md`.

## 4. Copias de seguridad

- `python -m mos respaldar` hace una copia consistente con la API de respaldo de SQLite, la verifica con `integrity_check` y conserva las últimas 14.
- Recomendado (Fase 4): programarlo una vez al día con el Programador de tareas de Windows y enviar la carpeta de respaldos, **cifrada**, a la nube personal de Didi con restic y rclone. Un respaldo sin cifrar con leads no se sube a ningún servicio.
- Probar la restauración una vez al mes: abrir la copia con `python -m mos --espacio <carpeta de prueba> estado`.

## 5. Incidentes (procedimiento de 48 horas)

Si se pierde, se roba o se expone la base, un respaldo o un archivo con leads:

1. **Contener.** Cambiar las claves afectadas, revocar autorizaciones (`python -m mos autorizar <categoria> --revocar`), retirar el archivo expuesto.
2. **Evaluar.** Qué datos, de cuántas personas, desde cuándo.
3. **Notificar en un máximo de 48 horas** a la Autoridad Nacional de Protección de Datos Personales y avisar a las personas afectadas (reglamento de la Ley 29733, art. 34). En entornos digitales, también al Centro Nacional de Seguridad Digital. **Validar el procedimiento con abogado.**
4. **Registrar** qué pasó y qué se cambió, en `docs/PROGRESO.md`.

## 6. Derechos de las personas

Comandos listos (ver `docs/EMBUDOS-Y-LEADS.md`):

- Acceso: `python -m mos lead acceso --contacto correo@ejemplo.pe`
- Baja de publicidad: `python -m mos lead baja --contacto …`
- Supresión: `python -m mos lead suprimir --contacto …`

Plazos legales (días hábiles): información 8, acceso 20, rectificación, cancelación y oposición 10.

## 7. Registro y auditoría

- Toda acción relevante queda en la tabla `auditoria` (quién, qué, cuándo). Los registros de leads guardan el identificador opaco, no el contacto.
- Los errores quedan en `registro_error` y se consultan con `python -m mos errores`.
- Ningún registro guarda claves ni el contenido de los prompts con datos personales.
