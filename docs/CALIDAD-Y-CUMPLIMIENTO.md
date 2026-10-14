# Calidad y cumplimiento

Cada pieza pasa por dos revisiones antes de publicarse: el **auditor automático** (código en `mos/calidad/auditor.py`) y **Didi**. El auditor no confía en lo que diga el agente que produjo la pieza: vuelve a leer todos los textos, incluidos los de cada lámina de un carrusel o cada escena de un guion.

## 1. Qué bloquea el auditor (la pieza no se puede aprobar)

| Regla | Qué detecta | Base |
| --- | --- | --- |
| Etapa comercial | Pieza promocional de un producto que no está a la venta | Matriz del producto |
| Capacidad no anunciable | Cita una capacidad en desarrollo, planificada o sin evidencia | Matriz del producto |
| Solo en demostración | Promete en un post algo que solo se muestra en vivo | Matriz del producto |
| Afirmación no demostrada | Frases prohibidas de cada capacidad («descárgalo», «envía tu SIRE», «PCGE oficial completo»…) y prohibiciones globales («cumple con SUNAT», «usado por N contadores», «ahorra X horas», escasez inventada) | D. Leg. 1044 art. 8: el anunciante debe tener la prueba **antes** de publicar |
| Precio | Cualquier importe, descuento o precio anterior sin precio aprobado | Código del Consumidor; precedente de INDECOPI sobre descuentos |
| Datos personales | Correos y celulares que no son de la marca, RUC reales, DNI | Ley 29733 |
| Noticia | Sin enlace a fuente oficial primaria, sin fecha de publicación de la fuente o sin revisión de un contador | Política editorial |
| Llamado a la acción | Falta en una pieza de captación, u ofrece comprar, descargar o probar algo que no existe | Matriz del producto |
| Longitud | Supera el máximo del canal (`semillas/canales.toml`) | Reglas de cada red |

## 2. Qué advierte (se puede aprobar, pero conviene corregir)

- Frases de relleno típicas de textos generados («en la era digital», «revoluciona», «lleva tu estudio al siguiente nivel»).
- Superlativos y absolutos («el mejor», «número uno», «100 %», «sin errores»). INDECOPI admite la exageración evidente, pero un superlativo comprobable exige prueba.
- Capacidades con matiz: recuerda la aclaración obligatoria.
- Signos de apertura faltantes (¿ ¡), palabras repetidas, espacios dobles, «S/.» en lugar de «S/».
- El nombre de la marca mal escrito.
- Enlaces sin https.
- La pieza habla del producto pero no dice qué capacidades afirma.

## 3. Reglas de publicidad en Perú (resumen práctico)

Fuente: investigación del 14/10/2026 (Código de Protección al Consumidor, D. Leg. 1044 y Lineamientos de INDECOPI de 2019). No es asesoría legal.

1. **Prueba previa.** Toda afirmación objetiva («importa 5,000 comprobantes en segundos», «RUC ilimitados») necesita la prueba antes de publicarse. Si la prueba es de la PC de desarrollo, no vale para la PC del cliente.
2. **Testimonios.** Solo experiencias auténticas y recientes, con autorización escrita, fecha y aclaración si hubo algo a cambio. Hoy no hay ninguno.
3. **Comparativas.** Solo veraces, exactas, pertinentes y verificables, con fecha. El PRD de Cuadra además prohíbe «reemplaza a ContaExcel» hasta cumplir cuatro condiciones. Hoy no se compara con nadie por nombre.
4. **Precios.** Cuando exista precio: precio total con impuestos claro («IGV incluido» o «+ IGV»); un precio tachado solo si ese precio se cobró de verdad; las promociones con duración y condiciones claras.
5. **Contenido patrocinado.** Si alguna vez un tercero publica por encargo, se rotula como «publicidad».

## 4. Reglas editoriales

- **Noticias normativas:** fuente oficial primaria (SUNAT, El Peruano, MEF, gob.pe), fecha de publicación, fecha de vigencia si la hay, a quién afecta y revisión de un contador. Sin revisión, la pieza no se publica.
- **Demostraciones:** pantallas reales de Cuadra con la empresa de ejemplo. Si se acelera o se corta, se dice en pantalla. Nunca se simula una función que no existe.
- **Imágenes generativas:** solo fondos o ilustraciones sin texto y sin simular la interfaz. Se registra su origen y licencia en la tabla `activo`.
- **Humor:** sobre situaciones del oficio, nunca sobre clientes, colegas con nombre, SUNAT como institución en tono despectivo ni competidores.

## 5. Revisión humana

Didi aprueba cada pieza con `python -m mos pieza aprobar P-XXXX`. La aprobación queda ligada al hash de la versión: si cambia una coma, hay que volver a auditar y aprobar. El sistema no deja preparar un paquete de publicación sin aprobación vigente.

## 6. Pruebas de calidad del propio sistema

`tests/test_auditor.py` describe en lenguaje de marketing qué pasa y qué no. Toda regla nueva del auditor entra con su prueba. Si una regla bloquea algo legítimo, se corrige la regla con una prueba que lo demuestre, nunca se desactiva.
