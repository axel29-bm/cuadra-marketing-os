# Paquete de lanzamiento · Lista de espera de la beta privada

Todo lo que hace falta para 30 días de publicaciones de Cuadra, del jueves 15/10/2026 al viernes 13/11/2026. **Nada está publicado ni aprobado.** Cada pieza espera tu aprobación en el panel y la publicas tú, a mano, en cada red.

## Qué hay en esta carpeta

| Archivo | Qué es |
| --- | --- |
| `campana.toml` | La fuente de todo: la campaña, los 30 días y el texto de cada pieza. Si cambias algo, cámbialo aquí |
| `CALENDARIO.md` y `calendario.csv` | El calendario legible (el CSV abre en Excel). Se generan desde el TOML |
| `exportados/` | Una carpeta por publicación (`fecha-clave`) con las imágenes, el PDF, el vídeo y `texto.md` con el copy listo para pegar |
| `mensajes-y-demo.md` | Cómo responder a quien escribe «BETA» o «DEMO», con la pregunta de consentimiento, y el copy para pedir una demostración |
| `secuencia-seguimiento.md` | Los mensajes de seguimiento, solo para quien aceptó recibirlos |
| `concepto-video-meme.md` | El vídeo meme de TikTok explicado, con variantes y qué música se puede usar |

## Las piezas del paquete pedido

| Pedido | Dónde está |
| --- | --- |
| Flyer comercial | C01 (lanzamiento), C06, C15 y C17 (beneficio) |
| Flyer educativo | C03 y C21 |
| Carrusel | C10 y C11 (guía del SIRE, con PDF para LinkedIn), C16 (lo que ya hace y lo que no) |
| Trivia interactiva | C08 y C09 (láminas) y `C08-fb-interactivo.html` (se juega en el navegador; va en la landing) |
| Guion para tu voz | C13 (cierre de mes) y C18 (importar Excel): `guion.md`, `teleprompter.html` y `subtitulos.srt` |
| Vídeo o demo animada | C13, C14 y C25 (cierre), C18 y C19 (importar Excel). Animación de texto e iconos: no simula pantallas |
| Meme gráfico | C02, C05 y C23 |
| Concepto de vídeo meme | C07 y `concepto-video-meme.md` |
| Noticia con fuente verificada | C12: R.S. N.° 000125-2026/SUNAT, leída en el PDF oficial el 14/10/2026 |
| Landing de captación | Fase 5 (se construye sin publicar; publicarla necesita tu autorización) |
| Copy para solicitar demo | C20 y C22, y `mensajes-y-demo.md` |
| Secuencia de seguimiento con consentimiento | `secuencia-seguimiento.md` |

## Antes de publicar la primera pieza

1. **Revisa y aprueba en el panel** (`python -m mos web`, pantalla Aprobaciones). Lee cada texto: el auditor revisa reglas, no el criterio.
2. **La noticia C12 está frenada** hasta que un contador la lea y confirme el resumen. Cuando lo haga, agrega `revisado_por_contador = true` en su contenido, vuelve a cargar y apruébala.
3. **Los contenidos educativos (C03, C08, C10, C21)** son práctica general del oficio. Conviene que un contador los lea antes.
4. **Antes de anotar a alguien en la lista** (guardar su nombre o contacto fuera del chat de la red): inscribe el banco de datos «Interesados» en el Registro Nacional de Protección de Datos Personales y ten listo el aviso de privacidad (ver `docs/EMBUDOS-Y-LEADS.md`, sección 4). Hasta entonces, conversa por mensaje sin guardar datos.
5. **Ten horarios para demostraciones** antes del 06/11 (C20).
6. **Graba tu voz** para C13 con su teleprompter y vuelve a renderizar: `python -m mos fabrica render P-00xx --audio voz.m4a`.

## Cómo se publica cada día

1. Abre `exportados/<fecha>-<clave>/`.
2. Sube la imagen, el carrusel (las láminas en orden), el PDF (en LinkedIn, como documento) o el vídeo con su portada, desde la app de cada red o desde Meta Business Suite (gratis, permite programar en Facebook e Instagram).
3. Pega el texto de `texto.md`.
4. Copia el enlace de la publicación y regístrala en el panel (Publicaciones → confirmar con enlace). Sin enlace, el sistema no la da por publicada.
5. En los días de revisión (domingos), carga las métricas de la semana en el panel.

## Si no empiezas el 15/10

`python -m mos campana mover campanas/lista-espera-beta --semanas 1` corre todas las fechas una semana (conserva los días de la semana y los domingos de revisión). Luego `cargar` y `calendario` otra vez. Ojo: la semana del 16 al 23 de cada mes es de vencimientos, por eso esa semana lleva humor y contenido ligero.

## Comandos

```powershell
python -m mos campana cargar campanas/lista-espera-beta       # pasa el TOML a la base y audita cada pieza
python -m mos campana render campanas/lista-espera-beta       # imágenes, PDF y vídeos (los que falten)
python -m mos campana calendario campanas/lista-espera-beta   # CALENDARIO.md y calendario.csv
python -m mos campana paquete campanas/lista-espera-beta      # junta todo en exportados/
```

`render --forzar` rehace los archivos aunque existan; `render --solo C13-ig` rehace solo esa pieza. Una misma imagen o vídeo que va a varias redes se renderiza una sola vez.

## Lo que esta campaña no hace

- No promete fecha, precio, descarga, prueba gratis ni funciones que la matriz de capacidades no permite.
- No usa testimonios, clientes, cifras de ahorro ni logos de terceros.
- No publica nada sola ni escribe a nadie que no lo haya pedido.
- La meta de 30 contadores es una meta inicial para revisar en la semana 2, no una predicción.
