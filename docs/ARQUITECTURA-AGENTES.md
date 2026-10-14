# Arquitectura de agentes

Este documento explica cómo trabaja el departamento de marketing automatizado: qué es un agente, cómo se le encarga trabajo, cómo se comprueba que lo hizo bien y qué controles humanos existen. La referencia de cada rol al final se genera desde el código (`mos/agentes/registro.py`), así que coincide con lo que el sistema exige.

## 1. Un agente es un contrato, no un proceso suelto

Cada uno de los 11 roles tiene:

- **Responsabilidad** y lo que **no hace** (límites explícitos del rol).
- **Entradas** y **salida** con esquema. El sistema rechaza entradas incompletas al crear la tarea y salidas que no cumplen el esquema al recibirlas.
- **Criterios de éxito** que son código: por ejemplo, el copywriter debe entregar al menos dos variantes y ninguna puede tener un bloqueo del auditor; el radar no puede marcar como fuente primaria un enlace que no sea de un dominio oficial; el community manager no puede dejar una consulta tributaria sin intervención humana.
- **Prompt** (para los roles que razonan): `prompts/<rol>.md`, precedido por las reglas comunes de `prompts/_comun.md`.
- **Aprobación humana** obligatoria en los roles sensibles (radar, estratega, community manager).

Ocho roles razonan o redactan con IA (director, investigador, radar, estratega, copywriter, director creativo, productor audiovisual y community manager). Tres son código determinista (leads, analista, auditor): no cuestan nada, no inventan y siempre dan el mismo resultado con los mismos datos.

## 2. La tarea: el contrato común de trabajo

Toda tarea queda en la tabla `tarea` con estos campos (los que pidió Didi en la sección 12 del encargo):

| Campo | Dónde |
| --- | --- |
| Identificador | `codigo` (T-0001) |
| Agente | `agente` |
| Objetivo | `objetivo` |
| Entradas | `entradas` (JSON validado contra el esquema del rol) |
| Restricciones | `restricciones` (lista; se agregan al prompt) |
| Salida esperada | `salida_esperada` (el esquema, legible) |
| Estado | `estado` |
| Resultado | `resultado` (solo si pasó la validación) |
| Evidencias | `evidencias` (rutas de archivos, enlaces) |
| Errores | `errores` (cada intento fallido con sus problemas) |
| Coste estimado y real | `coste_estimado_c`, `coste_real_c` (céntimos de sol) |
| Aprobación humana | `requiere_aprobacion` y el evento `APROBADA` con quién y cuándo |

Cada paso queda además en `tarea_evento` (creada, preparada, rechazada, validada, aprobada, cancelada, vencida, llamada a la IA).

### Estados

```
PENDIENTE ─▶ PREPARADA ─▶ (resultado) ─┬─▶ COMPLETADA
                │                      ├─▶ REQUIERE_APROBACION ─▶ COMPLETADA (Didi aprueba)
                │                      └─▶ EN_CURSO (no pasó: se corrige y se reintenta)
                │                                  └─▶ FALLIDA (al tercer intento)
                └─▶ FALLIDA (vence el plazo sin resultado) · CANCELADA (a mano)
```

### Garantías contra los fallos típicos de los agentes

| Riesgo | Control |
| --- | --- |
| Bucles | Profundidad máxima de subtareas: 3. Máximo 10 subtareas por tarea. Máximo 3 intentos por tarea |
| Duplicados | Clave de idempotencia (agente + objetivo + entradas). La misma tarea activa no se crea dos veces |
| Tareas colgadas | Plazo (`vence_en`, 72 h por defecto). `python -m mos estado` marca como fallidas las vencidas, con motivo |
| Éxito falso | La base impide `COMPLETADA` sin resultado, y el motor solo guarda resultados que pasan esquema y criterios |
| Errores silenciosos | Todo error queda en `registro_error` y se ve con `python -m mos errores` |
| Gasto oculto | Modo externo apagado por defecto, con autorización revocable, tope diario de llamadas y coste registrado por tarea |
| Fuga de datos personales | Los prompts con correos o teléfonos se rechazan antes de llamar a cualquier IA |
| Afirmaciones falsas | Todo texto pasa por el auditor, que contrasta con la matriz de capacidades del producto |

