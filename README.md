# Cuadra Marketing OS

El departamento de marketing de Didi, en su propia PC: investiga, planifica, produce, revisa, organiza, prepara la publicación, mide y aprende. Lo opera una sola persona con agentes de IA y controles humanos. Empieza con **Cuadra** (software contable para el contador peruano multiempresa) y está pensado para sumar otros productos y marcas.

**Coste mensual hoy: S/ 0.** Todo corre en local con software libre o planes gratuitos permanentes. Nada se paga, se publica ni se envía sin la autorización explícita de Didi.

## Qué hace

| Área | Qué hay | Dónde |
| --- | --- | --- |
| Verdad del producto | Matriz de 44 capacidades de Cuadra con evidencia y lo que se puede o no afirmar | `productos/cuadra/capacidades.toml`, `docs/AUDITORIA-CUADRA.md` |
| Auditor de calidad | Bloquea precios sin aprobar, promesas no verificadas, datos personales, noticias sin fuente oficial y llamados a comprar o descargar algo que no existe | `mos/calidad/auditor.py` |
| 11 agentes | Director, investigador, radar, estratega, copywriter, director creativo, productor audiovisual, community manager, leads, analista y auditor. Cada uno con contrato, prompt y criterios de éxito | `mos/agentes/`, `prompts/`, `docs/ARQUITECTURA-AGENTES.md` |
| Contenido | Ideas con puntuación explicable, campañas, piezas con versiones, auditoría, aprobación, paquetes de publicación y registro con prueba | `mos/contenido.py` |
| Leads | Registro sin duplicados, consentimiento probado y separado para publicidad, baja, acceso y supresión | `mos/leads.py`, `docs/EMBUDOS-Y-LEADS.md` |
| Métricas | Importa el CSV de estadísticas de cada red sin inventar datos, separa lo medido de lo estimado, recomienda con explicación y propone reutilizar lo que funcionó | `mos/metricas.py`, `semillas/metricas-csv.toml` |
| Experimentos | Hipótesis escritas en la campaña, calculadas solo con métricas medidas; la decisión la anotas tú | `campanas/lista-espera-beta/experimentos.toml`, `mos/experimentos.py`, `docs/METRICAS-Y-EXPERIMENTOS.md` |
| Fábrica | 10 plantillas con la identidad de Cuadra que exportan PNG, PDF de carrusel, trivia interactiva, vídeo MP4, guion, teleprompter y subtítulos, sin Internet | `plantillas/`, `mos/fabrica/`, `docs/IDENTIDAD-VISUAL.md` |
| Campañas | Campañas escritas en un archivo: se cargan sin duplicar, se auditan, se renderizan y salen como calendario y paquete listo para publicar | `campanas/`, `mos/campanas.py` |
| Landing | Página de la lista de espera con formulario de consentimiento, aviso de privacidad en borrador y trivia. Se ve en local; publicarla espera los trámites legales y tu autorización | `sitio/`, `mos/sitio.py`, `docs/CANALES-Y-PUBLICACION.md` |
| Panel | Todo lo anterior con clics, en `http://127.0.0.1:8765` | `mos/web/` |
| Radar | Fuentes oficiales (SUNAT, El Peruano, MEF) que se leen solas respetando `robots.txt`; lo nuevo entra sin verificar hasta que alguien lee la fuente | `semillas/fuentes.toml`, `mos/radar_lector.py` |
| Rutinas | Diaria (respaldo, radar y lo pendiente), semanal (resumen del director) y mensual (experimentos, piezas para reutilizar y herramientas por revisar), a mano o programadas en Windows; el panel avisa si dejan de correr | `mos/rutina.py`, `docs/AUTOMATIZACIONES.md` |
| Herramientas | Registro de herramientas con coste, licencia, límites, riesgo, decisión y fuente | `docs/REGISTRO-HERRAMIENTAS-Y-COSTES.md` |

## Empezar en 3 comandos

Necesitas Python 3.11 o superior. El núcleo no tiene dependencias externas.

```powershell
git clone https://github.com/axel29-bm/cuadra-marketing-os.git
cd cuadra-marketing-os
python -m mos iniciar
```

Luego abre el panel, que es donde se trabaja cada día:

```powershell
python -m mos web                                     # http://127.0.0.1:8765, solo en esta PC
```

O usa la línea de comandos:

```powershell
python -m mos estado                                  # resumen del sistema
python -m mos capacidades cuadra --detalle            # qué se puede afirmar y cómo
python -m mos auditar --texto "Tu texto" --cta "Pide una demostración"
python -m mos agentes --detalle                       # los roles y sus contratos
python -m mos campana cargar campanas/lista-espera-beta   # la campaña de lanzamiento, auditada
python -m mos campana render campanas/lista-espera-beta   # sus imágenes, PDF y vídeos
python -m mos sitio ver                                   # la landing en http://127.0.0.1:8766
python -m mos sitio pendientes                            # lo que falta para poder publicarla
python -m mos rutina diaria                               # respaldo, radar y lo pendiente del día
python -m mos metrica importar --archivo instagram.csv --revisar   # qué entendería del CSV de la red, sin guardar
python -m mos experimento cargar campanas/lista-espera-beta        # los cinco experimentos de la campaña
```

**La campaña de lanzamiento** (30 días, 26 piezas, paquete exportado) está en `campanas/lista-espera-beta/`: empieza por su `LEEME.md`.

La guía completa está en `docs/INSTALACION.md`, la rutina de cada día en `docs/OPERACION-DIARIA.md` y cómo sale cada pieza hacia las redes en `docs/CANALES-Y-PUBLICACION.md`.

## Cómo trabajan los agentes sin pagar una API

El modo por defecto es **asistido**: el sistema prepara el prompt completo de la tarea, con el contexto verificado del producto, y tú (o Claude Code en este repositorio) lo resuelves con la IA que ya usas. La respuesta vuelve al sistema, que la valida contra el contrato del agente y el auditor antes de darla por buena.

```powershell
python -m mos tarea crear --agente copywriter --objetivo "Copys del post de importación" --entradas "{\"pieza\": \"Post\", \"brief\": \"Importar compras desde Excel\", \"canal\": \"facebook\", \"tipo_afirmacion\": \"CAPTACION\"}"
python -m mos tarea preparar T-0001        # deja espacio/tareas/T-0001/PROMPT.md
python -m mos tarea completar T-0001       # lee espacio/tareas/T-0001/resultado.json y lo valida
```

También hay modo **local** (Ollama, sin coste por uso) y modo **externo** (apagado hasta que Didi lo autorice, con tope diario y bloqueo de datos personales).

## Pruebas

```powershell
python -m unittest discover -s tests -t .
node --test sitio/receptor/worker.test.mjs     # receptor del formulario (Node 22)
```

## Reglas que no se rompen

- Este repositorio **no modifica** el repositorio de Cuadra (`contatony-2`): solo lo lee para auditar.
- Ninguna afirmación sale sin respaldo en la matriz de capacidades. Ninguna noticia normativa sale sin fuente oficial y revisión de un contador.
- Ninguna publicación se da por hecha sin su URL o su identificador externo.
- Ningún gasto, prueba de pago, publicación o envío de mensajes sin autorización explícita de Didi.
- Ningún secreto en el código: las claves solo viven en variables de entorno.
- Ningún dato personal real en el repositorio, los prompts, los registros ni los ejemplos.

Estado del trabajo: `docs/PROGRESO.md`. Hoja de ruta: `docs/ROADMAP.md`.
