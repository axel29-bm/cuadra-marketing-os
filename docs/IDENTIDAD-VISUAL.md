# Identidad visual y fábrica de piezas

Estado: **provisional**. Se construyó con lo que pediste en el encargo (fondos blancos o luminosos, azul oscuro, verdes, acentos azules, titulares grandes, capturas reales) y con la apariencia real de Cuadra (negro con lima y letra Geist, según el repositorio del producto al 14/10/2026). Las imágenes de referencia que mencionaste no llegaron; cuando las subas, se ajustan los tokens de `marcas/cuadra/marca.toml` y todas las plantillas cambian a la vez.

## 1. Principios

1. **Lo que se ve es real.** Ninguna pieza simula la pantalla de Cuadra. Si una pieza necesita mostrar el producto, usa una captura real con la empresa de ejemplo y lo dice debajo («Captura real de Cuadra con una empresa de ejemplo»).
2. **Una idea por pieza.** Un titular grande, un apoyo corto y un llamado. Si hace falta más, es un carrusel.
3. **Claridad antes que adorno.** Fondo blanco, texto azul noche, un solo resaltado lima por titular.
4. **Hecha para el celular.** El formato principal es vertical 4:5 (1080 × 1350). Los textos se leen sin hacer zoom.
5. **Consistencia por código.** Las plantillas leen los colores por nombre. Nadie escribe un color a mano.

## 2. Tokens (marcas/cuadra/marca.toml)

| Token | Color | Uso |
| --- | --- | --- |
| `fondo` | #FFFFFF | Fondo de casi todas las piezas |
| `superficie` | #F3F6F1 | Cajas de listas, paneles, motivo de cuadros |
| `borde` | #D9E1D3 | Bordes finos |
| `tinta` | #0B1626 | Titulares, botón principal, bloques oscuros |
| `texto` / `texto_suave` | #1C2733 / #4A5868 | Texto de apoyo y notas |
| `acento` | #1E50D6 | Iconos, etiquetas, enlaces |
| `destacado` | #D4FF3F | El lima del producto: resaltado del titular y sellos. Siempre con texto en tinta, nunca texto lima sobre blanco |
| `exito` | #147A3B | Marcas de verificación, lo que «cuadra» |
| `alerta` | #A84B0C | Avisos («Cuadra está en desarrollo») |
| `oscuro` | #0B1626 | Fondos de lanzamiento, cierre de carrusel y de vídeo |

Contraste comprobado a ojo en las previsualizaciones; la tinta sobre blanco y sobre lima supera de sobra el mínimo de lectura.

**Tipografía:** Geist (licencia OFL, incluida en `recursos/tipografias/geist`), la misma del producto. Titulares en peso 750 con interletrado apretado; textos en 450 a 560. Geist Mono para fechas y contadores.

**Forma:** esquinas redondeadas de 24 px (12 px las chicas), margen de 72 px en un lienzo de 1080, separación de 24 px.

**Iconos:** Lucide 1.49.0 (ISC), 30 iconos en `recursos/iconos/lucide`, trazo 1.75. Para agregar uno, se copia de la misma versión del paquete.

**Motivo de marca:** cuatro cuadros redondeados, como los del logo, asomando por una esquina. Tres en `superficie` y uno en `destacado`.

**Resaltado:** en cualquier texto de una plantilla, `*palabras*` se pintan con el lima. Uno por titular.

## 3. Plantillas

Cada plantilla vive en `plantillas/<nombre>/` con tres cosas: `plantilla.toml` (campos, límites, formatos y un ejemplo), `plantilla.html.j2` (diseño) y `previa/` (la previsualización exportada con el ejemplo, marcada «Ejemplo de plantilla»).

