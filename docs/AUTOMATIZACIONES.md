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
| Alertas | Ver a tiempo errores, publicaciones atrasadas y tareas detenidas | Al abrir el panel | Página «Hoy» y página «Errores» | **Funciona** dentro del panel |
| Encargos a los agentes | Que cada agente reciba el contexto correcto y su resultado se revise | `tarea preparar` y `tarea completar` | Cada resultado pasa los criterios de su contrato antes de llegar a ti | **Funciona** en modo asistido |
| Copia de seguridad | No perder la base | Hoy, a mano con `respaldar` | La copia pasa `integrity_check` antes de guardarse; se conservan 14 | **Funciona a mano.** Programada: Fase 4 |
| Radar de fuentes oficiales | Enterarse de cambios de SUNAT, El Peruano y el MEF antes que la competencia | Fase 4: una vez al día, solo fuentes de `semillas/fuentes.toml` que lo permiten | Cada novedad entra «sin verificar»; solo un enlace oficial la verifica, y una pieza normativa necesita además la revisión de un contador | **Parcial:** registro y verificación manuales. Lectura diaria: Fase 4 |
| Resumen semanal del director | Una página con lo que pasó y lo que toca | Fase 4: los domingos | Archivo en `espacio\salidas\resumen-AAAA-MM-DD.md` con cifras medidas separadas de las estimadas | **Fase 4** |
| Plan de la semana | Proponer el calendario según metas, recursos y resultados | Fase 4, después del resumen | Una propuesta que pasa por el auditor y espera tu aprobación | **Fase 4** |
| Medición | Saber qué funcionó | Al registrar métricas | `metrica resumen` separa lo medido de lo estimado | **Parcial:** registro manual y planilla propia. CSV de cada red: Fase 6 |
| Reutilización | Rehacer lo que funcionó | Fase 6, en la revisión mensual | Propuestas de nuevas versiones de las piezas con mejores métricas medidas | **Fase 6** |
| Publicación | Ahorrar el paso de subir archivos | Solo con la autorización `PUBLICACION_API` y una prueba real en tu cuenta | La red devuelve la URL o el id; sin eso no cuenta como publicada | **Apagado** (ver `CANALES-Y-PUBLICACION.md`) |

## Fase 4: cómo quedará

1. **Un solo comando para el día:** `python -m mos rutina diaria` hará la copia de seguridad, leerá el radar y dejará el informe de lo pendiente. Podrás correrlo a mano o programarlo.
2. **Programarlo** (cuando lo pidas):
   ```powershell
   schtasks /Create /TN "Marketing OS diario" /SC DAILY /ST 08:00 /TR "cmd /c cd /d C:\MarketingOS\cuadra-marketing-os && python -m mos rutina diaria"
   schtasks /Delete /TN "Marketing OS diario" /F      # para quitarlo
   ```
3. **Radar:** solo leerá fuentes cuyo acceso automático esté permitido, con una petición al día por fuente, identificándose y respetando `robots.txt`. Las que no lo permitan quedan como enlaces para revisar a mano.
4. **Resumen semanal:** sin IA externa. Lo arma el sistema con los datos de la base; el texto final lo puedes pulir en modo asistido.

## Lo que no se automatiza

- Publicar, comentar o enviar mensajes en tu nombre.
- Captar datos de personas fuera del formulario con consentimiento.
- Comprar, activar pruebas de pago o consumir créditos (incluido Higgsfield).
- Decidir sobre contenido tributario sin un contador.
