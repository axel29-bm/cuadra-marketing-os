Estado: versión 1, 14/10/2026. Se revisa en la revisión semanal de los domingos.

# Métricas y experimentos · Cuadra

Cómo sabemos si el marketing de Cuadra funciona, sin inventar datos y sin vigilar a nadie. Código: `mos/metricas.py`; tablas `metrica`, `lead` y `experimento` en `mos/migraciones/0001_inicial.sql`. La rutina general del domingo (copia de seguridad, radar, errores) está en `OPERACION-DIARIA.md`; aquí va lo que toca a la medición.

## 1. Principios

1. **Ningún dato se inventa.** Si no hay dato, el resumen dice «sin datos» y así se informa.
2. **Lo medido y lo estimado nunca se suman.** Cada métrica es `MEDIDA` o `ESTIMADA`; el panel las muestra en bloques separados («Estimado (no es dato real)»).
3. **Las recomendaciones del sistema usan solo lo medido.**
4. **No se atribuyen ventas.** En prelanzamiento no hay ventas que atribuir.
5. **Se cuentan cosas, no se sigue a personas.** Las métricas son conteos; los datos personales viven solo en la tabla `lead`, con consentimiento.

## 2. Métrica norte

**Contadores en la lista de espera con consentimiento registrado** (`metrica_exito` de la campaña). Meta inicial: 30 al 13/11/2026; se revisa el 25/10/2026 (`LEEME.md` de la campaña).

Un lead (un interesado registrado en la tabla `lead`) cuenta si es de Cuadra, entró por la campaña `lista-espera-beta`, tiene `consentimiento = 1` y no pidió la baja ni la supresión.

Tres cosas que hay que saber:

- **Empieza en cero por diseño.** Nadie entra a la lista antes de inscribir el banco de datos «Interesados» y tener el aviso de privacidad. Hasta entonces se cuentan las conversaciones (sección 3), sin guardar datos de nadie.
- **La da el sistema.** `python -m mos lead embudo --campana lista-espera-beta` termina con la línea «En la lista con consentimiento», y el resumen de `python -m mos rutina semanal` trae una tabla por campaña activa con su meta. Cuenta solo a quien dio su consentimiento, sin baja, sin supresión y sin la marca «no contactar»; el resto de `lead embudo` cuenta por estado e incluye a quienes no dieron consentimiento.
- **El lead debe registrarse con la campaña y la finalidad**, como en `mensajes-y-demo.md`; sin `--campana` no se asocia a la campaña y sin `--finalidad` el sistema rechaza el consentimiento:

```powershell
python -m mos lead registrar --producto cuadra --fuente "instagram-dm" --campana lista-espera-beta --nombre "[nombre]" --telefono "[número]" --consentimiento --finalidad "lista de espera de la beta privada" --version-aviso "[versión del aviso]" --medio "mensaje directo"
```

Cada domingo se registra el acumulado como métrica de campaña:

```powershell
python -m mos metrica registrar --nombre leads --valor [número] --campana lista-espera-beta --fecha 2026-10-18 --nota "Leads con consentimiento, acumulado"
```

## 3. Métricas por etapa del embudo

Solo valen los nombres que acepta el sistema (`NOMBRES` en `mos/metricas.py`).

| Etapa | Pregunta | Métricas del sistema | De dónde sale |
| --- | --- | --- | --- |
| Atención | ¿Nos vio? | `impresiones`, `alcance`, `visualizaciones`, `retencion_promedio_ms` | Estadísticas de cada red |
| Interés | ¿Le sirvió? | `reacciones`, `comentarios`, `compartidos`, `guardados`, `clics` | Estadísticas de cada red |
| Consideración | ¿Quiso hablar? | `conversaciones` (mensajes con «BETA» o «DEMO»), `visitas` y `formularios` de la landing | Bandeja de mensajes; analítica sin cookies de la landing |
| Conversión | ¿Entró a la lista? | `leads` con consentimiento, `solicitudes_demo`, `demos_realizadas` | Tabla `lead` y agenda de Didi |
| Beta | ¿Está listo para probar? | Leads en `CUALIFICADO`, `DEMO_HECHA` y `BETA` | `python -m mos lead embudo --producto cuadra` |

- **No aplican hoy:** `ventas` e `ingresos_c` (no hay venta; no se registran). `gasto_c` queda en 0 salvo un gasto autorizado.
- **Operación y calidad**, para cuidar a un equipo de una persona: `horas_produccion_min` (minutos por pieza), `correcciones` (versiones devueltas por el auditor o por Didi), `errores_factuales` (afirmaciones equivocadas detectadas después de publicar) y `fallos_publicacion`.