| Plantilla | Para qué | Formatos | Tipos de pieza |
| --- | --- | --- | --- |
| `educativo` | Lista de 2 a 5 puntos útiles del oficio | vertical, cuadrado, historia | educativa, captación |
| `beneficio` | Una capacidad real, con icono o captura | vertical, cuadrado, historia, enlace | captación, educativa, desarrollo |
| `noticia` | Norma o comunicado oficial: qué cambia, a quién afecta, desde cuándo y fuente | vertical, cuadrado, historia | noticia |
| `carrusel` | 3 a 10 láminas en PNG y un PDF (documento de LinkedIn) | vertical, cuadrado | educativa, captación, desarrollo |
| `trivia` | Pregunta y respuesta en dos láminas, más una versión HTML interactiva | vertical, cuadrado, historia | educativa, humor, captación |
| `meme` | Humor del oficio solo con texto: dos paneles o «Nadie:» | cuadrado, vertical, historia | humor |
| `lanzamiento` | Anuncio grande sobre azul noche (hoy: lista de espera) | vertical, cuadrado, historia, horizontal, enlace | captación, desarrollo, promocional |
| `invitacion-demo` | Qué se verá en una demostración en vivo y cómo pedirla | vertical, cuadrado, historia, enlace | captación |
| `promocion` | Oferta con condiciones y vigencia obligatorias | vertical, cuadrado, historia | promocional (bloqueada en prelanzamiento) |
| `motion` | Vídeo por escenas, con guion, teleprompter y subtítulos | historia, vertical, cuadrado, horizontal | educativa, captación, desarrollo, humor |

Formatos: cuadrado 1080 × 1080 · vertical 1080 × 1350 · historia 1080 × 1920 · horizontal 1920 × 1080 · enlace 1200 × 627. En historias, el texto crece un 20 % y respeta las zonas que tapan los botones de Instagram y TikTok.

## 4. Cómo se produce una pieza

```powershell
python -m mos fabrica plantillas                       # catálogo
python -m mos pieza crear --titulo "Cierre" --formato post --canal instagram --tipo EDUCATIVA --plantilla educativo
python -m mos pieza version P-0001 --archivo textos.json   # textos de la plantilla, copy, cta y capacidades
python -m mos fabrica render P-0001 --formato vertical --formato historia
```

O desde el panel: en la pieza, «Escribir una versión nueva» (el cuadro JSON se llena con el ejemplo de la plantilla) y luego «Generar imágenes y vídeo».

Qué hace el sistema:
1. Revisa los textos contra la plantilla (obligatorios, largo máximo, número de láminas, iconos y capturas que existan).
2. Arma el HTML con las fuentes, los iconos y el logo incrustados: no depende de Internet.
3. Lo abre en Microsoft Edge (en Windows) o Chromium, sin ventana. Si un texto no cabe, reduce la letra hasta un 55 %; si aun así no cabe, avisa para que lo acortes.
4. Guarda los archivos en `espacio/salidas/P-0001/v<versión>/` y los registra en la base con su huella SHA-256, medida y origen.
5. El auditor ya revisó esos mismos textos: lo que dice la imagen es lo que se aprobó.

Para probar una plantilla con textos sueltos, sin crear una pieza: `python -m mos fabrica probar --plantilla trivia --archivo textos.json`.

## 5. Vídeo con tu voz

1. Escribe el guion por escenas en la plantilla `motion`: lo que va en pantalla, la locución y los segundos.
2. `python -m mos fabrica render P-0005` genera el vídeo mudo, `guion.md` (con palabras por minuto por escena), `subtitulos.srt` y `teleprompter.html` (espacio para iniciar, flechas para la velocidad, E para espejo).
3. Grabas la voz con el celular o el micrófono de la PC leyendo el teleprompter.
4. `python -m mos fabrica render P-0005 --audio voz.m4a` une la voz al vídeo. Si la voz dura más que una escena, ajusta sus segundos y vuelve a renderizar.

Más de 160 palabras por minuto suele sonar apurado. Las escenas pueden llevar una captura real con un zoom suave en lugar de icono: así se arma una demo animada a partir de capturas de verdad.

## 6. Capturas reales del producto

Se guardan en `espacio/capturas/` (privadas, fuera de git) o en `recursos/capturas/` (si se van a versionar). Reglas:
- Siempre con la empresa de ejemplo de Cuadra y datos inventados. Nunca con datos de un cliente.
- Sin RUC, nombres ni importes reales.
- En Windows: `Win + Shift + S` para una captura, OBS Studio para grabar la pantalla.
- Si se recorta o acelera un vídeo, se dice en pantalla.

## 7. Lo que no se hace

- Simular pantallas, botones o resultados de Cuadra.
- Usar imágenes de memes de terceros (derechos de autor y de imagen).
- Fotos de personas reales sin licencia y autorización.
- Imágenes generadas por IA con texto o que imiten la interfaz.
- Colores, tipografías o logos de SUNAT, El Peruano u otras instituciones.