## 3. Los cuatro modos de ejecución

| Modo | Quién razona | Coste | Cuándo |
| --- | --- | --- | --- |
| DETERMINISTA | Código | S/ 0 | Leads, analista y auditor |
| ASISTIDO (por defecto) | La IA que Didi ya usa, o Claude Code en este repositorio, con el prompt que prepara el sistema | S/ 0 adicional | Siempre disponible |
| LOCAL | Un modelo abierto en la PC con Ollama (por ejemplo Qwen3.5 4B o 9B) | S/ 0 por uso; consume RAM y tiempo | Cuando la PC lo permita |
| EXTERNO | Un proveedor con interfaz compatible con OpenAI | Puede costar | Solo con `python -m mos autorizar IA_EXTERNA`, clave en `MOS_IA_CLAVE` y tope diario |

**Sobre la suscripción de Claude.** Los términos de consumo de Anthropic prohíben el acceso automatizado a los productos de suscripción salvo con clave de API o permiso explícito. Por eso Claude Code se usa aquí como herramienta de trabajo supervisada (Didi la abre, ve lo que hace y aprueba), no como motor oculto de agentes desatendidos. Ejecutar agentes sin supervisión requeriría una clave de API de pago, que no se usa sin autorización.

## 4. Cómo se encadenan los roles

```
             objetivos de Didi
                    │
                 director ──────────────▶ prioridades de la semana
                    │
   investigador ─▶ estratega ─▶ ideas y campañas (Didi aprueba)
   radar ─────────┘    │
                       ▼
               copywriter ─▶ director creativo ─▶ fábrica (plantillas → PNG/PDF/MP4)
                       └──▶ productor audiovisual ─▶ guion, teleprompter, montaje
                                        │
                                  auditor (barrera) ─▶ aprobación de Didi ─▶ paquete de publicación
                                                                                    │
       community manager ◀── comentarios y mensajes ◀── publicación (manual o programador nativo)
       leads ◀── formularios y conversaciones                                       │
       analista ◀── métricas medidas ◀──────────────────────────────────────────────┘
                    │
                 director (siguiente semana)
```

Ningún rol publica, envía mensajes ni gasta. Esas tres cosas siempre las hace o autoriza Didi.

## 5. Herramientas por rol

| Rol | Herramientas | Nunca usa |
| --- | --- | --- |
| Director | Estado del sistema (`python -m mos estado`), métricas, tareas, presupuesto | Pagos |
| Investigador | Webs públicas de competidores, fuentes oficiales, entrevistas que haga Didi | Cuentas de terceros, datos de clientes |
| Radar | `semillas/fuentes.toml` (sitemap de El Peruano, índices de SUNAT, MEF), respetando robots.txt | Sistemas con clave (SOL), rutas prohibidas |
| Estratega | Matriz de capacidades, audiencias, banco de ideas, calendario | Cifras de mercado sin fuente |
| Copywriter | Matriz de capacidades, límites del canal (`semillas/canales.toml`) | Testimonios, precios |
| Director creativo | Plantillas de `plantillas/`, identidad de `marcas/` | Imágenes generativas con texto o con interfaz simulada |
| Productor audiovisual | Plantillas animadas, FFmpeg, faster-whisper, guion para la voz de Didi | Pantallas que no existen |
| Community manager | Comentarios que Didi copie o exporte | Envío automático |
| Leads | Tabla `lead`, consentimientos, lista de supresión | Contacto sin consentimiento |
| Analista | Tabla `metrica` (manual o CSV de cada red) | Estimaciones presentadas como medidas |
| Auditor | Matriz, prohibiciones, etapa comercial, límites de canal | La opinión del agente anterior |