**Tasas que se calculan en la revisión** (no se guardan en la base; se anotan en el registro de la sección 10):

| Tasa | Cálculo |
| --- | --- |
| De conversación a lista | `leads` ÷ `conversaciones` |
| De lista a cualificado | Leads en `CUALIFICADO` o más ÷ `leads` |
| Asistencia a demostraciones | `demos_realizadas` ÷ `solicitudes_demo` |
| Interacción por publicación | (reacciones + comentarios + compartidos + guardados + clics) ÷ alcance; la calcula el sistema en puntos básicos |

## 4. Métricas por canal

| Canal | Qué mirar primero | Dónde sale el dato | Qué no cuenta como éxito |
| --- | --- | --- | --- |
| Facebook | `alcance`, `comentarios`, `compartidos`, `conversaciones` | Meta Business Suite | Reacciones sin conversación |
| Instagram | `alcance`, `guardados`, `compartidos`, `conversaciones` | Meta Business Suite | Seguidores |
| LinkedIn | `impresiones`, `comentarios`, `conversaciones` | Estadísticas de cada publicación del perfil | Visitas al perfil |
| TikTok | `visualizaciones`, `retencion_promedio_ms`, `compartidos` | TikTok Studio | Seguidores |
| YouTube | `visualizaciones`, `retencion_promedio_ms` | YouTube Studio | Suscriptores |
| WhatsApp | `conversaciones` | Conteo propio de chats nuevos con «BETA» o «DEMO» | — |
| Landing | `visitas`, `formularios` | Cloudflare Web Analytics (sin cookies) y el receptor del formulario | — |

- **Origen de cada lead:** `--fuente` con la forma `<canal>-dm` (`facebook-dm`, `instagram-dm`, `linkedin-dm`, `tiktok-dm`), `whatsapp` o `landing`.
- **Qué pieza lo trajo:** se pregunta con naturalidad «¿Dónde nos viste?». Si la persona nombra una publicación, se suma a `conversaciones` de esa publicación. Si no, se suma solo a la cuenta de campaña.
- **Respuestas a encuestas de historias** (C09) no tienen métrica propia: se registran como `comentarios` con `--nota "respuestas a encuesta"`.
- La analítica de Cloudflare guarda los datos completos 7 días y luego muestrea: las visitas se copian cada domingo.

## 5. Qué es medido y qué es estimado

| Es `MEDIDA` | Es `ESTIMADA` |
| --- | --- |
| Un número que Didi vio en las estadísticas de la red o que viene en su CSV | Un número calculado o supuesto, como el alcance de una pieza reenviada en un grupo sin estadísticas |
| El conteo de leads con consentimiento en la base | Los minutos de producción calculados de memoria |
| Las conversaciones contadas una por una en la bandeja | Cualquier «personas que lo vieron» sin un panel que lo respalde |

Si no lo viste, es estimado o no se registra. Una estimación lleva en `--nota` cómo se calculó. Ninguna cifra estimada se publica ni se presenta como resultado.

## 6. Cómo se registra

En los comandos, las fechas van como AAAA-MM-DD. Los valores son enteros.

| Para qué | Comando |
| --- | --- |
| Confirmar una publicación (sin esto no hay dónde colgar la métrica) | `python -m mos publicacion confirmar <número> --url https://…` |
| Ver el número de cada publicación | `python -m mos publicacion listar` |
| Métrica de una publicación | `python -m mos metrica registrar --nombre alcance --valor [número] --publicacion [número] --fecha 2026-10-18` |
| Métrica estimada | Lo mismo con `--naturaleza ESTIMADA --nota "cómo se estimó"` |
| Métrica de la campaña | `--campana lista-espera-beta` en lugar de `--publicacion` |
| Importar el CSV que exporta una red, o una planilla propia | `python -m mos metrica importar --archivo instagram.csv --revisar` para ver qué entendería sin guardar nada; luego, lo mismo sin `--revisar` |
| Cargar o actualizar los experimentos de la campaña | `python -m mos experimento cargar campanas/lista-espera-beta` |
| Ver cómo va un experimento | `python -m mos experimento resultado EXP-01` |
| Resumen y recomendaciones | `python -m mos metrica resumen --desde 2026-10-15 --hasta 2026-10-18 --producto cuadra` |
| Embudo de leads | `python -m mos lead embudo --producto cuadra` |
| Seguimientos pendientes | `python -m mos lead seguimientos` |

