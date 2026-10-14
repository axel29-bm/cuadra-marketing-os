# Automatizaciones

Cada flujo tiene una razón, un criterio para ejecutarse y una forma de comprobar que funcionó. Si no tiene las tres, no se automatiza. Ninguno publica, envía mensajes ni gasta dinero por su cuenta.

## Reglas comunes

- **Corren en tu PC.** Nada depende de un servidor que haya que pagar ni de una clave de IA de pago.
- **La IA trabaja en modo asistido por defecto:** el sistema prepara el encargo y tú lo pasas por la IA que ya usas. El modo local (Ollama) es opcional; el externo está apagado y solo se enciende con `python -m mos autorizar IA_EXTERNA` (ver `ARQUITECTURA-AGENTES.md`).
- **Un fallo deja rastro.** Los errores de la consola, del panel y de las publicaciones van a la tabla de errores y aparece en la página «Hoy» del panel hasta que se resuelve.
- **Sin atajos.** Nada de raspar sitios que lo prohíben, saltarse CAPTCHA o automatizar el navegador para publicar.
- **Programar en Windows** se hace con el Programador de tareas, que viene con el sistema. El sistema no se instala solo como tarea: tú creas cada una con el comando que se indica, y la borras igual de fácil.

## Los flujos

| Flujo | Razón | Se ejecuta cuando | Cómo se comprueba | Estado |
| --- | --- | --- | --- | --- |
| Auditoría de cada pieza | Que nada prometa lo que Cuadra no hace | Cada vez que se crea o cambia una pieza (`campana cargar`, panel) | La pieza muestra su informe; sin informe no se puede aprobar | **Funciona** |
| Producción de archivos | No diseñar a mano cada formato | `campana render`, o el botón «Generar imágenes y vídeo» de la ficha de la pieza en el panel | Cada archivo queda registrado con su huella SHA-256; si el texto no cambió, no se vuelve a generar | **Funciona** |
| Calendario y paquete | Saber qué sale cada día y tener todo junto para subir | `campana calendario` y `campana paquete` | `CALENDARIO.md`, `calendario.csv` y una carpeta por pieza con su texto | **Funciona** |
| Recordatorios de seguimiento | Que ningún interesado quede sin respuesta | Al abrir el panel o con `lead seguimientos` | La cifra «Seguimientos de leads» en «Hoy» baja al registrar el contacto | **Funciona** (sin aviso fuera del panel) |
| Alertas | Ver a tiempo errores, publicaciones atrasadas, tareas detenidas y rutinas que dejaron de correr | Al abrir el panel y en el informe de la rutina diaria | Página «Hoy» (avisa si la rutina diaria no corre hace más de 2 días, la semanal hace más de 8 o la mensual hace más de 38) | **Funciona** |
| Encargos a los agentes | Que cada agente reciba el contexto correcto y su resultado se revise | `tarea preparar` y `tarea completar` | Cada resultado pasa los criterios de su contrato antes de llegar a ti | **Funciona** en modo asistido |
| Rutina diaria | Empezar el día sabiendo qué toca, con la base respaldada | `rutina diaria`, a mano o programada | Informe en `espacio\salidas\rutinas\diaria-AAAA-MM-DD.md` y una fila en la tabla `rutina`; si un paso falla, los demás siguen y el fallo queda en «Errores» | **Funciona** |
| Copia de seguridad | No perder la base | Dentro de la rutina diaria, o a mano con `respaldar` | La copia pasa `integrity_check` antes de guardarse; se conservan 14 | **Funciona** |
| Radar de fuentes oficiales | Enterarse de cambios de SUNAT, El Peruano y el MEF a tiempo | Dentro de la rutina diaria o con `radar leer`; cada fuente según su frecuencia (12 h a 7 días) | Cada novedad entra «sin verificar»; solo un enlace oficial la verifica, y una pieza normativa necesita además la revisión de un contador. `radar fuentes` muestra la última lectura y el último error de cada una | **Funciona** con servidores simulados; la primera lectura real se hace en tu PC |
| Resumen semanal del director | Una página con lo que pasó y lo que toca | `rutina semanal`, a mano o programada los domingos | Informe en `espacio\salidas\rutinas\semanal-AAAA-MM-DD.md`: publicaciones con prueba, métricas medidas separadas de las estimadas, interesados, aprobaciones, radar, salud de las rutinas y la semana siguiente | **Funciona** |
| Plan de la semana | Proponer el calendario según metas, recursos y resultados | Después del resumen semanal | Una propuesta que pasa por el auditor y espera tu aprobación | **Parcial:** el resumen lista la semana siguiente y lo que falta aprobar; la propuesta de piezas nuevas la hace el estratega en modo asistido (`tarea crear --agente estratega`) |
| Medición | Saber qué funcionó | Cada domingo, al importar el CSV de cada red (`metrica importar`, primero con `--revisar`) | El comando dice cuántas filas enlazó, qué columnas no entendió y qué filas no coinciden con una publicación confirmada; `metrica resumen` separa lo medido de lo estimado | **Funciona.** Los nombres de las columnas de cada red quedan por verificar con su primer archivo real (`semillas/metricas-csv.toml`) |
| Experimentos | Decidir con datos y no por impresión | `experimento resultado`, la pantalla Métricas y la revisión mensual | Cada resultado usa solo métricas medidas, dice cuántas publicaciones entran por grupo y se marca como indicio con menos de 30; la decisión la anotas tú con `experimento cerrar` | **Funciona** |
| Revisión mensual y reutilización | Rehacer lo que funcionó y revisar costes antes de que sorprendan | `rutina mensual`, a mano o programada el día 1 | Informe en `espacio\salidas\rutinas\mensual-AAAA-MM-DD.md`: métricas e interesados del mes, experimentos, piezas para reutilizar (con interesados o guardados medidos y más de 60 días) y herramientas gratuitas verificadas hace más de 90 días | **Funciona.** La nueva versión de cada pieza la haces tú o el copywriter en modo asistido, y pasa otra vez por el auditor |
| Publicación | Ahorrar el paso de subir archivos | Solo con la autorización `PUBLICACION_API` y una prueba real en tu cuenta | La red devuelve la URL o el id; sin eso no cuenta como publicada | **Apagado** (ver `CANALES-Y-PUBLICACION.md`) |

