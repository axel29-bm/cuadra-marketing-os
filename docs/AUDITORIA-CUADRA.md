# Auditoría de Cuadra para marketing

Fecha de la auditoría: 14 de octubre de 2026.
Fuente auditada: repositorio `axel29-bm/contatony-2`, rama `main`, commit `0411f76` (13/10/2026 23:44, hora de Lima).
Auditor: Claude Code, en modo solo lectura sobre el repositorio contable. No se modificó nada en él.

Este documento responde una sola pregunta: **qué se puede decir hoy de Cuadra en publicidad sin mentir**. La versión que lee el sistema (y que usa el auditor de calidad para bloquear afirmaciones) es `productos/cuadra/capacidades.toml`. Si cambian, manda el archivo TOML y este documento se actualiza.

## 1. Qué se leyó y cómo se verificó

| Fuente | Qué aporta | Fiabilidad |
| --- | --- | --- |
| `CLAUDE.md` | Reglas del producto, stack, prohibiciones | Vigente |
| `docs/PRD.md` (v1.0, 05/10/2026, 4,863 líneas) | Alcance, fases, criterios de beta y de lanzamiento, matriz frente a ContaExcel, riesgos | Vigente como intención. Describe lo planificado, no lo hecho |
| `docs/PROGRESO.md` (bitácora, 1,030 líneas, hasta el 13/10/2026) | Lo realmente construido, con pruebas y pendientes por paso | La fuente más actual del estado |
| `docs/FALTANTES.md` (al 07/10/2026) | Lo que espera algo externo | **Parcialmente desactualizado**: varias filas de su sección 10 ya están hechas según PROGRESO (cobros y pagos, estados financieros, PLE, cierre anual, SIRE por archivo). Las secciones 1 a 9 siguen siendo útiles |
| `GUIA-INICIO.md` | Instalación del entorno de desarrollo | Antigua en un punto: dice que ContaExcel «es de terceros», pero PRD §IV.19 y PROGRESO (decisión D3 del 10/10/2026) dicen que Didi es su autor. Prevalece lo más reciente |
| `docs/contable/LEEME.md` y `CC-01` a `CC-06` | Estado de la validación contable | Los seis casos siguen **pendientes de firma** del socio contador |
| `docs/diseno/sistema-de-diseno.md` | Voz, glosario y apariencia del producto | Vigente desde el 12/10/2026 |
| `src/Cuadra.App/Vistas/*.xaml` | Pantallas existentes | 22 vistas y 6 diálogos |
| `tests/` | Pruebas que respaldan cada función | 528 métodos de prueba; PROGRESO reporta 719 casos, 713 correctos y 6 omitidos a propósito (piden datos reales de SUNAT o la clave del asistente) |
| GitHub Actions, ejecución 38512989944 sobre `0411f76` (14/10/2026) | Verificación independiente | **Núcleo (Linux): compila y pasa. Aplicación (Windows, sin pruebas de interfaz): compila y pasa.** El trabajo «Licencias, vulnerabilidades y SBOM» falló en el paso «Buscar vulnerabilidades» (un paquete con aviso de seguridad; es un asunto del producto, no de marketing) |
| GitHub Releases de `contatony-2` | ¿Hay versiones publicadas? | **Ninguna** |
| `web/index.html` | Portal público | Solo una página «Muy pronto» |
| Ramas remotas | ¿Hay trabajo vigente fuera de `main`? | `feat/ux-pantallas` y `feat/ux-pulido` son anteriores y ya están integradas en `main`. `main` es la versión vigente |

Límites de esta verificación, dichos con claridad:

- **No ejecuté Cuadra.** Es una aplicación WPF que solo corre en Windows y este entorno es Linux. La evidencia de que las pantallas funcionan son las pruebas de interfaz (FlaUI) que PROGRESO dice haber corrido en la PC de Didi; esas pruebas no corren en la CI.
- Las pruebas con datos reales (SUNAT con un RUC real, bases de ContaExcel) están documentadas en PROGRESO y solo corren en la PC de Didi. Las tomo como evidencia declarada, no reproducida.
- Ninguna medición de rendimiento se hizo en la PC de referencia (4 GB de RAM y disco mecánico). Todas son de la PC de desarrollo.

## 2. Qué es Cuadra, en una frase verificable