Cómo se comporta el sistema:

- **Registrar dos veces no duplica.** La misma métrica, de la misma publicación o campaña, con la misma fecha, naturaleza y origen, reemplaza a la anterior.
- **El resumen toma el último valor** de cada métrica por publicación o campaña dentro del rango. Por eso se registran **acumulados** con la fecha del domingo, no lo sumado en la semana.
- **Sin fechas**, `metrica resumen` va del primer día del mes hasta hoy. El panel (pantalla Métricas) muestra los últimos 28 días y solo registra métricas de publicaciones; las de campaña van por la línea de comandos.
- **El CSV de cada red se lee tal como llega** (coma, punto y coma o tabulador; UTF-8, UTF-16 o Windows-1252). Los encabezados se traducen con `semillas/metricas-csv.toml`; esos nombres son probables y quedan por verificar con el primer archivo real de cada red. El comando lista las columnas que no reconoce: si una es una métrica, se agrega su nombre en ese archivo. Una columna que no está ahí no se importa.
- **Cada fila se enlaza con una publicación confirmada** por su URL (sin parámetros como `?igsh=`) o por su id en la red (`publicacion confirmar --id-externo`). Las filas que no coinciden se cuentan y se muestran, nunca se adivinan. Las filas de descripción o de totales que agregan algunas redes se saltan.
- **La fecha** es el día en que se tomó el dato: `--fecha`, o hoy si falta. Una planilla propia puede traer una columna `fecha` en AAAA-MM-DD por fila; la fecha de publicación que traen las redes no se usa. Una fecha en otro formato deja la fila fuera.
- **Solo números enteros.** «1.234», «1,234» y «1 234» se leen como 1234; «12.5», «4,5 %» o «1,2 mil» no se importan y se cuentan como no leídos. La retención va en milisegundos y sin decimales.

## 7. Revisión semanal de los domingos

Fechas de la campaña: 18/10, 25/10, 01/11 y 08/11/2026, más el cierre propuesto del 15/11/2026. Orden de trabajo, después de la copia de seguridad de `OPERACION-DIARIA.md`:

1. Confirmar con su enlace todo lo publicado en la semana.
2. Exportar de cada red el CSV de estadísticas e importarlo con `--fecha` del domingo (primero con `--revisar`). Lo que la red no exporta se copia a mano con `metrica registrar`.
3. Registrar `conversaciones` de campaña (acumulado) y, si ya hay lista, `leads` con consentimiento (acumulado).
4. Responder lo pendiente y revisar `lead seguimientos`.
5. Correr `metrica resumen` de la semana y de toda la campaña (desde el 15/10/2026).
6. Revisar los umbrales (sección 8) y los experimentos (sección 9) con `experimento resultado` o la pantalla Métricas. Decidir CONTINUAR, MODIFICAR, DETENER o INVESTIGAR, con el motivo.
7. Hacer la tarea del día que fija `campana.toml`: 18/10 voz de C13; 25/10 revisión de la meta y noticia C12 al contador; 01/11 decisión sobre la landing; 08/11 demostraciones y tres piezas para repetir.
8. Anotar las decisiones: `experimento cerrar EXP-01 --decision CONTINUAR --resultado "…"` (o `cancelar --motivo "…"`).

## 8. Umbrales para decidir

**Reglas del sistema** (código en `mos/metricas.py`; no son hipótesis):

- Para comparar piezas hacen falta al menos 3 publicaciones con 200 o más de alcance medido. Si no, la recomendación es INVESTIGAR.
- Una publicación con leads o pedidos de demostración medidos: CONTINUAR, repitiendo el tema en otro formato.
- Interacción de 1,5 veces la mediana o más: CONTINUAR con otro llamado. De la mitad de la mediana o menos: MODIFICAR el gancho.
- Para reciclar: piezas con interesados o guardados publicadas hace 60 días o más.

**Reglas de operación** (`EMBUDOS-Y-LEADS.md`; tampoco son hipótesis): respuesta en menos de 48 horas; tres mensajes sin respuesta y el lead pasa a `PERDIDO`; baja el mismo día; cualificado = 5 o más empresas, Windows, trabaja con Excel u otro sistema y quiere probar.

**Umbrales propuestos (todos son hipótesis; se ajustan con datos):**