## 6. Referencia de los roles (generada desde el código)

### Director de marketing y orquestador (`director`)

Prioriza campañas y tareas según objetivos comerciales, evita duplicidades, vigila el presupuesto y resume la semana. Su prioridad son oportunidades comerciales, no volumen de contenido.

- **Modo:** Asistido, local o externo.
- **Prompt:** `prompts/director.md` (más `prompts/_comun.md`).
- **Criterios de éxito:** prioridades_accionables.
- **Aprobación humana:** no para completar la tarea; sí para publicar lo que produzca.
- **No hace:** aprobar gastos; publicar; inventar resultados.
- **Límites:** 3 intentos, 10 subtareas por tarea.

Entradas:
```
{
  "periodo": texto
  "estado_del_sistema": objeto
  "objetivos": lista de:
    texto (opcional)
}
```

Salida:
```
{
  "resumen": texto
  "prioridades": lista de:
    {
      "accion": texto
      "motivo": texto
      "responsable": texto
    }
  "bloqueos": lista de:
    texto (opcional)
  "experimentos": lista de:
    {
      "codigo": texto
      "decision": "CONTINUAR" | "MODIFICAR" | "DETENER" | "INVESTIGAR"
      "motivo": texto
    } (opcional)
}
```

### Investigador de mercado y competencia (`investigador`)

Investiga problemas del público, competidores, mensajes y objeciones. Separa hechos con fuente de hipótesis.

- **Modo:** Asistido, local o externo.
- **Prompt:** `prompts/investigador.md` (más `prompts/_comun.md`).
- **Criterios de éxito:** hechos_con_fuente, hipotesis_sin_cifras.
- **Aprobación humana:** no para completar la tarea; sí para publicar lo que produzca.
- **No hace:** inventar comentarios, conversaciones o métricas de competidores.
- **Límites:** 3 intentos, 10 subtareas por tarea.

Entradas:
```
{
  "pregunta": texto
  "producto": texto
}
```

Salida:
```
{
  "hechos": lista de:
    {
      "afirmacion": texto
      "url": texto
      "fecha_consulta": texto
    }
  "hipotesis": lista de:
    {
      "enunciado": texto
      "como_validar": texto
    }
  "preguntas_abiertas": lista de:
    texto (opcional)
}
```

### Radar contable, tributario y de noticias (`radar`)

Detecta novedades en fuentes oficiales y propone contenido. Nunca marca una noticia como verificada: eso lo hace una persona.

- **Modo:** Asistido, local o externo.
- **Prompt:** `prompts/radar.md` (más `prompts/_comun.md`).
- **Criterios de éxito:** fuentes_oficiales.
- **Aprobación humana:** sí, antes de usar su resultado.
- **No hace:** presentar rumores como noticias; interpretar normas sin revisión de un contador.
- **Límites:** 3 intentos, 10 subtareas por tarea.

Entradas:
```
{
  "items_detectados": lista de:
    objeto
}
```

Salida:
```
{
  "items": lista de:
    {
      "titulo": texto
      "url": texto
      "fecha_publicacion": texto
      "fecha_vigencia": texto (opcional)
      "afecta_a": texto
      "que_cambia": texto
      "es_fuente_primaria": sí/no
      "advertencias": texto
      "propuesta_contenido": texto
    }
}
```

### Estratega editorial y de campañas (`estratega`)

Convierte objetivos e investigación en campañas, series y calendarios con hipótesis, oferta, CTA y métrica.

- **Modo:** Asistido, local o externo.
- **Prompt:** `prompts/estratega.md` (más `prompts/_comun.md`).
- **Criterios de éxito:** campanas_completas.
- **Aprobación humana:** sí, antes de usar su resultado.
- **Límites:** 3 intentos, 10 subtareas por tarea.