## Cómo programar las rutinas

```powershell
python -m mos rutina diaria          # a mano: respaldo, radar y lo pendiente del día
python -m mos rutina semanal         # a mano: el resumen de los últimos 7 días
python -m mos rutina mensual         # a mano: la revisión del mes anterior (--mes AAAA-MM para otro)
python -m mos rutina programar       # escribe un .cmd por rutina en espacio\ y te muestra los comandos
python -m mos rutina estado          # cuándo corrió cada una por última vez
```

`rutina programar` **no crea** las tareas: te muestra los comandos de `schtasks` (el Programador de tareas de Windows) para que los copies si quieres. La diaria queda a las 08:00, la semanal los domingos a las 18:00 y la mensual el día 1 a las 09:00; puedes cambiar la hora en el comando. Para quitarlas, el mismo comando te da las líneas de `schtasks /Delete`. La PC tiene que estar encendida a esa hora; si no lo está, corre en la siguiente.

**El radar, con cortesía.** Solo lee fuentes `SITEMAP` o `HTML` activas de `semillas/fuentes.toml`; las `MANUAL` nunca se descargan. Antes de cada sitio lee su `robots.txt` y no entra donde no le dejan (la fuente queda «bloqueada» y se revisa a mano). Se identifica como `CuadraMarketingOS/0.1`, espera al menos 5 segundos entre peticiones al mismo sitio, solo usa https y descarga como mucho 10 MB por archivo. La primera lectura de una página guarda lo que hay como punto de partida y no crea novedades; desde la segunda, solo entra lo nuevo que pase el `filtro` de palabras de la fuente, hasta 25 por pasada. En las fuentes sin filtro, si la página cambia sin enlaces nuevos (el valor de la UIT, un cronograma), se anota «Cambió la página» para que la mires.

## Lo que no se automatiza

- Publicar, comentar o enviar mensajes en tu nombre.
- Captar datos de personas fuera del formulario con consentimiento.
- Comprar, activar pruebas de pago o consumir créditos (incluido Higgsfield).
- Decidir sobre contenido tributario sin un contador.