| Señal | Cuándo se mira | Umbral (hipótesis) | Decisión |
| --- | --- | --- | --- |
| Conversaciones con «BETA» acumuladas | 25/10/2026 | Menos de 5 | MODIFICAR: más piezas de oficio con llamado directo; revisar ganchos |
| | | 15 o más | CONTINUAR y priorizar lo legal para abrir la lista |
| Leads con consentimiento | 08/11/2026 | Menos de 10 | Bajar la meta de la próxima campaña y apoyarse en demostraciones uno a uno |
| | | 30 o más antes del 13/11/2026 | No subir la frecuencia; dedicar el tiempo a cualificar |
| De conversación a lista | Cada domingo | Menos de 50 % | Revisar la respuesta a «BETA» (EXP-04) |
| Asistencia a demostraciones | Desde el 08/11/2026 | Menos de 70 % | Recordatorio el día anterior y horarios distintos |
| Canal sin conversaciones | Tras 4 publicaciones en ese canal | 0 | Reducir su frecuencia a la mitad; no abandonarlo antes de la próxima campaña |
| `horas_produccion_min` por pieza | Cada domingo | Más de 120 de media | Reutilizar más entre redes y hacer menos vídeos nuevos |
| `errores_factuales` | Siempre | 1 o más | DETENER esa pieza, corregirla o retirarla y revisar por qué pasó el auditor |

Con pocos datos, una diferencia es un indicio, no una prueba. Con menos de 30 casos por grupo, toda decisión es provisional y se anota así.

## 9. Cinco experimentos para la campaña

Los cinco están escritos en `campanas/lista-espera-beta/experimentos.toml` y se cargan en la base con `python -m mos experimento cargar campanas/lista-espera-beta`. Volver a cargar actualiza la definición sin tocar el estado, el resultado ni la decisión. Ninguno cuesta dinero ni necesita rastreo.

- **EXP-01 a EXP-03 se calculan solos** con `experimento resultado` y en la pantalla Métricas: suman los numeradores y el denominador de las publicaciones confirmadas de cada grupo, con el último valor **medido** de cada una (lo estimado no entra), y dicen qué grupo supera el umbral. Con menos de 30 publicaciones por grupo el resultado se marca como indicio. Las piezas sin publicación confirmada o sin el denominador se listan como «sin dato».
- **EXP-04 y EXP-05 se miden fuera de las publicaciones** (leads y conversaciones); su resultado se escribe al cerrarlos.
- **La decisión siempre es de Didi:** `experimento empezar`, `experimento cerrar --decision … --resultado "…"` o `experimento cancelar --motivo "…"`. Todo queda en la auditoría.

**EXP-01 · Oficio primero o producto primero**
- Hipótesis (la de la campaña): las piezas de Oficio y control generan más guardados y conversaciones por alcance que las de Producto real.
- Variable: el pilar. Grupos: Oficio y control (C03, C04, C08, C09, C10, C11, C21) frente a Producto real (C06, C13, C14, C15, C17, C18, C19, C25, C26).
- Métrica: (`guardados` + `conversaciones`) ÷ `alcance`, solo medido.
- Duración: del 15/10/2026 al 13/11/2026; lectura el 15/11/2026.
- Criterio (hipótesis): si Oficio llega a 1,5 veces Producto real o más, sube su peso en la próxima mezcla; si queda en dos tercios o menos, sube Producto real; en medio, se mantiene.
- Limitaciones: cada grupo mezcla canales y formatos; la atribución depende de que la persona diga dónde nos vio.

**EXP-02 · Captura real o icono**
- Hipótesis: una pieza de beneficio con captura real de la empresa de ejemplo gana más guardados y conversaciones que la misma plantilla con icono.
- Variable: el visual. Igual en ambas: Instagram, plantilla `beneficio`, llamado «BETA». Grupos: C06 (21/10/2026, con icono) y C17 (03/11/2026, con captura real).
- Condición: que Didi tenga la captura antes del 01/11/2026. Si no, se cancela.
- Métrica: (`guardados` + `conversaciones`) ÷ `alcance`. Duración: del 21/10/2026 al 10/11/2026.
- Criterio (hipótesis): con captura 1,3 veces mejor o más, las capturas pasan a ser prioridad en todas las piezas de producto.
- Limitaciones: temas distintos y una pieza por grupo: es un indicio.