Entradas:
```
{
  "producto": texto
  "objetivo": texto
  "periodo": texto (opcional)
  "capacidad_produccion": texto (opcional)
}
```

Salida:
```
{
  "campanas": lista de:
    {
      "nombre": texto
      "objetivo": texto
      "audiencia": texto
      "hipotesis": texto
      "oferta": texto
      "cta": texto
      "metrica_exito": texto
      "canales": lista de:
        texto
      "piezas": lista de:
        {
          "fecha": texto
          "formato": texto
          "canal": texto
          "tema": texto
          "etapa_embudo": "ATENCION" | "INTERES" | "CONSIDERACION" | "CONVERSION" | "FIDELIZACION"
          "objetivo": texto
        }
    }
}
```

### Copywriter y guionista (`copywriter`)

Escribe ganchos, copys, CTAs y variantes por canal, en español natural de Perú, sin promesas que no se puedan mostrar.

- **Modo:** Asistido, local o externo.
- **Prompt:** `prompts/copywriter.md` (más `prompts/_comun.md`).
- **Criterios de éxito:** copys_sin_bloqueos.
- **Aprobación humana:** no para completar la tarea; sí para publicar lo que produzca.
- **No hace:** inventar testimonios, cifras o precios.
- **Límites:** 3 intentos, 10 subtareas por tarea.

Entradas:
```
{
  "pieza": texto
  "brief": texto
  "canal": texto
  "tipo_afirmacion": "EDUCATIVA" | "PROMOCIONAL" | "DESARROLLO" | "NOTICIA" | "HUMOR" | "CAPTACION"
}
```

Salida:
```
{
  "variantes": lista de:
    {
      "gancho": texto
      "copy": texto
      "cta": texto
      "capacidades": lista de:
        texto
      "hashtags": lista de:
        texto (opcional)
    }
}
```

### Director creativo y diseñador gráfico (`director_creativo`)

Elige concepto, plantilla y jerarquía visual; entrega los textos definitivos de cada campo de la plantilla.

- **Modo:** Asistido, local o externo.
- **Prompt:** `prompts/director_creativo.md` (más `prompts/_comun.md`).
- **Criterios de éxito:** concepto_visual.
- **Aprobación humana:** no para completar la tarea; sí para publicar lo que produzca.
- **No hace:** generar texto dentro de imágenes generativas; recrear pantallas que no existen.
- **Límites:** 3 intentos, 10 subtareas por tarea.

Entradas:
```
{
  "pieza": texto
  "tipo_afirmacion": "EDUCATIVA" | "PROMOCIONAL" | "DESARROLLO" | "NOTICIA" | "HUMOR" | "CAPTACION"
  "capacidades": lista de:
    texto (opcional)
  "plantilla_sugerida": texto (opcional)
}
```

Salida:
```
{
  "concepto": texto
  "plantilla": texto
  "jerarquia": lista de:
    texto
  "textos": objeto
  "formatos": lista de:
    texto
  "capturas_necesarias": lista de:
    texto (opcional)
}
```

### Productor audiovisual y motion designer (`productor_audiovisual`)

Convierte una idea en un guion por escenas con voz, texto en pantalla, capturas, ritmo y adaptaciones.

- **Modo:** Asistido, local o externo.
- **Prompt:** `prompts/productor_audiovisual.md` (más `prompts/_comun.md`).
- **Criterios de éxito:** guion_coherente.
- **Aprobación humana:** no para completar la tarea; sí para publicar lo que produzca.
- **Límites:** 3 intentos, 10 subtareas por tarea.

Entradas:
```
{
  "pieza": texto
  "tipo_afirmacion": "EDUCATIVA" | "PROMOCIONAL" | "DESARROLLO" | "NOTICIA" | "HUMOR" | "CAPTACION"
  "duracion_objetivo_s": entero
  "capacidades": lista de:
    texto (opcional)
}
```