Un sistema contable de escritorio para Windows, que guarda los datos en la PC del contador (una base cifrada por empresa), pensado para el contador peruano que lleva muchas empresas: ve todas sus empresas en una sola pantalla, registra compras y ventas con su asiento a la vista, importa desde Excel y desde el SIRE, coteja la propuesta del SIRE con su contabilidad y genera libros, estados y archivos para SUNAT.

## 3. Etapa comercial real

**Prelanzamiento. Nada se puede vender ni descargar hoy.**

| Requisito de PRD §XVIII.4 para vender a fundadores | Estado al 14/10/2026 |
| --- | --- |
| MVP técnico (PRD §XIV.1) | Casi todo el código existe. Faltan el envío del SIRE hasta el preliminar y el portal |
| Beta privada superada (20 a 30 contadores) | No empezó |
| Licencia y cobro funcionando | Código y pruebas listos; nube creada a medias (faltan tablas, inicio de sesión por correo y portal). Cobro: no existe |
| Instalador firmado | Instalador generado en la PC de Didi, sin firmar y sin publicar. No hay certificado |
| Términos y política de privacidad revisados por abogado | No existen |
| Casos contables CC-01 a CC-16 firmados | 0 firmados; solo CC-01 a CC-06 están escritos. Los tratamientos contables se basan en ContaExcel (decisión D2) |
| Guías de primeros pasos y de credenciales del SIRE | No existen como material público |
| Canal de soporte | No definido |

Consecuencia para marketing: el objetivo honesto de los próximos meses no es vender, sino **reunir contadores interesados, conseguir participantes para la beta privada y validar el mensaje**. Todo llamado a la acción debe ser de interés (lista de espera, solicitar participar en la beta, pedir una demostración en vivo), nunca de compra o descarga.

## 4. Matriz de verificación

Escala pedida:

- **IMPLEMENTADO Y VERIFICADO**: el código está en `main`, tiene pruebas automáticas, la CI del 14/10/2026 compila y pasa, y PROGRESO documenta el recorrido de interfaz.
- **IMPLEMENTADO PARCIALMENTE**: existe y funciona, pero le falta una parte relevante para afirmarlo sin matices.
- **EN DESARROLLO**: hay código, pero no está terminado o no está probado de punta a punta.
- **PLANIFICADO**: solo existe en el PRD.
- **SIN EVIDENCIA SUFICIENTE**: se afirma o se supone, pero no hay medición ni prueba que lo respalde.

Aun lo verificado lleva una advertencia común: **ningún tratamiento contable está firmado por un contador colegiado**, y nada está disponible al público. Por eso la columna «Cómo se puede usar en marketing» manda sobre la columna de estado.

### 4.1 Trabajo con muchas empresas

| Código | Capacidad | Estado | Evidencia | Cómo se puede usar en marketing |
| --- | --- | --- | --- | --- |
| CU-EMP-01 | Sin tope de empresas en el diseño: una base cifrada por empresa y un catálogo central | IMPLEMENTADO Y VERIFICADO (diseño) · rendimiento a escala SIN EVIDENCIA SUFICIENTE | PRD ADR-06; `Cuadra.Infrastructure` catálogo; POC-3 parte 2 midió 100 empresas y 388,828 compras en la PC de desarrollo | «Pensado para llevar muchas empresas». **No decir** «1,000 empresas sin demoras» ni «RUC ilimitados» como promesa de rendimiento hasta medir en la PC de referencia. El límite comercial de empresas por plan tampoco está decidido |
| CU-EMP-02 | Mis empresas: todas en una pantalla con semáforo, vencimiento, compras, ventas, cierre, pendientes y siguiente acción | IMPLEMENTADO Y VERIFICADO | PROGRESO «Paso 29 · Mi Cartera»; 15 pruebas de dominio, 10 de integración, recorrido de interfaz | Mostrable en demostración con la empresa de ejemplo |
| CU-EMP-03 | Pendientes automáticos: correlativos faltantes, posible duplicado, caja negativa, mes sin cerrar, copia de seguridad fallida, claves SOL rechazadas, diferencias con el SIRE | IMPLEMENTADO Y VERIFICADO (parámetros provisionales) | PROGRESO «Paso 29»; `DetectorDiferenciasSire` | Sí, describiendo qué detecta. Los textos «por qué importa» esperan validación contable |
| CU-EMP-04 | Vencimientos por último dígito del RUC | IMPLEMENTADO PARCIALMENTE | El motor existe; `normative/cronograma.csv` está **vacío a propósito** | No anunciar hasta cargar el cronograma oficial. La pantalla dice «Sin datos» |
| CU-EMP-05 | Buscar cualquier cosa con Ctrl+K y cambiar de empresa con Ctrl+Tab | IMPLEMENTADO Y VERIFICADO | PROGRESO «Ctrl+K y Ctrl+Tab» | Sí |
| CU-EMP-06 | Etiquetas y archivo de empresas | IMPLEMENTADO Y VERIFICADO | PROGRESO «FR-004» | Sí, como detalle |
| CU-EMP-07 | Reportes para varias empresas a la vez (un ZIP con un PDF o Excel por empresa) | IMPLEMENTADO Y VERIFICADO | PROGRESO «FR-074»; 7 pruebas | Sí |