**EXP-03 · Documento o imagen en LinkedIn**
- Hipótesis: en LinkedIn, el documento PDF genera más comentarios y mensajes por impresión que la imagen única.
- Variable: el formato. Grupos: C10 y C16 (documento) frente a C04, C22, C24 y C26 (imagen).
- Métrica: (`comentarios` + `conversaciones`) ÷ `impresiones`. Duración: del 19/10/2026 al 13/11/2026.
- Criterio (hipótesis): si el documento llega a 1,5 veces o más, las guías y la transparencia van como documento; si no, imagen, que cuesta menos producir.
- Limitaciones: temas distintos; las métricas de LinkedIn se copian a mano.

**EXP-04 · Cuándo preguntar por la cartera**
- Hipótesis: si la pregunta «¿cuántas empresas llevas y qué usas hoy?» va en un mensaje aparte, al día siguiente del SÍ, responden más personas que si va junto con la pregunta de novedades.
- Variable: el momento de la pregunta. Igual en ambas: el consentimiento se pide primero y la publicidad, aparte. A = guion actual de `mensajes-y-demo.md`; B = la pregunta de cartera al día siguiente.
- Condición: que la lista esté abierta. Se alterna por día del mes (impar A, par B).
- Métrica: porcentaje de leads con `empresas_que_lleva` registrado y porcentaje que acepta publicidad, por variante; se cuentan sin nombres en la sección 10.
- Duración: dos semanas desde la apertura de la lista.
- Criterio (hipótesis): si B sube las respuestas en 20 puntos o más sin bajar la aceptación de publicidad, se adopta B.
- Limitaciones: pocos casos; la variante se anota en el lead con `lead actualizar [uid] --nota "EXP-04: A"`.

**EXP-05 · Mensaje o landing (depende de la decisión del 01/11/2026)**
- Hipótesis: con la landing publicada y el llamado «Únete a la lista de espera», entran más contadores con consentimiento por semana que solo con «Escríbenos «BETA» por mensaje».
- Variable: la vía de inscripción. Condición: que Didi autorice publicar la landing y que `python -m mos sitio pendientes` salga vacío. Si no, se cancela sin coste.
- Métrica: nuevos `leads` con consentimiento por semana (diferencia de acumulados), `visitas`, `formularios` y `fuente` (`landing` frente a `*-dm`).
- Duración: dos semanas antes y dos después de publicar la landing.
- Criterio (hipótesis): si los leads semanales suben un 50 % o más, la landing pasa a ser el llamado principal; si no, sigue el mensaje y la landing queda de apoyo.
- Limitaciones: es una comparación de antes y después, y el contenido cambia de una semana a otra.

## 10. Registro de experimentos y decisiones

El registro vivo está en la base: `python -m mos experimento listar` y la pantalla Métricas del panel. Esta tabla es el plan de partida.

| Código | Estado | Inicio | Fin | Resultado (solo medido) | Decisión y motivo |
| --- | --- | --- | --- | --- | --- |
| EXP-01 | PLANIFICADO | 15/10/2026 | 13/11/2026 | — | — |
| EXP-02 | PLANIFICADO | 21/10/2026 | 10/11/2026 | — | — |
| EXP-03 | PLANIFICADO | 19/10/2026 | 13/11/2026 | — | — |
| EXP-04 | PLANIFICADO | Al abrir la lista | Dos semanas después | — | — |
| EXP-05 | PLANIFICADO | Si se publica la landing | Dos semanas después | — | — |

Estados posibles, iguales a los de la tabla `experimento`: PLANIFICADO, EN_CURSO, TERMINADO y CANCELADO. Decisiones: CONTINUAR, MODIFICAR, DETENER o INVESTIGAR.

## 11. Qué no se mide

- Nada que necesite cookies, píxeles de seguimiento (de Meta, TikTok u otros), huella digital del navegador ni grabación de sesiones. Por eso no se usan Google Analytics 4 ni Microsoft Clarity.
- La landing usa, solo si Didi lo activa, Cloudflare Web Analytics: sin cookies ni almacenamiento en el navegador.
- No se sigue a personas entre sitios ni se cruza su perfil de redes con la base.
- No se leen perfiles ni grupos con robots, ni cuentas de competidores con sesión.
- No se compran ni alquilan listas de contactos.
- No se mide la apertura de correos con imágenes de rastreo.
- Los enlaces pueden llevar parámetros de campaña (UTM) por pieza y canal, nunca un identificador de persona.
- No se miden seguidores como meta, ni ventas, ingresos u horas ahorradas: no existen todavía.
- Ningún dato personal entra en una métrica ni en un prompt de IA.