Salida:
```
{
  "titulo": texto
  "duracion_s": entero
  "gancho": texto
  "escenas": lista de:
    {
      "n": entero
      "duracion_s": entero
      "voz": texto
      "en_pantalla": texto
      "visual": texto
      "capturas": lista de:
        texto (opcional)
    }
  "musica": texto (opcional)
  "instrucciones_montaje": lista de:
    texto
  "adaptaciones": lista de:
    {
      "canal": texto
      "formato": texto
      "copy": texto
    }
}
```

### Community manager (`community`)

Clasifica comentarios y mensajes y redacta borradores de respuesta. No envía nada: lo envía una persona.

- **Modo:** Asistido, local o externo.
- **Prompt:** `prompts/community.md` (más `prompts/_comun.md`).
- **Criterios de éxito:** respuestas_prudentes.
- **Aprobación humana:** sí, antes de usar su resultado.
- **No hace:** prometer descuentos; responder como asesor tributario; afirmar funciones no disponibles.
- **Límites:** 3 intentos, 10 subtareas por tarea.

Entradas:
```
{
  "mensajes": lista de:
    {
      "canal": texto
      "texto": texto
    }
}
```

Salida:
```
{
  "respuestas": lista de:
    {
      "categoria": "INTERES_COMERCIAL" | "DUDA_FUNCION" | "DEMO" | "SOPORTE" | "QUEJA" | "OBJECION" | "TRIBUTARIA" | "SPAM" | "HUMANO"
      "borrador": texto
      "accion_sugerida": texto
      "requiere_humano": sí/no
    }
}
```

### Responsable de leads y embudos (`leads`)

Registra, deduplica y ordena los leads; propone el siguiente seguimiento y detecta cuándo ya no corresponde contactar.

- **Modo:** Determinista (código, sin IA).
- **Prompt:** no usa; es código.
- **Criterios de éxito:** cumplir el esquema de salida.
- **Aprobación humana:** no para completar la tarea; sí para publicar lo que produzca.
- **No hace:** enviar mensajes; contactar sin consentimiento para publicidad.
- **Límites:** 3 intentos, 10 subtareas por tarea.

Entradas:
```
{
  "fecha": texto (opcional)
}
```

Salida:
```
{
  "seguimientos": lista
  "vencidos": entero
  "embudo": objeto
}
```

### Analista de rendimiento (`analista`)

Junta las métricas disponibles, separa lo medido de lo estimado y recomienda qué repetir, cambiar o detener.

- **Modo:** Determinista (código, sin IA).
- **Prompt:** no usa; es código.
- **Criterios de éxito:** cumplir el esquema de salida.
- **Aprobación humana:** no para completar la tarea; sí para publicar lo que produzca.
- **No hace:** atribuir ventas a una publicación sin evidencia; presentar estimaciones como medidas.
- **Límites:** 3 intentos, 10 subtareas por tarea.

Entradas:
```
{
  "desde": texto (opcional)
  "hasta": texto (opcional)
  "producto": texto (opcional)
}
```

Salida:
```
{
  "resumen": objeto
  "recomendaciones": lista de:
    objeto
  "reciclables": lista
}
```

### Auditor de calidad, marca y cumplimiento (`auditor`)

Revisa cada pieza contra la matriz de capacidades, la etapa comercial, las reglas del canal, la privacidad y el estilo. Puede rechazarla y explica qué corregir. No confía en lo que diga el agente anterior.

- **Modo:** Determinista (código, sin IA).
- **Prompt:** no usa; es código.
- **Criterios de éxito:** cumplir el esquema de salida.
- **Aprobación humana:** no para completar la tarea; sí para publicar lo que produzca.
- **Límites:** 3 intentos, 10 subtareas por tarea.

Entradas:
```
{
  "pieza": texto
}
```

Salida:
```
{
  "resultado": "APROBADO" | "CON_OBSERVACIONES" | "RECHAZADO"
  "hallazgos": lista
}
```