### 4.2 Compras, ventas y asientos

| Código | Capacidad | Estado | Evidencia | Cómo se puede usar en marketing |
| --- | --- | --- | --- | --- |
| CU-REG-01 | Registrar compras y ventas con el asiento que se generará a la vista, IGV con la tasa vigente a la fecha | IMPLEMENTADO Y VERIFICADO · sin firma contable | PROGRESO pasos 24 y 25; `ImpuestosTests`; `CorteVertical1Tests` | Sí, mostrando la pantalla. No decir «asientos correctos garantizados» |
| CU-REG-02 | Impuestos en el comprobante: ISC, ICBPER, percepción, detracción redondeada, renta de cuarta en recibos por honorarios, IGV sin derecho a crédito | IMPLEMENTADO Y VERIFICADO · sin firma contable | PROGRESO «Paso 25 (parte)» | Con prudencia y solo en demostraciones. Pendientes: descuentos globales e IVAP en ventas |
| CU-REG-03 | Pegar desde Excel e importar compras y ventas (Excel, CSV, TXT) con vista previa fila por fila, sin duplicar lo ya registrado y deshaciendo la importación entera | IMPLEMENTADO Y VERIFICADO | PROGRESO paso 24; 26 pruebas de lectura y 5 de punta a punta | Sí. Es de los mensajes más fuertes. La cifra «5,000 comprobantes en 6.3 s» es de la PC de desarrollo: no publicarla |
| CU-REG-04 | Recuerda el formato de cada archivo: la segunda vez reconoce las columnas solo | IMPLEMENTADO Y VERIFICADO | PROGRESO «Plantillas en el catálogo» | Sí |
| CU-REG-05 | Correlatividad de series de venta: huecos y saltos de fecha | IMPLEMENTADO Y VERIFICADO | PROGRESO paso 24 (ventas) | Sí |
| CU-REG-06 | Libro diario: asientos manuales con destinos automáticos, anular con motivo | IMPLEMENTADO Y VERIFICADO · destinos sin firma | PROGRESO paso 26 (adelanto) | Sí |
| CU-REG-07 | Reglas automáticas que aprenden la cuenta de cada proveedor y explican su confianza | IMPLEMENTADO Y VERIFICADO | PROGRESO FR-040 y FR-041; 15 pruebas del motor | Sí, con la explicación visible («confirmada 40 veces»). No decir «clasifica todo solo» |
| CU-REG-08 | Plan de cuentas editable con 1,832 cuentas y sus destinos | IMPLEMENTADO Y VERIFICADO | PROGRESO FR-020 y decisiones D1 a D4 | Decir «plan de cuentas basado en el PCGE, editable». No decir «PCGE oficial completo»: sale de las plantillas de ContaExcel |
| CU-REG-09 | Tipo de cambio: pegar o importar la tabla publicada; se completa solo desde el SIRE | IMPLEMENTADO PARCIALMENTE | PROGRESO FR-025. La descarga automática no existe | Decir «pegas la tabla una vez», no «tipo de cambio automático» |

### 4.3 SIRE

| Código | Capacidad | Estado | Evidencia | Cómo se puede usar en marketing |
| --- | --- | --- | --- | --- |
| CU-SIRE-01 | Descargar la propuesta del SIRE (compras y ventas) por el API oficial de SUNAT | IMPLEMENTADO PARCIALMENTE | Probado con **un** RUC real: 11 meses, 98 comprobantes en «coincide» (PROGRESO paso 9, 11/10/2026). SUNAT limita con HTTP 429 tras unas 3 propuestas seguidas. POC-1 pide 3 RUC | Mostrable en una demostración en vivo con autorización del titular. No decir «toda tu cartera en un clic» hasta medir el lote con varios RUC |
| CU-SIRE-02 | Importar la propuesta del SIRE descargada de SOL (ZIP o TXT) sin duplicar | IMPLEMENTADO Y VERIFICADO | PROGRESO FR-052; `PropuestaSireTests`; `RevisorSireTests` (18) | Sí |
| CU-SIRE-03 | Cotejar la propuesta con lo registrado: coincide, falta en Cuadra, falta en SUNAT, importe, fecha, tipo de cambio, duplicado | IMPLEMENTADO Y VERIFICADO · definición sin firma | PROGRESO FR-052 y FR-053 | Sí, como «te muestra las diferencias». Las tolerancias son provisionales |
| CU-SIRE-04 | Generar los archivos de reemplazo y complemento del RCE listos para subir en SOL | IMPLEMENTADO PARCIALMENTE | PROGRESO FR-054. Ventas (RVIE) pendiente. Sin firma | Solo compras, y diciendo que se suben en SOL |
| CU-SIRE-05 | Enviar a SUNAT por API: aceptar propuesta, reemplazo, preliminar | EN DESARROLLO | Código del adaptador existe; **nunca se probó contra SUNAT real** | No anunciar |
| CU-SIRE-06 | Claves SOL y del SIRE guardadas cifradas en la PC, con registro de cada uso | IMPLEMENTADO Y VERIFICADO | PROGRESO pasos 14 y 15; 9 pruebas de bóveda | Sí, como argumento de confianza. La custodia de claves de terceros espera dictamen legal (PRD Anexo B) |

### 4.4 Libros, estados y cierre

| Código | Capacidad | Estado | Evidencia | Cómo se puede usar en marketing |
| --- | --- | --- | --- | --- |
| CU-LIB-01 | Libro mayor y balance de comprobación por niveles | IMPLEMENTADO Y VERIFICADO | Corte vertical 1 | Sí |
| CU-LIB-02 | Hoja de trabajo y estados financieros (situación, resultados por naturaleza y por función, comparativo) | IMPLEMENTADO Y VERIFICADO · sin firma | PROGRESO paso 27; 8 pruebas | Sí, mostrando la pantalla. Formatos SMV pendientes |
| CU-LIB-03 | Exportar a PDF y Excel registros, diario, mayor, balance, hoja y estados | IMPLEMENTADO Y VERIFICADO | PROGRESO paso 27 | Sí. Los PDF no son los formatos oficiales 8.1 ni 14.1 y lo dicen |
| CU-LIB-04 | Libros electrónicos PLE en TXT: 5.1, 6.1, 1.1, 1.2 y 5.3 | IMPLEMENTADO PARCIALMENTE | PROGRESO paso 27 (PLE). No consta validación con el validador oficial de SUNAT | Solo «genera los TXT del PLE» con la aclaración pendiente. No decir «listos para presentar» |
| CU-LIB-05 | Cierre del mes con lista de control, sello y bloqueo real del periodo; reapertura con motivo | IMPLEMENTADO Y VERIFICADO | Corte vertical 1, CA-05 y CA-06 | Sí. Es un diferencial fuerte |
| CU-LIB-06 | Cierre anual y apertura del ejercicio; importar balance de apertura desde Excel | IMPLEMENTADO Y VERIFICADO · sin firma | `CierreAnualTests`, `AperturaTests` | Sí, con prudencia |
| CU-LIB-07 | Cobros y pagos, caja y bancos, antigüedad de saldos, transferencias y gastos bancarios con ITF | IMPLEMENTADO Y VERIFICADO · sin firma | `TesoreriaTests` (12) | Sí |

### 4.5 Seguridad, datos y confianza

| Código | Capacidad | Estado | Evidencia | Cómo se puede usar en marketing |
| --- | --- | --- | --- | --- |
| CU-SEG-01 | Los datos viven en la PC del contador, en una base cifrada por empresa | IMPLEMENTADO Y VERIFICADO | PROGRESO paso 5; ADR-08 | Sí. Matiz: el SIRE habla con SUNAT y el asistente IA envía datos resumidos con seudónimos |
| CU-SEG-02 | Copias de seguridad automáticas, cifradas y verificadas, con prueba de restauración | IMPLEMENTADO Y VERIFICADO | PROGRESO pasos 21 y 22; 13 pruebas de integración | Sí |
| CU-SEG-03 | Historial de cambios que nadie puede alterar sin que se note, y deshacer por operación | IMPLEMENTADO Y VERIFICADO | ADR-14 y ADR-15; corte vertical 1 | Sí |
| CU-SEG-04 | Clave de recuperación para abrir los datos en una PC nueva | IMPLEMENTADO Y VERIFICADO | PROGRESO paso 15 | Sí |
| CU-SEG-05 | Impide trabajar con las bases dentro de OneDrive, Google Drive, Dropbox, red o USB | IMPLEMENTADO Y VERIFICADO | CA-14 | Sí, como cuidado del dato |
| CU-SEG-06 | Funciona sin Internet | IMPLEMENTADO PARCIALMENTE | El trabajo contable es local; la licencia permite 30 días sin conexión en el código, pero el servicio de licencias aún no opera | Decir «trabajas en tu PC aunque se caiga el Internet» solo cuando la licencia esté operativa |

### 4.6 Migración, demostración e interfaz

| Código | Capacidad | Estado | Evidencia | Cómo se puede usar en marketing |
| --- | --- | --- | --- | --- |
| CU-MIG-01 | Traer el libro diario completo del sistema anterior (formato ContaExcel o TXT del PLE 5.1) y comparar el balance cuenta por cuenta | IMPLEMENTADO Y VERIFICADO con datos reales en la PC de Didi | PROGRESO FT-101: tres bases reales, la mayor con 65,052 asientos | Sí, sin cifras de clientes. No publicar los nombres ni los números de esas bases |
| CU-DEM-01 | Empresa de ejemplo con datos inventados y modo demostración sin licencia | IMPLEMENTADO Y VERIFICADO | PROGRESO «Empresa de ejemplo» | **Es la base de todas las capturas y vídeos**: datos sintéticos marcados DEMO, sin datos de clientes |
| CU-UI-01 | Interfaz en español de contador, atajos de teclado, temas de color, tamaño de texto, revisión automática de textos cortados | IMPLEMENTADO Y VERIFICADO | PROGRESO «Rediseño vivo» | Sí. La apariencia por defecto es negro con lima y la letra Geist |
| CU-IA-01 | Asistente IA: responde preguntas con cifras verificadas y propone registros que el contador aprueba; nunca borra | EN DESARROLLO | Funciona en desarrollo con modelos gratuitos de OpenRouter y datos sintéticos. Falta la pasarela de producción, el costo y la evaluación de 50 preguntas | **No anunciar como disponible.** Se puede contar como historia de desarrollo, aclarando que es un adicional futuro |

### 4.7 Distribución, cuenta y cobro

| Código | Capacidad | Estado | Evidencia | Cómo se puede usar en marketing |
| --- | --- | --- | --- | --- |
| CU-DIS-01 | Instalador y actualización automática | EN DESARROLLO | Instalador sin firmar generado localmente; ningún release publicado; POC-4 pendiente | No decir «descárgalo» |
| CU-DIS-02 | Cuenta, licencia y prueba de 30 días | EN DESARROLLO | Código y pruebas con nube simulada; proyectos de Supabase creados, tablas e inicio de sesión pendientes | No mencionar la prueba gratuita |
| CU-DIS-03 | Portal web y pago con Yape, Plin o transferencia | PLANIFICADO | `web/index.html` es una página «Muy pronto» | No |
| CU-DIS-04 | Precio | PLANIFICADO | PRD §X.8: «El PRD es agnóstico al precio». Las cifras S/ 24.90, S/ 34.90, S/ 249 y S/ 349 son ejemplos de comisión, no precios | **No publicar ningún precio** |
| CU-DIS-05 | Rendimiento en una PC de 4 GB y en Windows 10 | SIN EVIDENCIA SUFICIENTE | FALTANTES 5.4 y 6.1 | No afirmar requisitos mínimos |

### 4.8 Planificado o fuera del producto

PLANIFICADO (PRD §VI.1 y §XIV.2): inventarios y Kardex, conciliación bancaria, DAOT, formatos SMV y notas, modo fiscalización, recetas de automatización, bandeja documental con QR, papel de trabajo IGV-Renta, vigía de topes, solicitud de documentos, paquete del cliente, multiusuario, respaldo en la nube alojado, IA local.

**Nunca en este producto** (PRD §VI.1): planillas y PLAME, facturación electrónica propia, robot del Buzón SOL, aplicación móvil, producción y costos industriales, CRM. Es útil decirlo: «Cuadra no es un facturador» evita leads equivocados.

## 5. Mensajes que sí se pueden usar hoy

Todos en tono de prelanzamiento y respaldados por la matriz:

1. «Estoy construyendo un sistema contable para el contador que lleva muchas empresas.» (historia de desarrollo; verdadero)
2. «Todas tus empresas en una pantalla, con lo que toca hacer en cada una.» (CU-EMP-02, CU-EMP-03)
3. «Pegas tu Excel de compras y ves fila por fila qué va a pasar antes de guardar. Si te equivocas, deshaces la importación entera.» (CU-REG-03)
4. «Coteja la propuesta del SIRE con tu contabilidad y te dice qué falta y dónde.» (CU-SIRE-02, CU-SIRE-03)
5. «Cierras el mes y queda cerrado de verdad. Si hay que reabrirlo, queda el motivo.» (CU-LIB-05)
6. «Tus datos se quedan en tu PC, cifrados, con copias que se comprueban solas.» (CU-SEG-01, CU-SEG-02)
7. «Buscamos contadores para la beta privada.» (etapa real)

## 6. Lo que no se puede decir (y por qué)

| Afirmación tentadora | Por qué no |
| --- | --- |
| «Descárgalo gratis» o «prueba 30 días» | No hay instalador publicado ni servicio de licencias operativo |
| Cualquier precio, descuento o «precio de fundador» con cifra | No hay precio decidido |
| «Cumple con SUNAT», «asientos 100 % correctos», «homologado» | Ningún caso contable está firmado; no existe homologación de SUNAT para software contable que conste en el repositorio |
| «Envía tu SIRE automáticamente» | El envío por API nunca se probó contra SUNAT |
| «Procesa toda tu cartera en minutos», «1,000 RUC» | Sin medición en el hardware objetivo ni con varios RUC reales |
| «Reemplaza a ContaExcel» o comparativas con nombre | PRD §XVIII.5 fija cuatro condiciones; ninguna se cumple. La publicidad comparativa requiere validación legal |
| «Con inteligencia artificial» como función disponible | El asistente está en desarrollo |
| «Usado por X contadores», testimonios, cifras de ahorro de tiempo | No hay usuarios ni mediciones |
| «PCGE oficial completo», «PLE listo para presentar», «tipo de cambio automático» | Ver matriz: tienen matices |

## 7. Riesgos que esta auditoría detectó para el marketing

1. **Validación contable.** Sin socio contador que firme, toda pieza que explique un tratamiento contable o tributario de Cuadra queda en revisión. Las piezas educativas sobre normas necesitan también un contador que las revise antes de publicarse.
2. **Nombre provisional.** «Cuadra» no tiene búsqueda de marca registrada en el repositorio. Antes de invertir en identidad (dominio, cuentas en redes), conviene buscarlo gratis en el buscador de marcas de INDECOPI. Queda como pendiente.
3. **Dominio.** No hay dominio propio. PRD lo reconoce como gasto inevitable (unos USD 12 a 35 al año) solo cuando haya usuarios externos. Mientras tanto se puede usar un subdominio gratuito de Cloudflare Pages.
4. **Datos personales.** Captar interesados (lista de espera) es tratamiento de datos personales en Perú. Hace falta aviso de privacidad y consentimiento antes de publicar el formulario (ver `docs/SEGURIDAD-Y-PRIVACIDAD.md`).
5. **CI en rojo por vulnerabilidades.** No afecta al marketing, pero conviene que Didi lo revise antes de una beta.
6. **ContaExcel.** El PRD lo trata como competidor y a la vez como obra de Didi. Si ContaExcel tiene usuarios, son la audiencia más cercana para la beta, pero contactarlos exige una base legítima (ver embudos).

## 8. Cómo se mantiene al día

- Cada vez que cambie `docs/PROGRESO.md` en `contatony-2`, el comando `python -m mos producto revisar cuadra` (Fase 2) compara la fecha del último commit leído con la del repositorio y avisa si la auditoría quedó vieja.
- Cambiar un estado en `productos/cuadra/capacidades.toml` exige anotar la evidencia y la fecha. El auditor de calidad rechaza cualquier pieza que cite una capacidad cuyo estado no permita el tipo de afirmación.
